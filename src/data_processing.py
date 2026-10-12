"""Reproducible, chunked preparation of NYC pickup demand from train.csv."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "train.csv"
PROCESSED = ROOT / "data" / "processed" / "demand_aggregated.csv"
PROFILE = ROOT / "data" / "processed" / "data_profile.json"
REQUIRED = {"pickup_datetime", "pickup_latitude", "pickup_longitude", "trip_duration"}
NYC_BOUNDS = {"min_lat": 40.45, "max_lat": 40.95, "min_lon": -74.30, "max_lon": -73.65}
MAX_DEPLOY_BYTES = 24_000_000  # Headroom below the requested 25 MB ceiling.


def _prepare_chunk(chunk: pd.DataFrame, grid_size: float):
    pickup = pd.to_datetime(chunk["pickup_datetime"], errors="coerce")
    lat = pd.to_numeric(chunk["pickup_latitude"], errors="coerce")
    lon = pd.to_numeric(chunk["pickup_longitude"], errors="coerce")
    valid_geo = lat.between(-90, 90) & lon.between(-180, 180)
    in_nyc = (lat.between(NYC_BOUNDS["min_lat"], NYC_BOUNDS["max_lat"])
              & lon.between(NYC_BOUNDS["min_lon"], NYC_BOUNDS["max_lon"]))
    eligible = pickup.notna() & valid_geo & in_nyc
    selected_time = pickup.loc[eligible]
    grouped_input = pd.DataFrame({
        "date": selected_time.dt.strftime("%Y-%m-%d"),
        "hour": selected_time.dt.hour.astype("int8"),
        "day_type": np.where(selected_time.dt.dayofweek < 5, "Weekday", "Weekend"),
        "lat_bin": np.floor(lat.loc[eligible].to_numpy() / grid_size).astype("int16"),
        "lon_bin": np.floor(lon.loc[eligible].to_numpy() / grid_size).astype("int16"),
    })
    grouped = grouped_input.groupby(
        ["date", "hour", "day_type", "lat_bin", "lon_bin"], observed=True,
        sort=False).size().rename("trip_count").reset_index()
    return grouped, pickup, lat, lon, valid_geo, in_nyc, eligible


def build_aggregates(source: Path = SOURCE, output: Path = PROCESSED) -> dict:
    """Read the raw train set in chunks and write a compact, daily grid aggregate."""
    if not source.exists():
        raise FileNotFoundError(f"Missing source data: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    header = pd.read_csv(source, nrows=100)
    if missing := REQUIRED.difference(header.columns):
        raise ValueError(f"train.csv is missing columns: {sorted(missing)}")

    for grid_size in (0.01, 0.02, 0.03, 0.05):
        frames = []
        missing_counts = {column: 0 for column in header.columns}
        total = clean_count = invalid_geo_count = outside_count = invalid_time_count = 0
        zero_or_negative_duration = over_day_duration = 0
        time_min = time_max = None
        hourly = np.zeros(24, dtype=np.int64)
        day_type_counts = {"Weekday": 0, "Weekend": 0}
        lat_samples, lon_samples = [], []

        for chunk in pd.read_csv(source, chunksize=200_000, low_memory=False):
            total += len(chunk)
            for column, count in chunk.isna().sum().items():
                missing_counts[column] += int(count)
            duration = pd.to_numeric(chunk["trip_duration"], errors="coerce")
            zero_or_negative_duration += int(duration.le(0).sum())
            over_day_duration += int(duration.gt(86_400).sum())
            grouped, pickup, lat, lon, valid_geo, in_nyc, eligible = _prepare_chunk(chunk, grid_size)
            frames.append(grouped)
            invalid_geo_count += int((~valid_geo).sum())
            invalid_time_count += int(pickup.isna().sum())
            outside_count += int((valid_geo & ~in_nyc).sum())
            clean_count += int(eligible.sum())
            valid_time = pickup.dropna()
            if not valid_time.empty:
                p_min, p_max = valid_time.min(), valid_time.max()
                time_min = p_min if time_min is None else min(time_min, p_min)
                time_max = p_max if time_max is None else max(time_max, p_max)
            if eligible.any():
                hours = pickup.loc[eligible].dt.hour
                hourly += np.bincount(hours.to_numpy(), minlength=24)
                day_type_counts["Weekday"] += int((pickup.loc[eligible].dt.dayofweek < 5).sum())
                day_type_counts["Weekend"] += int((pickup.loc[eligible].dt.dayofweek >= 5).sum())
                lat_samples.append(lat.loc[eligible].to_numpy(dtype="float32"))
                lon_samples.append(lon.loc[eligible].to_numpy(dtype="float32"))

        combined = pd.concat(frames, ignore_index=True)
        aggregate = combined.groupby(
            ["date", "hour", "day_type", "lat_bin", "lon_bin"], observed=True,
            sort=True, as_index=False)["trip_count"].sum()
        aggregate["grid_lat"] = ((aggregate.pop("lat_bin") + .5) * grid_size).round(4)
        aggregate["grid_lon"] = ((aggregate.pop("lon_bin") + .5) * grid_size).round(4)
        aggregate = aggregate[["date", "hour", "day_type", "grid_lat", "grid_lon", "trip_count"]]
        temporary = output.with_suffix(".tmp")
        aggregate.to_csv(temporary, index=False)
        size = temporary.stat().st_size
        if size >= MAX_DEPLOY_BYTES:
            temporary.unlink()
            continue
        temporary.replace(output)
        latitude = np.concatenate(lat_samples)
        longitude = np.concatenate(lon_samples)
        profile = {
            "source": source.name,
            "source_bytes": source.stat().st_size,
            "raw_rows": total,
            "raw_columns": len(header.columns),
            "columns": {col: str(dtype) for col, dtype in header.dtypes.items()},
            "missing_values": missing_counts,
            "pickup_datetime_min": str(time_min),
            "pickup_datetime_max": str(time_max),
            "nyc_bounds": NYC_BOUNDS,
            "invalid_pickup_coordinates": invalid_geo_count,
            "outside_nyc_bounds": outside_count,
            "invalid_pickup_datetime": invalid_time_count,
            "zero_or_negative_trip_duration": zero_or_negative_duration,
            "trip_duration_over_24_hours": over_day_duration,
            "retained_pickups": clean_count,
            "excluded_pickups": total - clean_count,
            "latitude_quantiles": {str(q): float(np.quantile(latitude, q)) for q in (.01, .5, .99)},
            "longitude_quantiles": {str(q): float(np.quantile(longitude, q)) for q in (.01, .5, .99)},
            "hourly_pickups": hourly.tolist(),
            "day_type_pickups": day_type_counts,
            "grid_size_degrees": grid_size,
            "aggregate_rows": len(aggregate),
            "aggregate_bytes": size,
            "aggregate_date_min": aggregate["date"].min(),
            "aggregate_date_max": aggregate["date"].max(),
        }
        PROFILE.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        return profile
    raise RuntimeError("Daily aggregation exceeded 25 MB even with a 0.05-degree grid.")


if __name__ == "__main__":
    print(json.dumps(build_aggregates(), indent=2))

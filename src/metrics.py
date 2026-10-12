"""One consistent pickup-count denominator for every dashboard component."""

import pandas as pd


def filter_demand(data: pd.DataFrame, start, end, day_type: str) -> pd.DataFrame:
    if start > end:
        raise ValueError("Start date must not be later than end date.")
    selected = data.loc[data["date"].dt.date.between(start, end)]
    if day_type != "All":
        selected = selected.loc[selected["day_type"].eq(day_type)]
    return selected


def hourly_profile(data: pd.DataFrame) -> pd.Series:
    return data.groupby("hour", observed=True)["trip_count"].sum().reindex(range(24), fill_value=0)


def headline_metrics(data: pd.DataFrame) -> dict:
    if data.empty:
        return {"total": 0, "peak_hour": None, "top_zone": None}
    hour = hourly_profile(data)
    zones = data.groupby(["grid_lat", "grid_lon"], observed=True)["trip_count"].sum()
    return {"total": int(data["trip_count"].sum()),
            "peak_hour": int(hour.idxmax()), "top_zone": zones.idxmax()}


def hour_zones(data: pd.DataFrame, hour: int) -> pd.DataFrame:
    selected = data.loc[data["hour"].eq(hour)]
    return selected.groupby(["grid_lat", "grid_lon"], observed=True, as_index=False)["trip_count"].sum()


def fixed_scale_max(data: pd.DataFrame) -> int:
    if data.empty:
        return 1
    per_hour_zone = data.groupby(["hour", "grid_lat", "grid_lon"], observed=True)["trip_count"].sum()
    return max(1, int(per_hour_zone.max()))

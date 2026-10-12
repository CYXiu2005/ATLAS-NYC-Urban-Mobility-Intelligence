"""Load only the deployment aggregate at dashboard runtime."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.data_processing import PROFILE, PROCESSED


@st.cache_data(show_spinner="Loading pickup demand…")
def _read_aggregate(path: str, modified: int) -> pd.DataFrame:
    _ = modified
    frame = pd.read_csv(path, parse_dates=["date"], dtype={
        "hour": "int8", "day_type": "category", "grid_lat": "float32",
        "grid_lon": "float32", "trip_count": "int32"})
    expected = {"date", "hour", "day_type", "grid_lat", "grid_lon", "trip_count"}
    if expected.difference(frame.columns):
        raise ValueError(f"Aggregate missing columns: {sorted(expected.difference(frame.columns))}")
    return frame


@st.cache_data(show_spinner=False)
def _read_profile(path: str, modified: int) -> dict:
    _ = modified
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_dashboard_data() -> tuple[pd.DataFrame, dict]:
    if not PROCESSED.exists() or not PROFILE.exists():
        raise FileNotFoundError("Prepared data are missing. Run `uv run python -m src.data_processing` first.")
    return (_read_aggregate(str(PROCESSED), PROCESSED.stat().st_mtime_ns),
            _read_profile(str(PROFILE), PROFILE.stat().st_mtime_ns))

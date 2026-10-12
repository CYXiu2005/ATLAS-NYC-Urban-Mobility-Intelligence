"""ATLAS · historical NYC pickup demand for regional fleet planning."""

from pathlib import Path

import streamlit as st

from src.data_loader import load_dashboard_data
from src.metrics import filter_demand, fixed_scale_max, headline_metrics, hour_zones, hourly_profile
from src.visualizations import demand_map, hourly_chart


st.set_page_config(page_title="ATLAS | NYC Urban Mobility Intelligence", page_icon="◆", layout="wide")
st.markdown(f"<style>{(Path(__file__).parent / 'assets' / 'style.css').read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True)


def _hour_label(hour: int) -> str:
    return f"{hour:02d}:00–{(hour + 1):02d}:00"


@st.fragment(run_every="0.8s")
def playing_panel(data, scale_max):
    _demand_panel(data, scale_max, advance=True)


@st.fragment
def paused_panel(data, scale_max):
    _demand_panel(data, scale_max, advance=False)


def _demand_panel(data, scale_max: int, advance: bool):
    controls, action = st.columns([8, 1], vertical_alignment="bottom")
    with action:
        if st.button("❚❚ Pause" if advance else "▶ Play", width="stretch", type="primary"):
            st.session_state.playing = not advance
            st.rerun()
    if advance:
        st.session_state.selected_hour = (st.session_state.selected_hour + 1) % 24
        st.session_state.hour_widget = st.session_state.selected_hour
    elif st.session_state.get("last_playing", False):
        st.session_state.hour_widget = st.session_state.selected_hour
    with controls:
        hour = st.slider("Hour of day", 0, 23, key="hour_widget", format="%02d:00")
    st.session_state.selected_hour = hour
    st.session_state.last_playing = advance

    hour = st.session_state.selected_hour
    zones = hour_zones(data, hour)
    hour_total = int(zones["trip_count"].sum()) if not zones.empty else 0
    st.markdown(f'''<div class="map-context">
        <span><b>SELECTED HOUR</b><strong>{_hour_label(hour)}</strong></span>
        <span><b>ACTIVE PICKUP ZONES</b><strong>{len(zones):,}</strong></span>
        <span><b>TRIPS IN SELECTED HOUR</b><strong>{hour_total:,}</strong></span>
        <span class="map-note">Fixed color scale across all 24 hours</span>
    </div>''', unsafe_allow_html=True)
    st.pydeck_chart(demand_map(zones, scale_max), height=390, width="stretch")
    st.markdown('<div class="section-heading">HOURLY PICKUP DEMAND</div>', unsafe_allow_html=True)
    st.plotly_chart(hourly_chart(hourly_profile(data), hour), width="stretch",
                    config={"displayModeBar": False})


st.markdown('''<div class="masthead"><div><div class="brand">◆ &nbsp; ATLAS</div>
    <div class="brand-detail">NYC URBAN MOBILITY INTELLIGENCE</div></div>
    <div class="masthead-right">NEW YORK CITY<br><strong>HISTORICAL DATA</strong></div></div>''',
            unsafe_allow_html=True)
st.markdown('<div class="subtitle">Historical pickup demand intelligence for regional fleet planning.</div>',
            unsafe_allow_html=True)

try:
    all_data, profile = load_dashboard_data()
except (FileNotFoundError, ValueError) as exc:
    st.error(str(exc))
    st.info("Place `data/processed/demand_aggregated.csv` and `data_profile.json` in the project, "
            "or run `uv run python -m src.data_processing` with the Kaggle train.csv available locally.")
    st.stop()

date_min = all_data["date"].min().date()
date_max = all_data["date"].max().date()
filter_left, filter_right, filler = st.columns([3, 2, 5], vertical_alignment="bottom")
with filter_left:
    date_range = st.date_input("Date Range", value=(date_min, date_max),
                               min_value=date_min, max_value=date_max)
with filter_right:
    day_type = st.selectbox("Day Type", ["All", "Weekday", "Weekend"])

if len(date_range) != 2:
    st.info("Select both a start and end date to view pickup demand.")
    st.stop()
try:
    data = filter_demand(all_data, date_range[0], date_range[1], day_type)
except ValueError as exc:
    st.warning(str(exc))
    st.stop()
if data.empty:
    st.info("No recorded pickups match the selected dates and day type. Try another range.")
    st.stop()

metrics = headline_metrics(data)
top_lat, top_lon = metrics["top_zone"]
k1, k2, k3 = st.columns(3, gap="medium")
with k1.container(border=True):
    st.metric("TOTAL PICKUPS", f"{metrics['total']:,}")
    st.caption("Recorded trips in the selected period")
with k2.container(border=True):
    st.metric("PEAK DEMAND HOUR", _hour_label(metrics["peak_hour"]))
    st.caption("Highest pickup count across 24 hours")
with k3.container(border=True):
    st.metric("TOP PICKUP ZONE", f"{top_lat:.3f}, {top_lon:.3f}")
    st.caption("Center of the busiest 0.01° grid cell")

st.markdown('<div class="section-heading">SPATIOTEMPORAL DEMAND MAP</div>', unsafe_allow_html=True)
st.caption("Recorded pickups by location and hour · drag to pan, scroll to zoom, hover for a grid count")
if "selected_hour" not in st.session_state:
    st.session_state.selected_hour = 18
if "hour_widget" not in st.session_state:
    st.session_state.hour_widget = st.session_state.selected_hour
if "playing" not in st.session_state:
    st.session_state.playing = False
scale_max = fixed_scale_max(data)
if st.session_state.playing:
    playing_panel(data, scale_max)
else:
    paused_panel(data, scale_max)

st.markdown(f'''<div class="footer">DATA SOURCE: KAGGLE NYC TAXI TRIP DURATION &nbsp; · &nbsp;
    DATA PERIOD: {profile['aggregate_date_min']} TO {profile['aggregate_date_max']} &nbsp; · &nbsp;
    STATUS: HISTORICAL SNAPSHOT &nbsp; · &nbsp;
    PROPOSED PRODUCTION REFRESH: EVERY 15 MINUTES</div>''', unsafe_allow_html=True)

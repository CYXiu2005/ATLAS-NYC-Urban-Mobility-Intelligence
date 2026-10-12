"""ATLAS: historical NYC pickup demand command center and decision analysis."""

from datetime import timedelta
from pathlib import Path
from time import monotonic

import streamlit as st

from src.data_loader import load_dashboard_data
from src.data_processing import PROCESSED
from src.metrics import (daily_pickups, filter_demand, headline_metrics,
                         hourly_profile, weekday_daily_profile)
from src.visualizations import (daily_trend_chart, demand_map, hourly_chart_html,
                                weekday_average_chart)

PLAYBACK_INTERVAL_SECONDS = 2.5


st.set_page_config(
    page_title="ATLAS | NYC Urban Mobility Intelligence", page_icon="◆",
    layout="wide", initial_sidebar_state="collapsed",
)
st.markdown(
    f"<style>{(Path(__file__).parent / 'assets' / 'style.css').read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)


def hour_label(hour: int) -> str:
    return f"{hour:02d}:00–{(hour + 1):02d}:00"


@st.cache_data(show_spinner=False)
def prepared_view(start, end, day_type: str, source_modified: int, _source):
    """Aggregate a filter selection once; playback then selects one hour's grids."""
    _ = source_modified  # Invalidate this cache if the deployment CSV changes.
    filtered = filter_demand(_source, start, end, day_type)
    if filtered.empty:
        return None
    profile = hourly_profile(filtered)
    metrics = headline_metrics(filtered)
    by_hour = filtered.groupby(
        ["hour", "grid_lat", "grid_lon"], observed=True, as_index=False,
    )["trip_count"].sum()
    scale_max = max(1, int(by_hour["trip_count"].max()))
    return profile, metrics, by_hour, scale_max


@st.cache_data(show_spinner=False)
def prepared_analysis(start, end, day_type: str, source_modified: int, _source):
    """Compute daily demand only when the analytics filter changes."""
    _ = source_modified
    filtered = filter_demand(_source, start, end, day_type)
    if filtered.empty:
        return None
    daily = daily_pickups(filtered)
    return daily, weekday_daily_profile(daily)


def update_hour_on_scrub() -> None:
    st.session_state.selected_hour = st.session_state.hour_widget
    st.session_state.last_tick = monotonic()


def update_map_date() -> None:
    st.session_state.date_selection = tuple(st.session_state.map_date_range)


def update_map_day_type() -> None:
    st.session_state.day_selection = st.session_state.map_day_type


def update_analysis_date() -> None:
    st.session_state.date_selection = tuple(st.session_state.analysis_date_range)


def update_analysis_day_type() -> None:
    st.session_state.day_selection = st.session_state.analysis_day_type


st.markdown(
    '''<header class="masthead">
        <div class="brand-block"><div class="brand">ATLAS<span class="brand-mark">◆</span></div>
        <div class="brand-detail">NYC URBAN MOBILITY INTELLIGENCE</div></div>
        <div class="masthead-right"><span>NEW YORK CITY</span><strong>HISTORICAL DATA</strong></div>
    </header>
    <p class="subtitle">Historical pickup demand intelligence for regional fleet planning.</p>''',
    unsafe_allow_html=True,
)

try:
    all_data, source_profile = load_dashboard_data()
except (FileNotFoundError, ValueError) as exc:
    st.error(str(exc))
    st.info("Place `data/processed/demand_aggregated.csv` and `data_profile.json` in the project, "
            "or rebuild them from a locally downloaded Kaggle train.csv.")
    st.stop()

date_min = all_data["date"].min().date()
date_max = all_data["date"].max().date()
st.session_state.setdefault("date_selection", (date_min, date_max))
st.session_state.setdefault("day_selection", "All")
st.session_state.setdefault("selected_hour", 0)
st.session_state.setdefault("hour_widget", st.session_state.selected_hour)
st.session_state.setdefault("playing", True)  # Start the command center in motion.
st.session_state.setdefault("last_tick", monotonic())
if (st.session_state.date_selection[0] < date_min
        or st.session_state.date_selection[1] > date_max):
    st.session_state.date_selection = (date_min, date_max)


def render_command_center() -> None:
    left, right = st.columns([1.15, 2.85], gap="medium", vertical_alignment="top")
    with left:
        with st.container(key="intelligence_panel"):
            st.page_link(analysis_page, label="Demand Analysis", icon=":material/analytics:",
                         help="Open the Demand Analysis page", width="stretch")
            st.markdown('<div class="panel-eyebrow">DECISION INTELLIGENCE</div>',
                        unsafe_allow_html=True)
            overview_slot = st.empty()
            chart_slot = st.empty()
            zone_slot = st.empty()
            st.markdown('<div class="panel-heading filter-heading">FILTERS</div>',
                        unsafe_allow_html=True)
            st.session_state.map_date_range = st.session_state.date_selection
            date_range = st.slider(
                "Date Range", min_value=date_min, max_value=date_max,
                step=timedelta(days=1), format="MM/DD", key="map_date_range",
                on_change=update_map_date,
            )
            st.caption(f"{date_range[0]:%Y-%m-%d}  →  {date_range[1]:%Y-%m-%d}")
            st.session_state.map_day_type = st.session_state.day_selection
            day_type = st.selectbox(
                "Day Type", ["All", "Weekday", "Weekend"],
                key="map_day_type", on_change=update_map_day_type,
            )

    try:
        view = prepared_view(
            date_range[0], date_range[1], day_type,
            PROCESSED.stat().st_mtime_ns, all_data,
        )
    except ValueError as exc:
        st.warning(str(exc))
        view = None
    if view is None:
        with overview_slot:
            st.info("No recorded pickups match these dates and day type.")
        with right:
            st.info("Try another date range or day type to view the historical map.")
        return

    profile, metrics, by_hour, scale_max = view
    with chart_slot.container():
        st.markdown('<div class="panel-heading chart-heading">HOURLY DEMAND PROFILE</div>',
                    unsafe_allow_html=True)
        st.markdown(hourly_chart_html(profile), unsafe_allow_html=True)
        st.markdown(
            '<div class="chart-key"><span class="selected-dot"></span>Selected hour'
            '<span class="peak-dot"></span>Peak hour</div>',
            unsafe_allow_html=True,
        )
        chart_highlight_slot = st.empty()

    # A 3D map redraw is costly on Community Cloud. Let the browser finish each
    # frame before asking Streamlit to send another one.
    @st.fragment(run_every=PLAYBACK_INTERVAL_SECONDS if st.session_state.playing else None)
    def playback() -> None:
        if (st.session_state.playing
                and monotonic() - st.session_state.last_tick >= PLAYBACK_INTERVAL_SECONDS * .8):
            st.session_state.selected_hour = (st.session_state.selected_hour + 1) % 24
            st.session_state.hour_widget = st.session_state.selected_hour
            st.session_state.last_tick = monotonic()
        selected_hour = st.session_state.selected_hour
        zones = by_hour.loc[by_hour["hour"].eq(selected_hour)].copy()
        hour_total = int(profile.loc[selected_hour])

        # Replace only the live content; the left panel's navigation and filters stay mounted.
        with overview_slot.container():
            st.markdown('<div class="panel-heading">FLEET OVERVIEW</div>',
                        unsafe_allow_html=True)
            st.metric("01  PICKUPS THIS HOUR", f"{hour_total:,}")
            st.caption(f"{hour_label(selected_hour)} · {metrics['total']:,} in selected period")
            st.metric("02  SELECTED HOUR", hour_label(selected_hour))
            st.caption(f"Period peak: {hour_label(metrics['peak_hour'])}")

        # Update one style rule; the 24 chart bars never remount during playback.
        with chart_highlight_slot:
            st.markdown(
                f'<style>.hourly-chart .hour-bar[data-hour="{selected_hour}"]'
                '{background:#39C9F0}</style>',
                unsafe_allow_html=True,
            )

        with zone_slot.container():
            if zones.empty:
                st.metric("03  TOP GRID THIS HOUR", "—")
                st.caption("No recorded pickups in this hour")
            else:
                top_zone = zones.loc[zones["trip_count"].idxmax()]
                st.metric("03  TOP GRID THIS HOUR",
                          f"{top_zone['grid_lat']:.3f}, {top_zone['grid_lon']:.3f}")
                st.caption(f"{int(top_zone['trip_count']):,} pickups in the busiest 0.01° grid")

        with st.container(key="map_panel"):
            st.markdown('<div class="map-title-row"><div class="panel-heading">'
                        'SPATIOTEMPORAL DEMAND MAP</div>'
                        '<div class="map-mode">HISTORICAL PICKUPS BY HOUR</div></div>',
                        unsafe_allow_html=True)
            st.markdown(
                f'''<div class="map-context">
                    <span><small>SELECTED HOUR</small><strong>{hour_label(selected_hour)}</strong></span>
                    <span><small>ACTIVE PICKUP ZONES</small><strong>{len(zones):,}</strong></span>
                    <span><small>PICKUPS THIS HOUR</small><strong>{hour_total:,}</strong></span>
                </div>''', unsafe_allow_html=True,
            )
            st.pydeck_chart(
                demand_map(zones, scale_max, selected_hour),
                height=620, width="stretch", key="demand-map",
                alt="3D columns show recorded New York City taxi pickups by grid for the selected hour.",
            )
            st.markdown(
                '<div class="map-legend"><b>PICKUP INTENSITY</b><span>LOW</span>'
                '<i class="legend-gradient"></i><span>HIGH</span>'
                '<em>Column height uses square-root visual scaling; hover for recorded counts. '
                'Color scale stays fixed across all 24 hours for this filter.</em></div>',
                unsafe_allow_html=True,
            )
            with st.container(key="timeline_bar"):
                play_col, first_col, slider_col, last_col, current_col = st.columns(
                    [1.35, .55, 7.6, .55, 1.75], gap="small", vertical_alignment="center",
                )
                with play_col:
                    if st.button("❚❚ PAUSE" if st.session_state.playing else "▶ PLAY",
                                 key="play-toggle", width="stretch", type="primary",
                                 help="Playback runs from 00:00 to 23:00, then loops to 00:00."):
                        st.session_state.playing = not st.session_state.playing
                        st.session_state.last_tick = monotonic()
                        st.rerun()
                with first_col:
                    st.markdown('<span class="timeline-end">00</span>', unsafe_allow_html=True)
                with slider_col:
                    st.slider("Hour of day", 0, 23, key="hour_widget",
                              label_visibility="collapsed", on_change=update_hour_on_scrub)
                with last_col:
                    st.markdown('<span class="timeline-end">23</span>', unsafe_allow_html=True)
                with current_col:
                    st.markdown(f'<span class="timeline-current">{selected_hour:02d}:00</span>',
                                unsafe_allow_html=True)

    with right:
        playback()


def render_analysis() -> None:
    with st.container(key="analysis_navigation"):
        title_col, back_col = st.columns([4.2, 1], gap="medium", vertical_alignment="center")
        with title_col:
            st.markdown('<div class="analysis-eyebrow">FLEET PLANNING / HISTORICAL PATTERNS</div>'
                        '<h1 class="analysis-title">DEMAND ANALYSIS</h1>'
                        '<p class="analysis-summary">Use observed pickup patterns to review daily '
                        'staffing levels and weekday shift plans.</p>', unsafe_allow_html=True)
        with back_col:
            st.page_link(command_page, label="Command Center", icon=":material/arrow_back:",
                         width="content")

    with st.container(key="analysis_filters"):
        date_col, type_col = st.columns([3, 1], gap="medium", vertical_alignment="bottom")
        with date_col:
            st.session_state.analysis_date_range = st.session_state.date_selection
            date_range = st.slider(
                "Date Range", min_value=date_min, max_value=date_max,
                step=timedelta(days=1), format="MMM D, YYYY", key="analysis_date_range",
                on_change=update_analysis_date,
            )
        with type_col:
            st.session_state.analysis_day_type = st.session_state.day_selection
            day_type = st.selectbox(
                "Day Type", ["All", "Weekday", "Weekend"],
                key="analysis_day_type", on_change=update_analysis_day_type,
            )
        st.caption(f"Selected: {date_range[0]:%Y-%m-%d} to {date_range[1]:%Y-%m-%d} · {day_type}")

    view = prepared_analysis(
        date_range[0], date_range[1], day_type,
        PROCESSED.stat().st_mtime_ns, all_data,
    )
    if view is None:
        st.info("No recorded pickups match this selection. Expand the dates or change Day Type.")
        return
    daily, weekday_stats = view
    peak_date = daily.idxmax()
    peak_weekday = int(weekday_stats["mean_pickups"].idxmax())
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                     "Friday", "Saturday", "Sunday"]

    k1, k2, k3 = st.columns(3, gap="medium")
    with k1:
        st.metric("PICKUPS / OBSERVED DAY", f"{daily.mean():,.0f}")
        st.caption(f"Across {len(daily):,} dates with recorded trips")
    with k2:
        st.metric("PEAK DATE", peak_date.strftime("%d %b %Y"))
        st.caption(f"{int(daily.max()):,} recorded pickups on that date")
    with k3:
        st.metric("TOP WEEKDAY · DAILY AVG", weekday_names[peak_weekday])
        st.caption(f"{weekday_stats.loc[peak_weekday, 'mean_pickups']:,.0f} pickups per observed {weekday_names[peak_weekday]}")

    trend_col, weekday_col = st.columns([1.45, 1], gap="medium")
    with trend_col:
        with st.container(key="analysis_trend"):
            st.markdown('<div class="panel-heading">DAILY PICKUP TREND</div>', unsafe_allow_html=True)
            st.caption("Spot unusually busy dates and periods that may warrant extra shift coverage.")
            st.plotly_chart(daily_trend_chart(daily), width="stretch",
                            config={"displayModeBar": False})
    with weekday_col:
        with st.container(key="analysis_weekday"):
            st.markdown('<div class="panel-heading">AVERAGE DEMAND BY WEEKDAY</div>',
                        unsafe_allow_html=True)
            st.caption("Compare staffing baselines fairly across weekdays with different date counts.")
            st.plotly_chart(weekday_average_chart(weekday_stats), width="stretch",
                            config={"displayModeBar": False})
    st.markdown(
        '<div class="analysis-note"><b>PLANNING USE</b> Compare above-median dates with known '
        'events and use weekday averages as a starting point for shift reviews. These are sampled '
        'historical trips; the charts do not measure unserved requests or available drivers.</div>',
        unsafe_allow_html=True,
    )


command_page = st.Page(render_command_center, title="Command Center", default=True)
analysis_page = st.Page(render_analysis, title="Demand Analysis", url_path="analysis")
page = st.navigation([command_page, analysis_page], position="hidden")
page.run()
st.markdown(
    f'''<div class="footer"><strong>HISTORICAL SNAPSHOT</strong><span>Source: Kaggle NYC Taxi Trip Duration</span>
        <span>Period: {source_profile['aggregate_date_min']} – {source_profile['aggregate_date_max']}</span>
        <span>Production proposal: refresh every 15 minutes with a live source; no live API here.</span></div>''',
    unsafe_allow_html=True,
)

"""Two decision visuals: historical pickup grids and the 24-hour profile."""

from math import ceil, log10

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk


CARTO_DARK = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
COLOR_STOPS = np.array([
    [24, 77, 120],   # low: deep blue
    [32, 184, 213],  # moderate: cyan
    [255, 200, 87],  # high: amber
    [255, 105, 74],  # critical: orange-red
])


def demand_map(zones: pd.DataFrame, scale_max: int, selected_hour: int) -> pdk.Deck:
    points = zones.copy()
    counts = points["trip_count"].to_numpy(dtype=float)
    # Square-root compression reveals quieter grids without changing recorded counts.
    # The denominator is fixed across all 24 hours for the current date/day-type filter.
    strength = np.sqrt(np.clip(counts / max(scale_max, 1), 0, 1))
    channel = np.linspace(0, 1, len(COLOR_STOPS))
    rgb = np.column_stack([
        np.interp(strength, channel, COLOR_STOPS[:, index])
        for index in range(3)
    ]).astype(int)
    # Separate numeric channels avoid PyDeck's ambiguous object-array accessor.
    points["red"] = rgb[:, 0]
    points["green"] = rgb[:, 1]
    points["blue"] = rgb[:, 2]
    points["elevation"] = 35 + 3200 * strength
    points["grid_id"] = [
        f"NYC-{round(lat * 1000):05d}N-{round(abs(lon) * 1000):05d}W"
        for lat, lon in zip(points["grid_lat"], points["grid_lon"])
    ]
    points["grid_center"] = [
        f"{lat:.3f}, {lon:.3f}"
        for lat, lon in zip(points["grid_lat"], points["grid_lon"])
    ]
    points["selected_hour"] = f"{selected_hour:02d}:00–{(selected_hour + 1):02d}:00"
    layer = pdk.Layer(
        "ColumnLayer", points, id="pickup-grid-columns",
        get_position="[grid_lon, grid_lat]", get_elevation="elevation",
        get_fill_color="[red, green, blue, 202]", radius=340, elevation_scale=1,
        disk_resolution=6, extruded=True, pickable=True, auto_highlight=True,
    )
    return pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(
            latitude=40.735, longitude=-73.95, zoom=10.8, pitch=43, bearing=0,
        ),
        map_style=CARTO_DARK,
        tooltip={
            "html": (
                "<div style='font-size:10px;letter-spacing:.14em;color:#91A9BA'>PICKUP GRID</div>"
                "<div style='font-size:17px;font-weight:700;color:#EAF3FA'>"
                "{trip_count} recorded pickups</div>"
                "<div>Grid ID: {grid_id}</div>"
                "<div>Grid center: {grid_center}</div>"
                "<div>Selected hour: {selected_hour}</div>"
            ),
            "style": {"backgroundColor": "#0D1B2A", "color": "#D5E5EF", "fontSize": "12px"},
        },
    )


def hourly_chart_html(profile: pd.Series) -> str:
    """Build a fixed bar chart; playback changes only its selected-bar CSS rule."""
    values = [int(profile.loc[hour]) for hour in range(24)]
    maximum = max(values)
    step = 10 ** int(log10(maximum)) if maximum else 1
    axis_max = max(step, ceil(maximum / step) * step)
    midpoint = axis_max / 2
    midpoint_label = f"{midpoint / 1000:g}k" if midpoint >= 1000 else f"{midpoint:g}"
    peak_hour = int(profile.idxmax())
    bars = "".join(
        f'<div class="hour-bar{" peak" if hour == peak_hour else ""}" '
        f'data-hour="{hour}" style="height:{count / axis_max * 100:.2f}%" '
        f'title="{hour:02d}:00–{hour + 1:02d}:00 · {count:,} recorded pickups"></div>'
        for hour, count in enumerate(values)
    )
    ticks = "".join(
        f'<span class="hour-tick tick-{hour}">{hour:02d}</span>'
        for hour in (0, 6, 12, 18, 23)
    )
    return (
        '<div class="hourly-chart" role="img" '
        'aria-label="Recorded pickups by hour; cyan marks the selected hour and amber marks the peak">'
        f'<div class="hourly-y-axis"><span>{midpoint_label}</span><span>0</span></div>'
        f'<div class="hourly-bars">{bars}</div>'
        f'<div class="hourly-x-axis">{ticks}</div></div>'
    )


def daily_trend_chart(daily: pd.Series) -> go.Figure:
    """Daily recorded demand and the median of the selected observed dates."""
    fig = go.Figure(go.Scatter(
        x=daily.index, y=daily.to_numpy(), mode="lines+markers",
        line=dict(color="#39C9F0", width=2.5), marker=dict(size=5, color="#39C9F0"),
        fill="tozeroy", fillcolor="rgba(57,201,240,.08)",
        hovertemplate="%{x|%b %d, %Y}<br><b>%{y:,} recorded pickups</b><extra></extra>",
    ))
    fig.add_hline(
        y=float(daily.median()), line=dict(color="#FFC857", width=1.5, dash="dash"),
        annotation_text="Selected-period median", annotation_position="top left",
        annotation_font_color="#FFC857",
    )
    fig.update_layout(
        height=335, margin=dict(l=15, r=18, t=30, b=32),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#91A9BA", size=11), showlegend=False,
        xaxis=dict(title=None, showgrid=False, tickformat="%b %d", fixedrange=True),
        yaxis=dict(title="Recorded pickups / day", gridcolor="rgba(145,169,186,.12)",
                   zeroline=False, tickformat="~s", fixedrange=True),
        hoverlabel=dict(bgcolor="#112235", font_color="#EAF3FA"),
    )
    return fig


def weekday_average_chart(stats: pd.DataFrame) -> go.Figure:
    """Average daily pickups by weekday, avoiding unequal weekday exposure bias."""
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    mean = stats["mean_pickups"]
    peak = int(mean.idxmax())
    colors = [
        "#FFC857" if day == peak else "#39C9F0" if day >= 5 else "#316680"
        for day in range(7)
    ]
    fig = go.Figure(go.Bar(
        x=labels, y=mean.to_numpy(), marker_color=colors, marker_line_width=0,
        customdata=stats[["observed_days", "total_pickups"]].to_numpy(),
        hovertemplate=("%{x}<br><b>%{y:,.0f} pickups / observed day</b>"
                       "<br>%{customdata[0]:.0f} observed days"
                       "<br>%{customdata[1]:,.0f} recorded pickups<extra></extra>"),
    ))
    fig.update_layout(
        height=335, margin=dict(l=15, r=12, t=30, b=32),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#91A9BA", size=11), showlegend=False, bargap=.28,
        xaxis=dict(title=None, showgrid=False, fixedrange=True),
        yaxis=dict(title="Mean recorded pickups", gridcolor="rgba(145,169,186,.12)",
                   zeroline=False, tickformat="~s", fixedrange=True),
        hoverlabel=dict(bgcolor="#112235", font_color="#EAF3FA"),
    )
    return fig

"""Map and single supporting chart for regional pickup planning."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk


CARTO_DARK = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"


def demand_map(zones: pd.DataFrame, scale_max: int) -> pdk.Deck:
    points = zones.copy()
    strength = np.log1p(points["trip_count"].to_numpy()) / np.log1p(max(scale_max, 1))
    strength = np.clip(strength, 0, 1)
    points["color"] = [
        [int(40 + 215 * x), int(173 - 94 * x), int(235 - 183 * x), 210]
        for x in strength]
    points["elevation"] = 60 + 3100 * strength
    layer = pdk.Layer(
        "ColumnLayer", points, get_position="[grid_lon, grid_lat]",
        get_elevation="elevation", get_fill_color="color", radius=410,
        elevation_scale=1, disk_resolution=6, extruded=True,
        pickable=True, auto_highlight=True)
    return pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(latitude=40.755, longitude=-73.96,
                                         zoom=10.4, pitch=48, bearing=0),
        map_style=CARTO_DARK,
        tooltip={"html": "<b>{trip_count} recorded pickups</b><br/>Grid center: {grid_lat}, {grid_lon}",
                 "style": {"backgroundColor": "#13263B", "color": "#EAF2F8", "fontSize": "13px"}})


def hourly_chart(profile: pd.Series, selected_hour: int) -> go.Figure:
    values = profile.to_numpy()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(24)), y=values, mode="lines+markers", fill="tozeroy",
        line=dict(color="#52C8EF", width=2.5), marker=dict(size=5, color="#52C8EF"),
        fillcolor="rgba(69,184,220,.13)", name="Recorded pickups",
        hovertemplate="%{x}:00–%{x}:59<br>%{y:,} pickups<extra></extra>"))
    fig.add_vline(x=selected_hour, line_color="#FF985D", line_width=2,
                  annotation_text="Selected hour", annotation_position="top right")
    fig.add_trace(go.Scatter(x=[selected_hour], y=[values[selected_hour]], mode="markers",
                             marker=dict(size=12, color="#FF985D", line=dict(color="#FFE5D5", width=2)),
                             hovertemplate="%{x}:00–%{x}:59<br>%{y:,} pickups<extra></extra>",
                             showlegend=False))
    fig.update_layout(
        height=225, margin=dict(l=15, r=15, t=28, b=28),
        paper_bgcolor="#101B2B", plot_bgcolor="#101B2B", font=dict(color="#DDE8F1"),
        showlegend=False, xaxis=dict(title="Hour of day", tickmode="linear", dtick=2,
                                      gridcolor="rgba(130,148,171,.11)", range=[-.3, 23.3]),
        yaxis=dict(title="Pickup count", gridcolor="rgba(130,148,171,.15)", rangemode="tozero"),
        hoverlabel=dict(bgcolor="#1B3147", font_color="#FFFFFF"))
    return fig

# bc_transit_victoria_tracker.py
import json
import dash
import geopandas as gpd
import plotly.express as px
from dash import dcc, html
from dash.dependencies import Output, Input
import plotly.graph_objects as go
import os
import subprocess

# === Load static route GeoJSON once ===
gdf = gpd.read_file("data/routes.shp")
gdf.to_file("data/routes.geojson", driver="GeoJSON")
with open("data/routes.geojson") as f:
    route_geojson = json.load(f)

# === Dash app ===
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H2("BC Transit Victoria – Bus Tracker"),

    # Bus input
    html.Div([
        html.Label("Enter Bus Number:"),
        dcc.Input(
            id="bus-search",
            type="text",
            placeholder="e.g. 9542",
            value="9542",
            debounce=True
        )
    ], style={"margin-bottom": "10px"}),

    html.H3(id="bus-speed"),
    dcc.Graph(id="live-map"),

    # Manual update button
    html.Div([
        html.Button(
            "Update Now",
            id="manual-update",
            n_clicks=1,
            style={
                "padding": "10px 20px",
                "font-size": "16px",
                "background-color": "#007BFF",
                "color": "white",
                "border": "none",
                "border-radius": "5px",
                "cursor": "pointer"
            }
        )
    ], style={"margin-bottom": "20px"}),

    # Auto-refresh
    dcc.Interval(
        id="interval-component",
        interval=60*1000,  # 60 seconds
        n_intervals=0
    )
])

# === Helper functions ===
def load_buses():
    data_file = "data/buses.json"
    if not os.path.exists(data_file):
        return []
    try:
        with open(data_file) as f:
            return json.load(f)
    except Exception:
        return []

def generate_map(buses, bus_number):
    default_lat, default_lon = 48.4284, -123.3656  # Victoria, BC

    fig = go.Figure()

    # Draw routes
    for feature in route_geojson["features"]:
        if feature["geometry"]["type"] == "LineString":
            coords = feature["geometry"]["coordinates"]
            lons, lats = zip(*coords)
            fig.add_trace(go.Scattermapbox(
                lat=lats,
                lon=lons,
                mode="lines",
                line=dict(color="gray", width=2),
                hoverinfo="none"
            ))

    # Draw bus
    bus = next((b for b in buses if b["id"].endswith(bus_number)), None)
    if bus:
        lat, lon, speed, route, bus_id = (
            bus["lat"], bus["lon"], bus["speed"], bus["route"], bus["id"][6:]
        )
        fig.add_trace(go.Scattermapbox(
            lat=[lat],
            lon=[lon],
            mode="markers+text",
            marker=dict(size=12, color="red"),
            text=[f"{bus_id}"],
            textposition="top right",
            hoverinfo="text"
        ))
        center_lat, center_lon = lat, lon
        speed_text = (
            f"{bus_id} is running route {route} at {speed:.1f} km/h"
            if speed else f"{bus_id} is running route {route} and is currently stopped"
        )
    else:
        center_lat, center_lon = default_lat, default_lon
        speed_text = f"{bus_number} is not running at the moment"

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=12
        ),
        height=600,
        margin={"l":0,"r":0,"t":0,"b":0}
    )

    return fig, speed_text

# === Callbacks ===

# Auto-refresh
@app.callback(
    [Output("live-map", "figure"),
     Output("bus-speed", "children")],
    [Input("interval-component", "n_intervals"),
     Input("bus-search", "value")]
)
def update_map_interval(n, bus_number):
    buses = load_buses()
    return generate_map(buses, bus_number)

# Manual update
@app.callback(
    [Output("live-map", "figure"),
     Output("bus-speed", "children")],
    [Input("manual-update", "n_clicks"),
     Input("bus-search", "value")],
    prevent_initial_call=True
)
def manual_update(n_clicks, bus_number):
    try:
        # Run fetch_data.py on Render
        # subprocess.run(["python3", "fetch_data.py"], check=True)
        buses = load_buses()
        return generate_map(buses, bus_number)
    except Exception as e:
        fig = go.Figure()
        fig.update_layout(
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=48.4284, lon=-123.3656),
                zoom=12
            ),
            height=600,
            margin={"l":0,"r":0,"t":0,"b":0}
        )
        return fig, f"Error fetching live data: {e}"

if __name__ == "__main__":
    app.run(debug=True)

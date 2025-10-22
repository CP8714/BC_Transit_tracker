# Import necessary modules
import geopandas as gpd
import json
import dash
from dash import dcc, html
from dash.dependencies import Output, Input, State
import plotly.express as px
import os
import requests
import subprocess

# === Load static route data once ===
fp_routes = "data/routes.shp"   # adjust path if needed
route_data = gpd.read_file(fp_routes)
route_geojson = json.loads(route_data.to_json())

# === Dash app ===
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H2("BC Transit Victoria – Bus Tracker"),
    
    # Input for bus number
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

    # Manual update button
    html.Button("Update Now", id="manual-update", n_clicks=0, style={"margin-bottom": "10px"}),

    html.H3(id="bus-speed"),
    dcc.Graph(id="live-map"),

    # Auto-refresh interval
    dcc.Interval(
        id="interval-component",
        interval=60*1000,  # 60 seconds
        n_intervals=0
    )
])

def load_buses():
    """Load buses.json safely."""
    data_file = os.path.join("data", "buses.json")
    if not os.path.exists(data_file):
        return []
    with open(data_file, "r") as f:
        return json.load(f)

def generate_map(buses, bus_number):
    """Generate figure and speed text for a given bus_number."""
    bus = next((b for b in buses if b["id"].endswith(bus_number)), None)

    if not bus:
        fig = px.scatter_map(lat=[], lon=[], zoom=11, height=600)
        return fig, f"{bus_number} is not running at the moment"

    lat, lon, speed, route, bus_id = (
        bus["lat"], bus["lon"], bus["speed"], bus["route"], bus["id"][6:]
    )

    fig = px.scatter_map(
        lat=[lat], lon=[lon],
        text=[f"{bus_id}"],
        zoom=12, height=600
    )

    # Add static routes
    fig.update_layout(
        map_style="open-street-map",
        map_layers=[{
            "sourcetype": "geojson",
            "source": route_geojson,
            "type": "line",
            "color": "gray",
            "line": {"width": 2}
        }]
    )

    speed_text = (
        f"{bus_id} is running route {route} at {speed:.1f} km/h"
        if speed else f"{bus_id} is running route {route} and is currently stopped"
    )

    return fig, speed_text

# --- Callback for auto-refresh interval ---
@app.callback(
    [Output("live-map", "figure"),
     Output("bus-speed", "children")],
    [Input("interval-component", "n_intervals"),
     Input("bus-search", "value")]
)
def update_map_interval(n, bus_number):
    buses = load_buses()
    return generate_map(buses, bus_number)

# --- Callback for manual "Update Now" button ---
@app.callback(
    [Output("live-map", "figure"),
     Output("bus-speed", "children")],
    [Input("manual-update", "n_clicks"),
     Input("bus-search", "value")],
    prevent_initial_call=True
)
def manual_update(n_clicks, bus_number):
    try:
        # Run fetch_data.py to update buses.json live
        # subprocess.run(["python", "fetch_data.py"], check=True)
        # buses = load_buses()
        # return generate_map(buses, bus_number)
        return
    except Exception as e:
        fig = px.scatter_map(lat=[], lon=[], zoom=11, height=600)
        return fig, f"Error fetching live data: {e}"

if __name__ == "__main__":
    app.run(debug=True)

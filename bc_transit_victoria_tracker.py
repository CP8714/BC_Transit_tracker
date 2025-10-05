# Import necessary modules
import geopandas as gpd
import json
import dash
from dash import dcc, html
from dash.dependencies import Output, Input
import plotly.express as px
import os
import requests

# === GitHub data source ===
# Update this to your actual username/repo
DATA_URL = "https://github.com/CP8714/BC_Transit_tracker/blob/main/data/buses.json"

# === Load static route data once ===
fp_routes = "data/routes.shp"   # adjust path if needed
route_data = gpd.read_file(fp_routes)
route_geojson = json.loads(route_data.to_json())

# === Dash app ===
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H2("BC Transit Victoria – Bus Tracker"),
    html.Div([
        html.Label("Enter Bus Number:"),
        dcc.Input(
            id="bus-search",
            type="text",
            placeholder="e.g. 9542",
            value="9542",   # default
            debounce=True
        )
    ], style={"margin-bottom": "10px"}),
    html.H3(id="bus-speed"),
    dcc.Graph(id="live-map"),
    dcc.Interval(
        id="interval-component",
        interval=60*1000,  # refresh every 60 seconds (to match GitHub Actions)
        n_intervals=0
    )
])

@app.callback(
    [Output("live-map", "figure"),
     Output("bus-speed", "children")],
    [Input("interval-component", "n_intervals"),
     Input("bus-search", "value")]
)
def update_map(n, bus_number):
    # Fetch latest bus data from GitHub
    try:
        headers = {"Authorization": f"token {os.environ['GITHUB_TOKEN']}"}
        response = requests.get(DATA_URL, headers=headers, timeout=10)
        response.raise_for_status()
        buses = response.json()
    except Exception as e:
        fig = px.scatter_map(lat=[], lon=[], zoom=11, height=600)
        return fig, f"Error fetching data: {e}"

    # Filter for specific bus
    bus = next((b for b in buses if b["id"].endswith(bus_number)), None)

    if not bus:
        fig = px.scatter_map(lat=[], lon=[], zoom=11, height=600)
        return fig, f"{bus_number} is not running at the moment"

    lat, lon, speed, route, bus_id = (
        bus["lat"], bus["lon"], bus["speed"], bus["route"], bus["id"][6:]
    )

    # Plot bus location
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


if __name__ == "__main__":
    app.run(debug=True)


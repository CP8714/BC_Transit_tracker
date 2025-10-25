# Import necessary modules
import geopandas as gpd
import json
import dash
from dash import dcc, html
from dash.dependencies import Output, Input
# import plotly.express as px
import plotly.graph_objects as go
import math
import os
import requests
import pandas as pd
import fetch_fleet_data
import fetch_trip_data
from datetime import datetime
import pytz

# === GitHub data source fallback (optional) ===
bus_updates = "https://raw.githubusercontent.com/CP8714/BC_Transit_tracker/refs/heads/main/data/bus_updates.json"
trip_updates = "https://raw.githubusercontent.com/CP8714/BC_Transit_tracker/refs/heads/main/data/trip_updates.json"

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
            value="9542",
            debounce=True
        )
    ], style={"margin-bottom": "10px"}),

    # Manual update button
    html.Button("Update Now", id="manual-update", n_clicks=0, style={"margin-bottom": "10px"}),

    html.H3(id="desc-text"),

    html.H3(id="stop-text"),

    html.H3(id="capacity-text"),

    html.H3(id="speed-text"),
    
    dcc.Graph(id="live-map"),

    html.H3(id="timestamp-text"),

    # Auto-refresh interval
    dcc.Interval(
        id="interval-component",
        interval=60*1000,  # 60 seconds
        n_intervals=0
    )
])

# --- Helper functions ---
def load_buses():
    """Load latest bus_updates.json safely."""
    data_file = os.path.join("data", "bus_updates.json")
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            return json.load(f)
    # fallback to GitHub JSON if file missing
    try:
        response = requests.get(bus_updates, timeout=10)
        return response.json()
    except:
        return []

def load_current_trips():
    data_file = os.path.join("data", "trip_updates.json")
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            return json.load(f)
    try:
        response = requests.get(trip_updates, timeout=10)
        return response.json()
    except:
        return []

def load_trips():
    trips_file = os.path.join("data", "trips.csv")
    if os.path.exists(trips_file):
        trips_df = pd.read_csv(trips_file)
        return trips_df

def load_stops():
    stops_file = os.path.join("data", "stops.csv")
    if os.path.exists(stops_file):
        stops_df = pd.read_csv(stops_file)
        return stops_df

def generate_map(buses, bus_number, current_trips, trips_df, stops_df):
    """Generate figure and speed text for a given bus_number."""
    bus = next((b for b in buses if b["id"].endswith(bus_number)), None)

    if not bus:
        fig = go.Figure()
        return fig, f"{bus_number} is not running at the moment", "Next Stop: Not Available", "Occupancy Status: Not Available", "Current Speed: Not Available", ""

    lat, lon, speed, route, bus_id, capacity, trip_id, stop_id, bearing, timestamp = (
        bus["lat"], bus["lon"], bus["speed"], bus["route"], bus["id"][6:], bus["capacity"], bus["trip_id"], bus["stop_id"], bus["bearing"], bus["timestamp"]
    )
    current_trip = next((trip for trip in current_trips if trip["trip_id"] == trip_id), None)

    deadheading = False
    if not current_trip:
        deadheading = True
    else:
        delay, stop_sequence, start_time = (
            current_trip["delay"], current_trip["stop_sequence"], current_trip["start_time"]
        )
        delay = delay // 60
    
    # stop_id in stops_df is a float so stop_id from buses must be converted to a float 
    stop_id = float(stop_id)
    route_number = route.split('-')[0] 
    trip_headsign = trips_df.loc[trips_df["trip_id"] == trip_id, "trip_headsign"]
    speed = speed * 3
    stop = stops_df.loc[stops_df["stop_id"] == stop_id, "stop_name"]

    

    # bearing_rad = math.radians(bearing)
    # arrow_len = 0.002  # adjust for zoom

    # end_lat = lat + arrow_len * math.cos(bearing_rad)
    # end_lon = lon + arrow_len * math.sin(bearing_rad)

    fig = go.Figure()

    # Bus location as marker
    fig.add_trace(go.Scattermapbox(
        lat=[lat],
        lon=[lon],
        mode="markers+text",
        text=[bus_id],
        textposition="top center",
        marker=dict(size=12, color="blue"),
        name="Bus Position"
    ))

    # Arrow showing heading
    # fig.add_trace(go.Scattermapbox(
    #    lat=[lat, end_lat],
    #    lon=[lon, end_lon],
    #    mode="lines",
    #    line=dict(width=4, color="red"),
    #    name="Heading"
    #))

    fp_routes = os.path.join("data", "routes.shp")
    route_data = gpd.read_file(fp_routes)
    # Route map not shown for buses heading back to yard
    if trip_headsign.empty:
        route = "0"
    current_route = route_data[route_data["route_id"] == route]
    route_geojson = json.loads(current_route.to_json())

    # Add route on map
    fig.update_layout(
        mapbox = dict(
            style="open-street-map",
            center={"lat": lat, "lon": lon},
            zoom=12,
            layers=[
                dict(
                    sourcetype="geojson",
                    source=route_geojson,
                    type="line",
                    line = dict(width=4)
                )
            ]
        ),
        height=600,
        margin={"r":0,"t":0,"l":0,"b":0}
    )
    stop = stop.iloc[0]
    if deadheading:
        if stop_id == 900000 or stop_id == 930000:
            desc_text = f"{bus_id} is currently returning back to a transit yard"
            stop_text = f"Next Stop: {stop}"
        else:
            desc_text = f"{bus_id} is currently deadheading to run another route"
            stop_text = f"First Stop: {stop}"
    else:
        trip_headsign = trip_headsign.iloc[0]
        if delay == 0:
            desc_text = f"{bus_id} is currently on schedule running the {route_number} {trip_headsign}"
        elif delay < 0:
            delay = delay * -1
            if delay == 1:
                desc_text = f"{bus_id} is currently {delay:d} minute early running the {route_number} {trip_headsign}"
            else:
                desc_text = f"{bus_id} is currently {delay:d} minutes early running the {route_number} {trip_headsign}"
        else:
            if delay == 1:
                desc_text = f"{bus_id} is currently {delay:d} minute late running the {route_number} {trip_headsign}"
            else:
                desc_text = f"{bus_id} is currently {delay:d} minutes late running the {route_number} {trip_headsign}"

        
        if speed > 0:
            stop_text = f"Next Stop: {stop}"
        else:
            stop_text = f"Current Stop: {stop}"

    speed_text = (
        f"Current Speed: {speed:.1f} km/h"
        if speed else f"Current Speed: 0 km/h"
    )
    
    if capacity == 0:
        capacity_text = "Occupancy Status: Empty"
    elif capacity == 1:
        capacity_text = "Occupancy Status: Many Seats Available"
    elif capacity == 2:
        capacity_text = "Occupancy Status: Some Seats Available"
    elif capacity == 3:
        capacity_text = "Occupancy Status: Standing Room Only"
    else:
        capacity_text = "Occupancy Status: Full"

    # Parse timestamp as UTC time
    utc_time = datetime.fromisoformat(timestamp).replace(tzinfo=pytz.utc)

    # Convert to PST 
    pst_time = utc_time.astimezone(pytz.timezone("America/Los_Angeles"))

    pst_timestamp = pst_time.strftime("%H:%M:%S")

    timestamp_text = f"Updated at {pst_timestamp}"

    return fig, desc_text, stop_text, capacity_text, speed_text, timestamp_text

# --- Unified callback ---
from dash import callback_context

@app.callback(
    [Output("live-map", "figure"),
     Output("desc-text", "children"),
     Output("stop-text", "children"),
     Output("capacity-text", "children"),
     Output("speed-text", "children"),
     Output("timestamp-text", "children")],
    [Input("interval-component", "n_intervals"),
     Input("manual-update", "n_clicks"),
     Input("bus-search", "value")]
)
def update_map_callback(n_intervals, n_clicks, bus_number):
    triggered_id = callback_context.triggered_id

    # Manual button triggers a live fetch
    if triggered_id == "manual-update":
        try:
            fetch_fleet_data.fetch()
            fetch_trip_data.fetch()
        except Exception as e:
            print(f"Error fetching live fleet data: {e}", flush=True)

    # Load the latest bus data
    buses = load_buses()
    current_trips = load_current_trips()
    trips_df = load_trips()
    stops_df = load_stops()
    return generate_map(buses, bus_number, current_trips, trips_df, stops_df)

# === Run app ===
if __name__ == "__main__":
    app.run(debug=True)

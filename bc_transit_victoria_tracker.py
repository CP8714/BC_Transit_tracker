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

    html.Button(id="toggle-future-stops", n_clicks=0, children="Show Next 5 Stops", style={"margin-bottom": "10px"}),

    html.H3(id="future-stop-text"),
    
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

def load_stop_times(current_trip_id):
    stop_times_file = os.path.join("data", "stop_times.csv")
    if os.path.exists(stop_times_file):
        stop_times_df = pd.DataFrame()
        stop_times_chunks = pd.read_csv(stop_times_file, chunksize=10000)
        for stop_times_chunk in stop_times_chunks:
            current_trip_stops = stop_times_chunk[stop_times_chunk["trip_id"] == current_trip_id]
            if not current_trip_stops.empty:
                stop_times_df = pd.concat([stop_times_df, current_trip_stops], ignore_index=True)
        return stop_times_df

def generate_map(buses, bus_number, current_trips, trips_df, stops_df, toggle_future_stops_clicks):
    """Generate figure and speed text for a given bus_number."""
    fig = go.Figure()
    toggle_future_stops_text = "Show Next 5 Stops"
    bus = next((b for b in buses if b["id"].endswith(bus_number)), None)

    if toggle_future_stops_clicks % 2 == 1:
        toggle_future_stops_text = "Show All Next Stops"
    else:
        toggle_future_stops_text = "Show Next 5 Stops"
        

    if not bus:
        fig = go.Figure()
        return fig, f"{bus_number} is not running at the moment", "Next Stop: Not Available", "Occupancy Status: Not Available", "Current Speed: Not Available", "", [], toggle_future_stops_text

    lat, lon, speed, route, bus_id, capacity, trip_id, stop_id, bearing, timestamp = (
        bus["lat"], bus["lon"], bus["speed"], bus["route"], bus["id"][6:], bus["capacity"], bus["trip_id"], bus["stop_id"], bus["bearing"], bus["timestamp"]
    )
    current_trip = [trip for trip in current_trips if trip["trip_id"] == trip_id]
    current_stop = next((stop for stop in current_trip if stop["stop_id"] == stop_id), None)
    future_stops_eta = []

    deadheading = False
    if not current_trip:
        deadheading = True
    else:

        # Get lon and lat coordinates for all stops on current route to be displayed on map
        stop_times_df = load_stop_times(trip_id)
        current_trip_stop_ids = stop_times_df["stop_id"].astype(float).tolist()
        current_trip_stops_df = stops_df[stops_df["stop_id"].isin(current_trip_stop_ids)]
        
        delay, stop_sequence, start_time, eta_time, current_stop_id = (
            current_stop["delay"], current_stop["stop_sequence"], current_stop["start_time"], current_stop["time"], current_stop["stop_id"]
        )
        delay = delay // 60
        # Converting from Unix to PST
        eta_time = datetime.fromtimestamp(eta_time, pytz.timezone("America/Los_Angeles"))
        eta_time = eta_time.strftime("%H:%M")

        future_stops = [stop for stop in current_trip if stop["stop_sequence"] > current_stop["stop_sequence"]]
        if future_stops:
            all_future_stops_eta = []
            all_future_stops_eta.append("Next Stop ETAs")
            for stop in future_stops:
                future_eta_time = datetime.fromtimestamp(stop["time"], pytz.timezone("America/Los_Angeles"))
                future_eta_time = future_eta_time.strftime("%H:%M")
                future_stop_id = float(stop["stop_id"])
                future_stop_name = stops_df.loc[stops_df["stop_id"] == future_stop_id, "stop_name"]
                future_stop_name = future_stop_name.iloc[0]
                future_stops_text = f"{future_stop_name}: {future_eta_time}"
                all_future_stops_eta.append(future_stops_text)
            # Only include the next 5 stops depending on if the "Show Next 5 stops" button has been clicked
            if toggle_future_stops_clicks % 2 == 1 and len(future_stops) >= 5:
                future_stops_eta = all_future_stops_eta[:6]
            else:
                future_stops_eta = all_future_stops_eta
            future_stops_eta = [html.Div(text) for text in future_stops_eta]
        
        
    
    # stop_id in stops_df is a float so stop_id from buses must be converted to a float 
    stop_id = float(stop_id)
    route_number = route.split('-')[0] 
    trip_headsign = trips_df.loc[trips_df["trip_id"] == trip_id, "trip_headsign"]
    speed = speed * 3
    stop = stops_df.loc[stops_df["stop_id"] == stop_id, "stop_name"]

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
            zoom=14,
            layers=[
                dict(
                    sourcetype="geojson",
                    source=route_geojson,
                    type="line",
                    line = dict(width=2)
                )
            ]
        ),
        height=600,
        margin={"r":0,"t":0,"l":0,"b":0}
    )

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

    # Possible future arrow
    # bearing_rad = math.radians(bearing)
    # arrow_len = 0.002  # adjust for zoom

    # end_lat = lat + arrow_len * math.cos(bearing_rad)
    # end_lon = lon + arrow_len * math.sin(bearing_rad)

    # Arrow showing heading
    # fig.add_trace(go.Scattermapbox(
    #    lat=[lat, end_lat],
    #    lon=[lon, end_lon],
    #    mode="lines",
    #    line=dict(width=4, color="red"),
    #    name="Heading"
    #))

    if not deadheading:
        # Add stops of current route to map
        fig.add_trace(go.Scattermapbox(
            lat=current_trip_stops_df["stop_lat"],
            lon=current_trip_stops_df["stop_lon"],
            mode="markers+text",
            marker=dict(size=10, color="red"),
            line=dict(width=2,color='white'))
            text=trip_stops_df["stop_name"],
            textposition="top center",
            name="Route Stops"
        ))

    
    stop = stop.iloc[0]
    if deadheading:
        if stop_id == 900000 or stop_id == 930000:
            desc_text = f"{bus_id} is currently returning back to a transit yard"
            stop_text = f"Next Stop: {stop}"
        else:
            desc_text = f"{bus_id} is currently deadheading to run another route"
            stop_text = f"First Stop: {stop}"
    else:
        # Remove seconds from start_time
        start_time = start_time[:5]
        trip_headsign = trip_headsign.iloc[0]
        if delay == 0:
            if stop_sequence == 1:
                desc_text = f"{bus_id} will be running the {route_number} {trip_headsign} departing at {start_time}"
            else:
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
            stop_text = f"Next Stop: {stop} (ETA: {eta_time})"
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

    return fig, desc_text, stop_text, capacity_text, speed_text, timestamp_text, future_stops_eta, toggle_future_stops_text

# --- Unified callback ---
from dash import callback_context

@app.callback(
    [Output("live-map", "figure"),
     Output("desc-text", "children"),
     Output("stop-text", "children"),
     Output("capacity-text", "children"),
     Output("speed-text", "children"),
     Output("timestamp-text", "children"),
     Output("future-stop-text", "children"),
     Output("toggle-future-stops", "children")],
    [Input("interval-component", "n_intervals"),
     Input("manual-update", "n_clicks"),
     Input("bus-search", "value"),
     Input("toggle-future-stops", "n_clicks")]
)
def update_map_callback(n_intervals, manual_update, bus_number, toggle_future_stops_clicks):
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
    return generate_map(buses, bus_number, current_trips, trips_df, stops_df, toggle_future_stops_clicks)

# === Run app ===
if __name__ == "__main__":
    app.run(debug=True)

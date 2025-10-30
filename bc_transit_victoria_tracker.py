# Import necessary modules
import geopandas as gpd
import json
import dash
from dash import html, dcc, register_page, callback
from dash.dependencies import Output, Input, State
import plotly.graph_objects as go
import math
import os
import requests
import pandas as pd
import fetch_fleet_data
import fetch_trip_data
from datetime import datetime
from dash import callback_context
import pytz

# BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# DATA_DIR = os.path.join(BASE_DIR, "data")

# === GitHub data source fallback (optional) ===
bus_updates = "https://raw.githubusercontent.com/CP8714/BC_Transit_tracker/refs/heads/main/data/bus_updates.json"
trip_updates = "https://raw.githubusercontent.com/CP8714/BC_Transit_tracker/refs/heads/main/data/trip_updates.json"

app = dash.Dash(__name__)

bus_tracker_layout = html.Div([
    html.H2("BC Transit Victoria – Bus Tracker"),

    html.Div([
        html.Label("Enter Bus Number:"),
        dcc.Input(
            id="bus-search-user-input",
            type="text",
            placeholder="enter bus number e.g. 9542",
            value="9542",
            debounce=True
        ),
        html.Button("Search", id="search-for-bus", n_clicks=0),
    ], style={"margin-bottom": "10px"}),

    # Manual update button
    html.Button("Update Now", id="manual-update", n_clicks=0, style={"margin-bottom": "10px"}),

    html.Div([
        dcc.Loading(
            id="loading-component",
            type="circle",
            children=[
                html.H3(id="desc-text"),
                html.H3(id="stop-text"),
                html.H3(id="capacity-text"),
                html.H3(id="speed-text"),
                html.Button(id="toggle-future-stops", n_clicks=0, children="Show All Upcoming Stops", style={"margin-bottom": "10px"}),
                html.H3(id="future-stop-text"),
                dcc.Graph(id="live-map"),
                html.H3(id="timestamp-text"),
                dcc.Link("Go to Next Buses →", href="/next_buses"),
            ]
        )
    ]),

    # Auto-refresh interval
    dcc.Interval(
        id="interval-component",
        interval=100*10000,  # 60 seconds
        n_intervals=0
    ),
    
])

next_buses_layout = html.Div([
    html.H1("Next Buses Page"),
    html.Div([
        html.Label("Enter Bus Stop Number:"),
        dcc.Input(
            id="stop-search-user-input",
            type="text",
            placeholder="enter stop bus number e.g. 100032",
            value="100032",
            debounce=True
        ),
        html.Button("Search", id="look-up-next-buses", n_clicks=0),
    ], style={"margin-bottom": "10px"}),

    # Manual update button
    html.Button("Update Now", id="stop-manual-update", n_clicks=0, style={"margin-bottom": "10px"}),

    html.Div([
        dcc.Loading(
            id="loading-component",
            type="circle",
            children=[
                html.H3(id="stop-name-text"),
                html.H3(id="stop-desc-text"),
                dcc.Link("← Back to Bus Tracker", href="/"),
            ]
        )
    ]),

    # Auto-refresh interval
    dcc.Interval(
        id="stop-interval-component",
        interval=100*10000,  # 60 seconds
        n_intervals=0
    ),
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

def get_capacity(capacity):
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
    return capacity_text

def load_scheduled_bus_times(current_stop_id):
    bus_times_file = os.path.join("data", "stop_times.csv")
    if os.path.exists(bus_times_file):
        bus_times_df = pd.DataFrame()
        bus_times_chunks = pd.read_csv(bus_times_file, chunksize=10000)
        for bus_times_chunk in bus_times_chunks:
            next_buses = bus_times_chunk[bus_times_chunk["stop_id"] == current_stop_id]
            if not next_buses.empty:
                bus_times_df = pd.concat([bus_times_df, next_buses], ignore_index=True)
        return bus_times_df

def get_next_buses(stop_number, stops_df, trips_df, current_trips, buses):
    next_buses = []
    if not stop_number:
        return "No Stop Number Entered", next_buses
    stop_number = int(stop_number)
    stop = stops_df.loc[stops_df["stop_id"] == stop_number, "stop_name"]
    if stop.empty:
        return f"{stop_number} is not a valid Stop Number", next_buses
    stop_name = stop.iloc[0]
    stop_name_text = f"Next Buses For Stop {stop_number:d} ({stop_name})"

    
    scheduled_next_bus_times_df = load_scheduled_bus_times(stop_number)
    # Account for times past midnight such as 25:00:00
    scheduled_next_bus_times_df["arrival_time"] = pd.to_timedelta(scheduled_next_bus_times_df["arrival_time"])
    scheduled_next_bus_times_df = scheduled_next_bus_times_df.sort_values("arrival_time")

    # current_time = datetime.now(pytz.timezone("America/Los_Angeles"))
    # current_time = current_time.time()
    # current_time = pd.to_timedelta(f"{current_time.hour:02d}:{current_time.minute:02d}:{current_time.second:02d}")
    
    # scheduled_next_bus_times_df = scheduled_next_bus_times_df[scheduled_next_bus_times_df["arrival_time"] >= current_time]

    stop_number = str(stop_number)
    current_time = int(datetime.now().timestamp())
    next_trip = [stop for stop in current_trips if stop["stop_id"] == stop_number]
    next_trip = [stop for stop in next_trip if stop["time"] >= current_time]
    # Sort by arrival time 
    next_trip = sorted(next_trip, key=lambda x: x["time"])
    next_trip = next_trip[:10]

    next_buses.append("Next Buses")
    for bus in next_trip:
        current_bus = next((b for b in buses if b["trip_id"] == bus["trip_id"]), None)
        if not current_bus:
            bus_number = "Unknown"
        else:
            bus_number = current_bus["id"]
            bus_number = bus_number[-4:]
        next_bus = trips_df[trips_df["trip_id"] == bus["trip_id"]].iloc[0]
        route = bus["route_id"]
        route_number = route.split('-')[0] 
        headsign = next_bus["trip_headsign"]
        arrival_time = datetime.fromtimestamp(bus["time"], pytz.timezone("America/Los_Angeles"))
        arrival_time = arrival_time.strftime("%H:%M")
        next_bus_text = f"{arrival_time} {route_number} {headsign} (Run by {bus_number})"
        next_buses.append(next_bus_text)     
    next_buses = [html.Div(text) for text in next_buses]
        
        

    # scheduled_next_bus_times_df = scheduled_next_bus_times_df.head(10)
    # next_buses.append("Next Scheduled Buses")
    # for _, bus in scheduled_next_bus_times_df.iterrows():
    #     next_bus = trips_df[trips_df["trip_id"] == bus["trip_id"]].iloc[0]
    #     route = next_bus["route_id"]
    #     route_number = route.split('-')[0] 
    #     headsign = next_bus["trip_headsign"]
    #     arrival_time = str(bus["arrival_time"]).split(" days ")[-1]
    #     next_bus_text = f"{arrival_time} {route_number} {headsign}"
    #     next_buses.append(next_bus_text)
    # next_buses = [html.Div(text) for text in next_buses]
        
    
    
    return stop_name_text, next_buses
    

def generate_map(buses, bus_number, current_trips, trips_df, stops_df, toggle_future_stops_clicks):
    """Generate figure and speed text for a given bus_number."""
    fig = go.Figure()
    toggle_future_stops_text = "Show All Upcoming Stops"
    bus = next((b for b in buses if b["id"].endswith(bus_number)), None)

    if toggle_future_stops_clicks % 2 == 0:
        toggle_future_stops_text = "Show All Upcoming Stops"
    else:
        toggle_future_stops_text = "Show Next 5 Stops"
        
    if not bus:
        return fig, f"{bus_number} is not running at the moment", "Next Stop: Not Available", "Occupancy Status: Not Available", "Current Speed: Not Available", "", [], toggle_future_stops_text

    lat, lon, speed, route, bus_id, capacity, trip_id, stop_id, bearing, timestamp = (
        bus["lat"], bus["lon"], bus["speed"], bus["route"], bus["id"][6:], bus["capacity"], bus["trip_id"], bus["stop_id"], bus["bearing"], bus["timestamp"]
    )
    current_trip = [trip for trip in current_trips if trip["trip_id"] == trip_id]
    current_stop = next((stop for stop in current_trip if stop["stop_id"] == stop_id), None)
    future_stops_eta = []

    capacity_text = get_capacity(capacity)

    # Parse timestamp as UTC time
    utc_time = datetime.fromisoformat(timestamp).replace(tzinfo=pytz.utc)
    
    # Convert to PST 
    pst_time = utc_time.astimezone(pytz.timezone("America/Los_Angeles"))
    pst_timestamp = pst_time.strftime("%H:%M:%S")
    timestamp_text = f"Updated at {pst_timestamp}"
    
    speed_text = (
        f"Current Speed: {speed:.1f} km/h"
        if speed else f"Current Speed: 0 km/h"
    )

    deadheading = False
    if not current_trip:
        deadheading = True
    else:

        # Get lon and lat coordinates for all stops on current route to be displayed on map
        stop_times_df = load_stop_times(trip_id)
        current_trip_stop_ids = stop_times_df["stop_id"].astype(float).tolist()
        current_trip_stops_df = stops_df[stops_df["stop_id"].isin(current_trip_stop_ids)]

        capacity_text = get_capacity(capacity)

        if not current_stop:
            # Add route on map
            fig.update_layout(
                mapbox = dict(
                    style="open-street-map",
                    center={"lat": lat, "lon": lon},
                    zoom=14
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
                hovertext=[bus_id],
                hoverinfo="text",
                name=f"Position of {bus_id}"
            ))
            return fig, f"{bus_number} is currently Not In Service", "Next Stop: Not Available", capacity_text, speed_text, timestamp_text, [], toggle_future_stops_text
            
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
            if toggle_future_stops_clicks % 2 == 0 and len(future_stops) >= 5:
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
                    line = dict(width=2),
                    below='traces'
                )
            ]
        ),
        height=600,
        margin={"r":0,"t":0,"l":0,"b":0}
    )

    if not deadheading:
        # Add stops of current route to map
        fig.add_trace(go.Scattermapbox(
            lat=current_trip_stops_df["stop_lat"],
            lon=current_trip_stops_df["stop_lon"],
            mode="markers",
            marker=dict(size=10, color="red"),
            hovertext=current_trip_stops_df["stop_name"],
            hoverinfo="text",
            name="Bus Stops"
        ))

    # Bus location as marker
    fig.add_trace(go.Scattermapbox(
        lat=[lat],
        lon=[lon],
        mode="markers+text",
        text=[bus_id],
        textposition="top center",
        marker=dict(size=12, color="blue"),
        hovertext=[bus_id],
        hoverinfo="text",
        name=f"Position of {bus_id}"
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


    return fig, desc_text, stop_text, capacity_text, speed_text, timestamp_text, future_stops_eta, toggle_future_stops_text

# --- App layout with a container that will be swapped ---
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(id="page-content")
])


# --- Callback to swap layouts based on URL ---
@callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    if pathname == "/next_buses":
        return next_buses_layout
    else:
        return bus_tracker_layout

@callback(
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
     Input("search-for-bus", "n_clicks"),
     Input("toggle-future-stops", "n_clicks")],
    [State("bus-search-user-input", "value")]
)
def update_map_callback(n_intervals, manual_update, search_for_bus, toggle_future_stops_clicks, bus_number):
    triggered_id = callback_context.triggered_id

    # Manual button triggers a live fetch
    if triggered_id == "manual-update" or triggered_id == "search-for-bus":
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

@callback(
    [Output("stop-name-text", "children"),
     Output("stop-desc-text", "children")],
    [Input("stop-interval-component", "n_intervals"),
     Input("stop-manual-update", "n_clicks"),
     Input("look-up-next-buses", "n_clicks")],
    [State("stop-search-user-input", "value")]
)
def update_stop_callback(n_intervals, manual_update, look_up_next_buses, stop_number):
    triggered_id = callback_context.triggered_id

    # Manual button triggers a live fetch
    if triggered_id == "manual-update" or triggered_id == "look-up-next-buses":
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
    return get_next_buses(stop_number, stops_df, trips_df, current_trips, buses)


if __name__ == "__main__":
    app.run(debug=True)

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
from urllib.parse import parse_qs, urlparse, urlencode

# === GitHub data source fallback (optional) ===
bus_updates = "https://raw.githubusercontent.com/CP8714/BC_Transit_tracker/refs/heads/main/data/bus_updates.json"
trip_updates = "https://raw.githubusercontent.com/CP8714/BC_Transit_tracker/refs/heads/main/data/trip_updates.json"

app = dash.Dash(__name__)

home_layout = html.Div([
    html.H2("BC Transit Victoria – Bus Tracker"),

    html.Div([
        html.Label("Enter Bus Number:"),
        dcc.Input(
            id="bus-search-home",
            type="text",
            placeholder="enter bus number e.g. 9542",
            value="9542",
            debounce=True
        ),
        html.Button("Search", id="search-for-bus-home", n_clicks=0),
    ], style={"margin-bottom": "10px"}),

    html.Div([
        html.Label("Enter Stop Number:"),
        dcc.Input(
            id="stop-search-home",
            type="text",
            placeholder="enter stop bus number e.g. 100032",
            value="100032",
            debounce=True
        ),
        html.Button("Search", id="search-for-stop-home", n_clicks=0),
    ], style={"margin-bottom": "10px"})
    
])

bus_tracker_layout = html.Div([
    html.H2("Bus Tracker"),

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
                html.H3(id="block-trips"),
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
            debounce=True,
            style={"width": "250px"}
        ),
        html.Button("Search", id="look-up-next-buses", n_clicks=0),
    ], style={"margin-bottom": "10px"}),

    html.Div([
        html.Label("Enter Route Stop Number:"),
        dcc.Input(
            id="route-search-user-input",
            type="text",
            placeholder="(Optional) enter route number e.g. 95",
            value="",
            debounce=True,
            style={"width": "250px"}
        ),
        html.Button("Search", id="look-up-next-buses-route", n_clicks=0),
    ], style={"margin-bottom": "10px"}),

    # Manual update button
    html.Button("Update Now", id="stop-manual-update", n_clicks=0, style={"margin-bottom": "10px"}),

    html.Div([
        dcc.Loading(
            id="loading-component",
            type="circle",
            children=[
                html.Button(id="toggle-future-buses", n_clicks=0, children="Show Next 20 Buses", style={"margin-bottom": "10px"}),
                html.Div(id="next-buses-output"),
                dcc.Link("← GO to Bus Tracker", href="/bus_tracker"),
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
# Returns dictionary of bus_updates.json, the realtime update file for buses
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

# Returns dictionary of trip_updates.json, the realtime update file for trips
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

# Returns dataframe of trips.csv
def load_trips():
    trips_file = os.path.join("data", "trips.csv")
    if os.path.exists(trips_file):
        trips_df = pd.read_csv(trips_file)
        return trips_df

# Returns dataframe of stops.csv
def load_stops():
    stops_file = os.path.join("data", "stops.csv")
    if os.path.exists(stops_file):
        stops_df = pd.read_csv(stops_file)
        return stops_df

# Finds all the stops that are served by at current_trip_id and returns a dataframe containing them along with all other info from stop_times.csv
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

# Returns appropriate text for bus capacity depending on the capacity input value
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

# Finds all the trips that stop at current_stop_id and returns a dataframe containing them along with all other info from stop_times.csv
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

# Finds the initial trip departure time from stop_times.csv for all the trips in trips_ids and returns a dataframe containing them
def load_block_departure_times(trip_ids):
    stop_times_file = os.path.join("data", "stop_times.csv")
    departure_times_list = []
    if os.path.exists(stop_times_file):
        departure_times_chunks = pd.read_csv(stop_times_file, chunksize=10000, usecols=["trip_id", "stop_sequence", "departure_time"])
        for departure_times_chunk in departure_times_chunks:
            departure_times = departure_times_chunk[departure_times_chunk["trip_id"].isin(trip_ids) & (departure_times_chunk["stop_sequence"] == 1)]
            if not departure_times.empty:
                departure_times_list.append(departure_times)
        if departure_times_list:
            return pd.concat(departure_times_list, ignore_index=True)
    return pd.DataFrame(columns=["trip_id", "stop_sequence", "departure_time"])


def make_next_buses_table(next_buses):
    return html.Table([
        html.Thead(html.Tr([
            html.Th("Estimated Arrival Time", style={"border": "1px solid black"}),
            html.Th("Trip Headsign", style={"border": "1px solid black"}),
            html.Th("Assigned Bus", style={"border": "1px solid black"}),
        ])),
        html.Tbody([
            html.Tr([
                html.Td(bus["arrival_time"], style={"border": "1px solid black", "textAlign": "center"}),
                html.Td(bus["trip_headsign"], style={"border": "1px solid black", "textAlign": "center"}),
                html.Td(
                    html.A(bus["bus"], href=f"/bus_tracker?bus={bus['bus']}", style={"textDecoration": "none", "color": "blue"})
                    if bus["bus"] != "Unknown" else bus["bus"],
                    style={"border": "1px solid black", "textAlign": "center"}
                )
            ])
            for bus in next_buses
        ])
    ],
    style={"borderCollapse": "collapse", "border": "1px solid black", "width": "100%", "marginTop": "10px"}
    )

def get_next_buses(stop_number_input, route_number_input, stops_df, trips_df, current_trips, buses, toggle_future_buses_clicks):
    next_buses = []
    if not stop_number_input:
        return html.Div("No Stop Number Entered")
    stop_number_input = int(stop_number_input)
    stop = stops_df.loc[stops_df["stop_id"] == stop_number_input, "stop_name"]
    if stop.empty:
        return html.Div(f"{stop_number_input} is not a valid Stop Number")
    stop_name = stop.iloc[0]
    stop_name_text = f"Next Estimated Arrivals At Stop {stop_number_input:d} ({stop_name})"

    stop_number_input = str(stop_number_input)
    current_time = int(datetime.now().timestamp())

    # current_time_test = pytz.timezone("America/Los_Angeles")
    # current_time_test = datetime.now(current_time_test).strftime("%H:%M:%S")
    # # today = pd.Timestamp(datetime.now(pst).date(), tz=pst)
    
    # scheduled_next_bus_times_df = load_scheduled_bus_times(float(stop_number_input))
    # # Account for times past midnight such as 25:00:00
    # scheduled_next_bus_times_df = scheduled_next_bus_times_df.sort_values("arrival_time")
    # scheduled_next_bus_times_df = scheduled_next_bus_times_df[scheduled_next_bus_times_df["arrival_time"] >= current_time_test]

    # scheduled_next_bus_times_df = scheduled_next_bus_times_df.head(20)
    # next_buses_test = []
    # next_trips = []
    # next_buses_test.append("Next Scheduled Buses")
    # for _, bus_test in scheduled_next_bus_times_df.iterrows():
    #     next_bus = trips_df[trips_df["trip_id"] == bus_test["trip_id"]].iloc[0]
    #     route = next_bus["route_id"]
    #     route_number = route.split('-')[0] 
    #     headsign = next_bus["trip_headsign"]
    #     # arrival_time = str(bus_test["arrival_time"]).split(" days ")[-1]
    #     # arrival_time = bus_test["arrival_time"].strftime("%H:%M")
    #     arrival_time = bus_test["arrival_time"]
    #     arrival_time = arrival_time[:-3]
    #     first_number, second_number, _ = bus_test["trip_id"].split(":")
    #     already_added_trip = any(i.split(":")[0] == first_number and i.split(":")[1] == second_number for i in next_trips)
    #     if not next_trips:
    #         next_bus_text_test = f"{arrival_time} {route_number} {headsign}"
    #         next_trips.append(bus_test["trip_id"])
    #         next_buses_test.append(next_bus_text_test)
    #     elif not already_added_trip:
    #         next_bus_text_test = f"{arrival_time} {route_number} {headsign} {first_number} {second_number} {bus_test["trip_id"]}"
    #         next_trips.append(bus_test["trip_id"])
    #         next_buses_test.append(next_bus_text_test)
            
    # next_buses_test = [html.Div(text) for text in next_buses_test]


    
    

    next_trip = [stop for stop in current_trips if stop["stop_id"] == stop_number_input]
    next_trip = [stop for stop in next_trip if stop["time"] >= current_time]
    if route_number_input:
        route_number_input = str(route_number_input)
        route_number_input = route_number_input + "-VIC"
        next_trip = [stop for stop in next_trip if stop["route_id"] == route_number_input]
        route_number_input = route_number_input.split('-')[0] 
        stop_name_text = f"Next Estimated Arrivals For Route {route_number_input} At Stop {stop_number_input} ({stop_name})"
        
    # Sort by arrival time 
    next_trip = sorted(next_trip, key=lambda x: x["time"])
    if toggle_future_buses_clicks % 2 == 0:
        next_trip = next_trip[:10]
    else:
        next_trip = next_trip[:20]
    
    for bus in next_trip:
        current_bus = next((b for b in buses if b["trip_id"] == bus["trip_id"]), None)
        if not current_bus:
            current_trip = trips_df[trips_df["trip_id"] == bus["trip_id"]].iloc[0]
            block = current_trip["block_id"]
            full_block = trips_df[trips_df["block_id"] == block]
            bus_number = "Unknown"
            for _, row in full_block.iterrows():
                current_bus = next((b for b in buses if b["trip_id"] == row["trip_id"]), None)
                if current_bus:
                    bus_number = current_bus["id"]
                    bus_number = bus_number[-4:]
                    break
        else:
            bus_number = current_bus["id"]
            bus_number = bus_number[-4:]
        next_bus = trips_df[trips_df["trip_id"] == bus["trip_id"]].iloc[0]
        route = bus["route_id"]
        route_number = route.split('-')[0] 
        headsign = next_bus["trip_headsign"]
        arrival_time = datetime.fromtimestamp(bus["time"], pytz.timezone("America/Los_Angeles"))
        arrival_time = arrival_time.strftime("%H:%M")
        next_buses.append({
            "arrival_time": arrival_time,
            "trip_headsign": f"{route_number} {headsign}",
            "bus": f"{bus_number}"
        })    
    
    return html.Div([
        html.H3(stop_name_text),
        make_next_buses_table(next_buses)
    ])
    

def get_bus_info(buses, bus_number, current_trips, trips_df, stops_df, toggle_future_stops_clicks):
    """Generate figure and speed text for a given bus_number."""
    fig = go.Figure()
    toggle_future_stops_text = "Show All Upcoming Stops"
    bus = next((b for b in buses if b["id"].endswith(bus_number)), None)

    if toggle_future_stops_clicks % 2 == 0:
        toggle_future_stops_text = "Show All Upcoming Stops"
    else:
        toggle_future_stops_text = "Show Next 5 Stops"
        
    if not bus:
        return fig, f"{bus_number} is not running at the moment", "Next Stop: Not Available", "Occupancy Status: Not Available", "Current Speed: Not Available", "", [], toggle_future_stops_text, ""

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
        block_trips = []
        block = trip_id.split(":")[2]
        full_block = trips_df[trips_df["block_id"].astype(str) == block]
        block_trips.append(f"{bus_number} will be running the following trips today:")

        # Load all stop times for all trips in the block
        stop_times_df = load_block_departure_times(full_block["trip_id"].tolist())

        full_block = full_block.merge(stop_times_df, on="trip_id", how="left")
        # Allow departure_time to exceed 24:00:00 ie 25:00:00
        full_block["departure_time"] = pd.to_timedelta(full_block["departure_time"])
        full_block = full_block.sort_values(by="departure_time")
        # Only keep hours and minutes
        full_block["departure_time"] = full_block["departure_time"].apply(
            lambda t: f"{int(t.total_seconds() // 3600):02d}:{int((t.total_seconds() % 3600) // 60):02d}"
        )
        
        for _, row in full_block.iterrows():
            # stop_times_df = load_stop_times(row["trip_id"])
            # stop_times_df = stop_times_df[stop_times_df["stop_sequence"] == 1]
            # departure_time = stop_times_df["departure_time"]
            departure_time = row["departure_time"]
            route_number = row["route_id"].split("-")[0]
            headsign = row["trip_headsign"]

            block_trip_text = f"{route_number} {headsign} leaving at {departure_time}"
            # block_trip_text = f"{route_number} {headsign}"
            block_trips.append(block_trip_text)

        block_trips = [html.Div(text) for text in block_trips]

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
            return fig, f"{bus_number} is currently Not In Service", "Next Stop: Not Available", capacity_text, speed_text, timestamp_text, [], toggle_future_stops_text, block_trips
            
        delay, stop_sequence, start_time, eta_time, current_stop_id = (
            current_stop["delay"], current_stop["stop_sequence"], current_stop["start_time"], current_stop["time"], current_stop["stop_id"]
        )
        delay = delay // 60
        # Converting from Unix to PST
        eta_time = datetime.fromtimestamp(eta_time, pytz.timezone("America/Los_Angeles"))
        eta_time = eta_time.strftime("%H:%M")

        future_stops = [stop for stop in current_trip if stop["stop_sequence"] >= current_stop["stop_sequence"]]
        
        if future_stops:
            all_future_stops_eta = []
            all_future_stops_eta.append("Next Stop ETAs")
            for stop in future_stops:
                future_eta_time = datetime.fromtimestamp(stop["time"], pytz.timezone("America/Los_Angeles"))
                future_eta_time = future_eta_time.strftime("%H:%M")
                # future_stop_id = float(stop["stop_id"])
                future_stop_id = int(stop["stop_id"])
                future_stop_name = stops_df.loc[stops_df["stop_id"] == future_stop_id, "stop_name"]
                future_stop_name = future_stop_name.iloc[0]
                future_stops_text = html.Span([
                    f"{future_stop_name} (Stop ",
                    dcc.Link(
                        str(future_stop_id),
                        href=f"/next_buses?stop_id={future_stop_id}",
                        style={"textDecoration": "underline", "color": "blue"}
                    ),
                    f"): {future_eta_time}"
                ])
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


    return fig, desc_text, stop_text, capacity_text, speed_text, timestamp_text, future_stops_eta, toggle_future_stops_text, block_trips

# --- App layout with a container that will be swapped ---
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(id="page-content")
])

@callback(
    Output("url", "href"),
    Input("search-for-bus-home", "n_clicks"),
    Input("search-for-stop-home", "n_clicks"),
    State("bus-search-home", "value"),
    State("stop-search-home", "value"),
    prevent_initial_call=True
)
def navigate_from_home(bus_clicks, stop_clicks, bus_value, stop_value):
    triggered_id = callback_context.triggered_id
    if triggered_id == "search-for-bus-home" and bus_value:
        params = urlencode({"bus": bus_value})
        return f"/bus_tracker?{params}"
    elif triggered_id == "search-for-stop-home" and stop_value:
        params = urlencode({"stop": stop_value})
        return f"/next_buses?{params}"
    return "/"


# --- Callback to swap layouts based on URL ---
@callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    if pathname == "/next_buses":
        return next_buses_layout
    elif pathname == "/bus_tracker":
        return bus_tracker_layout
    else:
        return home_layout

@callback(
    [Output("live-map", "figure"),
     Output("desc-text", "children"),
     Output("stop-text", "children"),
     Output("capacity-text", "children"),
     Output("speed-text", "children"),
     Output("timestamp-text", "children"),
     Output("future-stop-text", "children"),
     Output("toggle-future-stops", "children"),
     Output("block-trips", "children")],
    [Input("interval-component", "n_intervals"),
     Input("manual-update", "n_clicks"),
     Input("search-for-bus", "n_clicks"),
     Input("toggle-future-stops", "n_clicks"),
     Input("url", "href")],
    [State("bus-search-user-input", "value")]
)
def update_bus_callback(n_intervals, manual_update, search_for_bus, toggle_future_stops_clicks, href, bus_number):
    triggered_id = callback_context.triggered_id

    # Check if there is a bus number in the url and use it if so
    if href:
        parsed_url = urlparse(href)
        query_params = parse_qs(parsed_url.query)
        if "bus" in query_params:
            bus_number = query_params["bus"][0]
        

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
    return get_bus_info(buses, bus_number, current_trips, trips_df, stops_df, toggle_future_stops_clicks)


# Update bus number value in search bar of bus_tracker if bus number detected in url
@callback(
    Output("bus-search-user-input", "value"),
    Input("url", "search")
)
def update_bus_input_from_url(search_input):
    if not search_input:
        return dash.no_update

    params = parse_qs(search_input.lstrip("?"))
    bus_number = params.get("bus", [None])[0]
    if bus_number:
        return bus_number
    return dash.no_update


@callback(
    [Output("next-buses-output", "children"),
     Output("toggle-future-buses", "children")],
    [Input("stop-interval-component", "n_intervals"),
     Input("stop-manual-update", "n_clicks"),
     Input("look-up-next-buses", "n_clicks"),
     Input("look-up-next-buses-route", "n_clicks"),
     Input("toggle-future-buses", "n_clicks"),
     Input("url", "href")],
    [State("stop-search-user-input", "value"),
     State("route-search-user-input", "value")]
)
def update_stop_callback(n_intervals, manual_update, look_up_next_buses, look_up_next_buses_route, toggle_future_buses_clicks, href, stop_number_input, route_number_input):
    triggered_id = callback_context.triggered_id

    # Check if there is a stop number in the url and use it if so
    if href:
        parsed_url = urlparse(href)
        query_params = parse_qs(parsed_url.query)
        if "stop_id" in query_params:
            stop_number_input = query_params["stop_id"][0]

    # Manual button triggers a live fetch
    if triggered_id in ["manual-update", "look-up-next-buses", "look-up-next-buses-route"]:
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
    if toggle_future_buses_clicks % 2:
        toggle_future_buses_text = "Show Next 10 Buses"
    else:
        toggle_future_buses_text = "Show Next 20 Buses"
    next_buses_html = get_next_buses(stop_number_input, route_number_input, stops_df, trips_df, current_trips, buses, toggle_future_buses_clicks)
    return next_buses_html, toggle_future_buses_text

@callback(
    Output("stop-search-user-input", "value"),
    Input("url", "search")
)
def set_stop_input(stop_search):
    if stop_search:
        query_params = parse_qs(stop_search.lstrip("?"))
        stop_id = query_params.get("stop_id", [None])[0]
        return stop_id
    return ""


if __name__ == "__main__":
    app.run(debug=True)


# Import necessary modules
import geopandas as gpd
import json
import dash
from dash import html, dcc, register_page, callback
from dash.dependencies import Output, Input, State
import plotly.graph_objects as go
import os
import requests
import pandas as pd
import fetch_fleet_data
import fetch_trip_data
from datetime import datetime, date
from dash import callback_context, no_update
import pytz
from urllib.parse import parse_qs, urlparse
from flask import Flask, Response
import glob
from zoneinfo import ZoneInfo
import numpy as np

# Fallback data from the last run of the Github Actions Workflow
bus_updates = "https://raw.githubusercontent.com/CP8714/BC_Transit_tracker/refs/heads/main/data/bus_updates.json"
trip_updates = "https://raw.githubusercontent.com/CP8714/BC_Transit_tracker/refs/heads/main/data/trip_updates.json"

page_flags = {
    "bus_tracker": False,
    "next_buses": False
}

server = Flask(__name__)

@server.route("/sitemap.xml")
def sitemap():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://www.bctvictracker.ca/</loc>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
      </url>
    </urlset>"""
    return Response(xml, mimetype="application/xml")

app = dash.Dash(
    __name__, 
    server=server, 
    title="BCTVicTracker",
    meta_tags=[
        {"name": "description", "content": "Track BC Transit buses live in Victoria, BC. Get realtime info about a bus or see when the next buses are arriving at a stop"}
    ])

# Layout of the home page
home_layout = html.Div([
    # Navbar which appears on the top of every page and has links to every page
    html.Div(
        className="navbar",
        children=[
            dcc.Link("Home", href="/", className="nav-link"),
            dcc.Link("Bus Tracker", href="/bus_tracker", className="nav-link"),
            dcc.Link("Next Buses", href="/next_buses", className="nav-link"),
        ]
    ),
    html.H1("Welcome to BCTVicTracker"),

    html.H2("A Tracking and Next Bus tool for British Columbia Transit (BC Transit) in Victoria, BC"),

    html.Div([
        dcc.Loading(
            id="loading-component",
            type="circle",
            children=[
                html.H3("Bus Tracker tracks a specific bus (e.g. 9542)"),
                dcc.Link(
                    html.Button("Go to Bus Tracker", id="go-to-bus-tracker", className="home-button"),
                    href="/bus_tracker"
                )
            ]
        )
    ]),

    html.Div([
        dcc.Loading(
            id="loading-component",
            type="circle",
            children=[
                html.H3("Next Buses shows the arrival times of the next buses arriving at a specific stop (e.g. 100032 - Douglas St at Fort St)"),
                dcc.Link(
                    html.Button("Go to Next Buses", id="go-to-next-buses", className="home-button"),
                    href="/next_buses"
                )
            ]
        )
    ]),
    
    html.H4("This website uses publicly available General Transit Feed Specification (GTFS) data from BC Transit to provide users with the ability to view information of a specific bus such as its location, how early/late it is, and the estimated times that it will be arriving at specific stops. This website also allows users to see what are the estimated arrivals times of the next buses arriving at a specific stop and also allows them to only see the next arrivals for buses running a specific route"),
])

# Layout of the bus tracker page where users get information about a specific bus
bus_tracker_layout = html.Div([
    # Navbar which appears on the top of every page and has links to every page
    html.Div(
        className="navbar",
        children=[
            dcc.Link("Home", href="/", className="nav-link"),
            dcc.Link("Bus Tracker", href="/bus_tracker", className="nav-link"),
            dcc.Link("Next Buses", href="/next_buses", className="nav-link"),
        ]
    ),
    html.H2("Bus Tracker Page", className="h2-bus-page-title"),

    html.H4("This is the Bus Tracker Page where you can get information about a specific bus such as its current location, how busy it is, and how early/late it is.", className="h4-bus-page-instruction"),
    html.H4("To use this page, you need to enter a bus number of the bus you want to track such as 9542 and press the Search button. You can also press the Update Now button or press the Enter button on your keyboard. Clicking any of those three will also refresh the page and give you the most up-to-date info on that bus", className="h4-bus-page-instruction"),
    dcc.Loading(
            id="loading-component-map",
            type="circle",
            children=[
                html.Div([
                    html.Label("(Required) Enter Bus Number:"),
                    # Input where the user will tell the site which bus they want to track
                    dcc.Input(
                        id="bus-search-user-input",
                        type="text",
                        placeholder="enter bus number e.g. 9542",
                        value="9542",
                        className="input",
                        debounce=True,
                        n_submit=0
                    ),
                    html.Button("Search", id="search-for-bus", className="input-button",  n_clicks=0),
                    # Button used to clear the input
                    html.Button("Clear", id="clear-bus-input", className="input-button", n_clicks=0),
                ]),
                
                # Manual update button so users can get the most up-to-date info on the bus
                html.Button("Update Now", id="manual-update", className="update-now-button", n_clicks=0),
            ]
    ),

    html.Div([
        dcc.Loading(
            id="loading-component-1",
            type="circle",
            children=[
                html.Div(
                    className="info-1-container",
                    children=[
                        # Info about the bus such as how late/early it is, what is its next stop, what is its current capacity/how busy it is, 
                        # its current speed, and what are the next stops it will be serving 
                        html.H3(id="desc-text"),
                        html.H3(id="stop-text"),
                        html.H3(id="capacity-text"),
                        html.H3(id="speed-text"),
                        # Button where the user can toggle whether they want to only see the next 5 stops served by the bus or all upcoming stops
                        html.Button(id="toggle-future-stops", className="toggle-future-stops-button", n_clicks=0, children="Show All Upcoming Stops"),
                        html.H3(id="future-stop-text"),
                        # All of the trips that this bus will, has or is currently running today
                        html.H3(id="block-trips", className="h3-bus-tracker"),
                        # Timestamp indicating when the data was received by BC Transit
                        html.H3(id="timestamp-text", className="h3-bus-tracker"),
                    ]
                )
            ]
        ),
        dcc.Loading(
            id="loading-component-2",
            type="circle",
            children=[
                # Map which shows the bus' current location as well as the route it is currently running and which stops it is serving
                html.Div(
                    dcc.Graph(
                        id="live-map"
                    ),
                    className="map-container"
                ),
            ]
        )
    ]),

    # Auto-refresh interval
    dcc.Interval(
        id="interval-component",
        interval=60*10000,
        n_intervals=0
    ),
    
])

# Layout of the next buses page where users get information about the next trips arriving at a specific stop. 
# Users can also select to filter by a specific route as well as its variations
next_buses_layout = html.Div([
    # Navbar which appears on the top of every page and has links to every page
    html.Div(
        className="navbar",
        children=[
            dcc.Link("Home", href="/", className="nav-link"),
            dcc.Link("Bus Tracker", href="/bus_tracker", className="nav-link"),
            dcc.Link("Next Buses", href="/next_buses", className="nav-link"),
        ]
    ),

    html.H1("Next Buses Page"),

    html.H4("This is the Next Buses Page where you can get information about the next arrivals for a specific stop can such as what route the next bus is running, the estimated arrival time, and what bus is running that trip.", className="h4-stop-page-instruction"), 
    html.H4("To use this page, you need to select a stop in the top dropdown menu. You can type in the street name (e.g. Douglas St) or the stop number (e.g. 100032) or simply scroll through the options and then select the stop you wish to get the next arrivals for.", className="h4-stop-page-instruction"), 
    html.H4(" Optionally, you can also filter the next arrivals by a specific route by using the second dropdown menu where you can choose the route you want to only see the next arrivals for. You can also choose to have variants of that route also be displayed (e.g. you'll see the 6A if you select the 6)", className="h4-stop-page-instruction"),

    html.Div([
        dcc.Loading(
            id="loading-component-next-buses-1",
            type="circle",
            children=[
                html.Div(
                    # Dropdown where the user selects which stop they want to see the next departures for
                    dcc.Dropdown(
                        id="stop-dropdown",
                        className = "next-buses-dropdown",
                        options=[],
                        placeholder="(Required) Type in the Name or Number of a Stop and/or select a Stop",
                        searchable=True
                    ),
                ),

                html.Div(
                    # Dropdown where the user can optionally filter the next departures by selecting a specific route
                    dcc.Dropdown(
                        id="route-dropdown",
                        className = "next-buses-dropdown",
                        options=[],
                        placeholder="(Optional) Type and/or select a route number e.g. 95",
                        searchable=True
                    ),
                ),

                html.Div([
                    # Checklist where the user can select whether they want to also see variations of their selected route or not
                    dcc.Checklist(
                        id="variant-checklist",    
                        options=[
                            {"label": "Include Variants (e.g. 6A and 6B for the 6)", "value": "include_variants"},
                        ],
                        value=[]
                     )
                ], style={"margin-bottom": "10px"})
            ]
        ),
        dcc.Loading(
            id="loading-component-next-buses-2",
            type="circle",
            children=[
                html.Div(
                    # Search button which will search for the next departures based on the user inputs and display them in a table
                    html.Button("Search", id="stop-search", className="next-buses-button", n_clicks=0),
                ),
                html.Div(
                    # Button where the users can toggle whether they want to see the next 10 or 20 departures
                    html.Button(id="toggle-future-buses", className="next-buses-button", n_clicks=0, children="Show Up To Next 20 Buses"),
                ),
                html.Div(id="next-buses-output"),
            ]
        )
    ]),

    # Auto-refresh interval
    dcc.Interval(
        id="stop-interval-component",
        interval=100*10000,
        n_intervals=0
    ),
])

# --- Helper functions ---
# Returns dictionary containing data from bus_updates.json, the realtime update file for buses
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

# Returns dictionary containing data trip_updates.json, the realtime update file for trips
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

# Returns the service_ids for today denoting which trips are being run today
def get_service_id():
    calendar_file = os.path.join("data", "calendar_dates.csv")
    if os.path.exists(calendar_file):
        calendar_dates = pd.read_csv(calendar_file, dtype=str)
        today = date.today().strftime("%Y%m%d")
        today_service_ids = calendar_dates.loc[calendar_dates["date"] == today]
        service_id_list = today_service_ids["service_id"]  
        return service_id_list

# Returns dataframe of trips.csv, the static file containing info on all trips
def load_trips():
    trips_file = os.path.join("data", "trips.csv")
    if os.path.exists(trips_file):
        trips_df = pd.read_csv(trips_file)
        return trips_df

# Returns dataframe of stops.csv, the static file containing info on all stops
def load_stops():
    stops_file = os.path.join("data", "stops.csv")
    if os.path.exists(stops_file):
        stops_df = pd.read_csv(stops_file)
        return stops_df

# Returns dataframe of routes.csv, the static file containing info on all routes
def load_routes():
    routes_file = os.path.join("data", "routes.csv")
    if os.path.exists(routes_file):
        routes_df = pd.read_csv(routes_file)
        return routes_df

# Finds all the stops that are served by at current_trip_id and returns a dataframe containing them along with all other info from stop_times.csv
def load_stop_times(current_trip_id):
    stop_times_list = []

    for file in sorted(glob.glob(os.path.join("data", "stop_times_part_*.csv"))):
        stop_times_chunks = pd.read_csv(file, chunksize=10000)
        for stop_times_chunk in stop_times_chunks:
            current_trip_stops = stop_times_chunk[stop_times_chunk["trip_id"] == current_trip_id]
            if not current_trip_stops.empty:
                stop_times_list.append(current_trip_stops)
    if stop_times_list:
        return pd.concat(stop_times_list, ignore_index=True)
    return pd.DataFrame()

# Returns appropriate text for bus capacity depending on the capacity input value
# ----------------------------------------------------------------------------------
# capacity is an int value which determines how busy the bus is
# ----------------------------------------------------------------------------------
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


# **This function is currently not being used**
def load_today_scheduled_bus_times(current_stop_id, today_trips_df):
    today_trip_ids = set(today_trips_df["trip_id"].unique())
    current_stop_id = int(current_stop_id)
    current_stop_id = np.int64(current_stop_id)
    
    bus_times_df_list = []
    for file in sorted(glob.glob(os.path.join("data", "stop_times_part_*.csv"))):
        bus_times_chunks = pd.read_csv(file, chunksize=10000)
        for bus_times_chunk in bus_times_chunks:
            next_buses = bus_times_chunk[bus_times_chunk["stop_id"] == current_stop_id]
            if not next_buses.empty:
                today_next_buses = next_buses[next_buses["trip_id"].isin(today_trip_ids)]
                if not today_next_buses.empty:
                    bus_times_df_list.append(today_next_buses)

    if bus_times_df_list:
        return pd.concat(bus_times_df_list, ignore_index=True) 
    return pd.DataFrame()

# Loads all the stop times of the first stop for all the trips in trip_ids
# ----------------------------------------------------------------------------------
# trips_ids is a list of trip ids that a specific bus is running
# ----------------------------------------------------------------------------------
def load_block_departure_times(trip_ids):
    departure_times_list = []

    for file in sorted(glob.glob(os.path.join("data", "stop_times_part_*.csv"))):
        departure_times_chunks = pd.read_csv(file, chunksize=10000, usecols=["trip_id", "stop_sequence", "departure_time"])
        for departure_times_chunk in departure_times_chunks:
            departure_times = departure_times_chunk[departure_times_chunk["trip_id"].isin(trip_ids) & (departure_times_chunk["stop_sequence"] == 1)]
            if not departure_times.empty:
                departure_times_list.append(departure_times)

    if departure_times_list:
        return pd.concat(departure_times_list, ignore_index=True)
    return pd.DataFrame(columns=["trip_id", "stop_sequence", "departure_time"])

# Makes a table with the estimated next arrival times, the route, and bus from the dictionaries in next_buses
# ----------------------------------------------------------------------------------
# next_buses which is a list of dictonaries, each containing the estimated next arrival times, the route, and bus
# ----------------------------------------------------------------------------------
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
                # Add a link to the bus tracker page on the bus number if it's known so users can search up info on that bus
                html.Td(
                    html.A(bus["bus"], href=f"/bus_tracker?bus={bus['bus'][:4]}", style={"textDecoration": "none", "color": "blue"})
                    if bus["bus"] != "Unknown" else bus["bus"],
                    style={"border": "1px solid black", "textAlign": "center"}
                )
            ])
            for bus in next_buses
        ])
    ],
    style={"borderCollapse": "collapse", "border": "1px solid black", "width": "100%", "marginTop": "10px"}
    )

# Returns the outputs for the next buses page
# ----------------------------------------------------------------------------------
# stop_number_input is the stop number selected by the user
# route_number_input is the route number selected by the user
# stops_df dataframe containing all the data from stops.json
# trips_df dataframe containing all the data from trips.json
# current_trips dictionary containing all the realtime data from trip_updates.json
# buses is the dictionary containing all the realtime data from bus_updates.json
# toggle_future_buses_clicks is the number of times the "Show Up To Next 10 Buses"/"Show Up To Next 20 Buses" button has been clicked
# include_variants is the value determining if the user wants to include variants of the selected route or not
# ----------------------------------------------------------------------------------
def get_next_buses(stop_number_input, route_number_input, stops_df, trips_df, current_trips, buses, toggle_future_buses_clicks, include_variants, today_trips_df):
    next_buses = []
    # If no stop number is selected, return the following line of text
    if not stop_number_input:
        return html.Div("Please Select A Stop")
    stop_number_input = int(stop_number_input)
    stop = stops_df.loc[stops_df["stop_id"] == stop_number_input]
    # If the stop number entered does not match any known number, return the following line of text
    if stop.empty:
        return html.Div(f"{stop_number_input} is not a valid Stop Number")
    stop = stop.iloc[0]
    stop_name = stop["stop_name"]
    stop_lat = stop["stop_lat"]
    stop_lon = stop["stop_lon"]
    
    map_fig = go.Figure(layout=go.Layout(paper_bgcolor="#f8f9fa"))
    map_fig.update_layout(height=400)
    map_fig.add_trace(go.Scattermapbox(
        lat=[stop_lat],
        lon=[stop_lon],
        mode="markers",
        marker=dict(size=12, color="red"),
        text=[stop_name],
        hoverinfo="text",
        name="stop location"
    ))
    map_fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center={"lat": stop_lat, "lon": stop_lon},
            zoom=13,
        ),
        margin={"r":0, "t":0, "l":0, "b":0},
    )
    
    stop_name_text = f"Next Estimated Arrivals At Stop {stop_number_input:d} ({stop_name}), (Click on a bus number to see info about that specific bus)"

    stop_number_input = str(stop_number_input)
    # Get current time to determine the next arrivals
    current_time = int(datetime.now().timestamp())


    current_pst = datetime.now(ZoneInfo("America/Los_Angeles"))
    current_pst_hms = current_pst.strftime("%H:%M:%S")
    today_all_arrival_times = load_today_scheduled_bus_times(stop_number_input, today_trips_df)
    upcoming_arrival_times = [bus for _, bus in today_all_arrival_times.iterrows() if bus["arrival_time"] >= current_pst_hms]
    # upcoming_arrival_times = [bus for bus in today_all_arrival_times if bus["arrival_time"] >= current_pst_hms]
    
    # Filter the next trips arriving based on the selected stop and the current time
    next_trip = [stop for stop in current_trips if stop["stop_id"] == stop_number_input]
    next_trip = [stop for stop in next_trip if stop["time"] >= current_time]
    if route_number_input:
        route_number_input = str(route_number_input)
        # If the user wants to include variants, include any trips for that route number which also ends with A, B, N, or X
        if include_variants:
            # route_variants = [f"{route_number_input}-VIC", f"{route_number_input}A-VIC", f"{route_number_input}B-VIC", f"{route_number_input}N-VIC", f"{route_number_input}X-VIC"]
            # all_variant_trips = [trip for trip in trips_df if trip["route_id"] in route_variants]
            # upcoming_arrival_times = [bus for bus in all_variant_trips if bus["trip_id"] in upcoming_arrival_times]
            route_variants = [f"{route_number_input}-VIC", f"{route_number_input}A-VIC", f"{route_number_input}B-VIC", f"{route_number_input}N-VIC", f"{route_number_input}X-VIC"]
            all_variant_trips = trips_df[trips_df["route_id"].isin(route_variants)]
            upcoming_trip_ids = {bus.trip_id for bus in upcoming_arrival_times}
            all_variant_trips_ids = set(all_variant_trips["trip_id"])
            valid_trip_ids = all_variant_trips_ids & upcoming_trip_ids
            upcoming_arrival_times = today_all_arrival_times[today_all_arrival_times["trip_id"].isin(valid_trip_ids)]
            upcoming_arrival_times = upcoming_arrival_times.sort_values("arrival_time")
            next_trip = upcoming_arrival_times
            
            next_trip = [stop for stop in next_trip if stop["route_id"] in route_variants]
        else:
            # route_number_input = str(route_number_input)
            # route_number_input = route_number_input + "-VIC"
            # all_route_trips = [trip for trip in trips_df if trip["route_id"] == route_number_input]
            # upcoming_arrival_times = [bus for bus in all_route_trips if bus["trip_id"] in upcoming_arrival_times]

            route_number_input = f"{route_number_input}-VIC"
            all_route_trip_ids = set(trips_df.loc[trips_df["route_id"] == route_number_input, "trip_id"])
            upcoming_trip_ids = {bus.trip_id for bus in upcoming_arrival_times}
            valid_trip_ids = all_route_trip_ids & upcoming_trip_ids
            upcoming_arrival_times = today_all_arrival_times[today_all_arrival_times["trip_id"].isin(valid_trip_ids)]
            upcoming_arrival_times = upcoming_arrival_times.sort_values("arrival_time")
           
            next_trip = [stop for stop in next_trip if stop["route_id"] == route_number_input]
            next_trip = upcoming_arrival_times

        route_number_input = route_number_input.split('-')[0] 
        stop_name_text = f"Next Estimated Arrivals For Route {route_number_input} At Stop {stop_number_input} ({stop_name}), (Click on a bus number to see info about that specific bus)"

    else:
        # Sort the next trips by arrival time 
        next_trip = sorted(next_trip, key=lambda x: x["time"])
    
    
        next_trip = upcoming_arrival_times
        next_trip = sorted(next_trip, key=lambda x: x["arrival_time"])
        

    # Show only the next 10 arrivals if the "Show Up To Next 10 Buses"/"Show Up To Next 20 Buses" button has not been pressed or been pressed an even amount of times
    if toggle_future_buses_clicks % 2 == 0:
        next_trip = next_trip[:10]
    # Show the next 20 arrivals if the Show Up To Next 10 Buses/Show Up To Next 20 Buses button has been pressed an odd amount of times
    else:
        next_trip = next_trip[:20]

    # Search up which bus is running each of the next trips in next_trip
    bus_lat_list = []
    bus_lon_list = []
    bus_number_list = []
    if route_number_input:
        for _, bus in next_trip.iterrows():
            scheduled = False
            current_bus = next((b for b in buses if b["trip_id"] == bus["trip_id"]), None)
            # If there is no bus currently running that trip, check the blocks to see if one is scheduled. If not, set bus_number to "Unknown"
            if not current_bus:
                bus_number = "Unknown"
                current_trip = trips_df[trips_df["trip_id"] == bus["trip_id"]]
                if not current_trip.empty:
                    current_trip = current_trip.iloc[0]
                    block = current_trip["block_id"]
                    full_block = trips_df[trips_df["block_id"] == block]
                    for _, row in full_block.iterrows():
                        current_bus = next((b for b in buses if b["trip_id"] == row["trip_id"]), None)
                        if current_bus:
                            # The bus number is only the final four digits of the its id
                            bus_number = current_bus["id"]
                            bus_number = bus_number[-4:]
                            scheduled = True
                            break
            else:
                # The bus number is only the final four digits of the its id
                bus_number = current_bus["id"]
                bus_number = bus_number[-4:]
                bus_lat_list.append(current_bus["lat"])
                bus_lon_list.append(current_bus["lon"])
                bus_number_list.append(bus_number)
            next_bus = trips_df[trips_df["trip_id"] == bus["trip_id"]]
            if not next_bus.empty:
                next_bus = next_bus.iloc[0]
                route = next_bus["route_id"]
                route_number = route.split('-')[0] 
                headsign = next_bus["trip_headsign"]
                # Getting the arrival time and converting it to PST and only including hours and minutes
                # arrival_time = datetime.fromtimestamp(bus["time"], pytz.timezone("America/Los_Angeles"))
    
                # arrival_time = datetime.fromtimestamp(bus["arrival_time"], pytz.timezone("America/Los_Angeles"))
                # arrival_time = arrival_time.strftime("%H:%M")
                arrival_time = bus["arrival_time"]
                arrival_time = arrival_time[:5]
                if scheduled:
                    next_buses.append({
                        "arrival_time": arrival_time,
                        "trip_headsign": f"{route_number} {headsign}",
                        "bus": f"{bus_number} (Scheduled)"
                    })
                else:
                    next_buses.append({
                        "arrival_time": arrival_time,
                        "trip_headsign": f"{route_number} {headsign}",
                        "bus": f"{bus_number}"
                    })
    else:
        for bus in next_trip:
            scheduled = False
            current_bus = next((b for b in buses if b["trip_id"] == bus["trip_id"]), None)
            # If there is no bus currently running that trip, check the blocks to see if one is scheduled. If not, set bus_number to "Unknown"
            if not current_bus:
                bus_number = "Unknown"
                current_trip = trips_df[trips_df["trip_id"] == bus["trip_id"]]
                if not current_trip.empty:
                    current_trip = current_trip.iloc[0]
                    block = current_trip["block_id"]
                    full_block = trips_df[trips_df["block_id"] == block]
                    for _, row in full_block.iterrows():
                        current_bus = next((b for b in buses if b["trip_id"] == row["trip_id"]), None)
                        if current_bus:
                            # The bus number is only the final four digits of the its id
                            bus_number = current_bus["id"]
                            bus_number = bus_number[-4:]
                            scheduled = True
                            break
            else:
                # The bus number is only the final four digits of the its id
                bus_number = current_bus["id"]
                bus_number = bus_number[-4:]
                bus_lat_list.append(current_bus["lat"])
                bus_lon_list.append(current_bus["lon"])
                bus_number_list.append(bus_number)
            next_bus = trips_df[trips_df["trip_id"] == bus["trip_id"]]
            if not next_bus.empty:
                next_bus = next_bus.iloc[0]
                route = next_bus["route_id"]
                route_number = route.split('-')[0] 
                headsign = next_bus["trip_headsign"]
                # Getting the arrival time and converting it to PST and only including hours and minutes
                # arrival_time = datetime.fromtimestamp(bus["time"], pytz.timezone("America/Los_Angeles"))
    
                # arrival_time = datetime.fromtimestamp(bus["arrival_time"], pytz.timezone("America/Los_Angeles"))
                # arrival_time = arrival_time.strftime("%H:%M")
                arrival_time = bus["arrival_time"]
                arrival_time = arrival_time[:5]
                if scheduled:
                    next_buses.append({
                        "arrival_time": arrival_time,
                        "trip_headsign": f"{route_number} {headsign}",
                        "bus": f"{bus_number} (Scheduled)"
                    })
                else:
                    next_buses.append({
                        "arrival_time": arrival_time,
                        "trip_headsign": f"{route_number} {headsign}",
                        "bus": f"{bus_number}"
                    })
                
    if bus_lat_list:
        map_fig.add_trace(go.Scattermapbox(
            lat=bus_lat_list,
            lon=bus_lon_list,
            mode="markers",
            marker=dict(size=10, color="blue"),
            hovertext=bus_number_list,
            hoverinfo="text",
            name="Bus Locations",
        ))
    # Returning the text describing the stop and route selected by the user as well as the table containing the next arrivals
    return html.Div([
        html.H3(stop_name_text),
        make_next_buses_table(next_buses),
        html.H3(f"Scheduled Assigned Bus means the bus is currently not running that trip"),
        html.Div(
            className="next-buses-map-container",
            children = [
            html.H3("Map showing the locations of the next arriving buses (Buses that are scheduled are not shown)"),
            dcc.Graph(id="next-buses-map", figure=map_fig),
            ]
        )
    ])


# Returns the outputs for the bus tracker page
# ----------------------------------------------------------------------------------
# buses is the dictionary containing all the realtime data from bus_updates.json
# bus_number is the string value of the bus which the user wants to track
# current_trips is the dictionary containing all the realtime data from trip_updates.json
# trips_df dataframe containing all the data from trips.json
# stops_df dataframe containing all the data from stops.json
# toggle_future_stops_clicks is the number of times the "Show Next 5 Stops"/"Show All Upcoming Stops" button has been clicked
# reset_url is the new url that is to be used at the end of the current update_bus_callback
# triggered_id is the id of what triggered update_bus_callback
# update_bus_input is used to determine if the user has clicked the Clear button for the input
# ----------------------------------------------------------------------------------
def get_bus_info(buses, bus_number, current_trips, trips_df, stops_df, toggle_future_stops_clicks, reset_url, triggered_id, update_bus_input):
    # Generate the initial figure for the map and use the same background color as for the rest of the website
    fig = go.Figure(layout=go.Layout(paper_bgcolor="#f8f9fa"))
    fig.update_layout(height=600)
    toggle_future_stops_text = "Show All Upcoming Stops"
    # Search for the inputted bus in buses featuring the realtime data from buses_updates.json and get all the data of that bus
    bus = next((b for b in buses if b["id"].endswith(bus_number)), None)

    # Update the text for the "Show All Upcoming Stops"/"Show Next 5 Stops" depending on how many times the button has been pressed
    if toggle_future_stops_clicks % 2 == 0:
        toggle_future_stops_text = "Show All Upcoming Stops"
    else:
        toggle_future_stops_text = "Show Next 5 Stops"

    # If no results for the inputted bus, it is not running right now
    if not bus:
        return fig, f"{bus_number} is not running at the moment", "Next Stop: Not Available", "Occupancy Status: Not Available", "Current Speed: Not Available", "", [], toggle_future_stops_text, "", reset_url, update_bus_input

    # Get the position, current route, its id, how busy it is, its current trip, next stop, and bearing along with the timestamp that BC Transit received this data
    lat, lon, speed, route, bus_id, capacity, trip_id, stop_id, bearing, timestamp = (
        bus["lat"], bus["lon"], bus["speed"], bus["route"], bus["id"][6:], bus["capacity"], bus["trip_id"], bus["stop_id"], bus["bearing"], bus["timestamp"]
    )

    # Get the realtime data from current_trips of the current trip being run by that bus
    current_trip = [trip for trip in current_trips if trip["trip_id"] == trip_id]
    # Get the data regarding the next stop which will be served by that bus
    current_stop = next((stop for stop in current_trip if stop["stop_id"] == stop_id), None)
    future_stops_eta = []

    # Get the text regarding how busy that bus currently is
    capacity_text = get_capacity(capacity)

    # Convert the timestamp time to PST and only include hours, minutes, and seconds for the timestamp output
    utc_time = datetime.fromisoformat(timestamp).replace(tzinfo=pytz.utc)
    pst_time = utc_time.astimezone(pytz.timezone("America/Los_Angeles"))
    pst_timestamp = pst_time.strftime("%H:%M:%S")
    timestamp_text = f"Updated at {pst_timestamp}"

    # Converting speed from m/s to km/h
    speed = speed * 3.6

    # Speed text output
    speed_text = (
        f"Current Speed: {speed:.1f} km/h"
        if speed else f"Current Speed: 0 km/h"
    )

    # Determine if the bus is actually running a trip or heading back to a transit yard
    deadheading = False
    block_trips = []
    if not current_trip:
        deadheading = True
    else:
        # Get the block id that the bus is running and find all trips it is running and their respective departure times
        block = trip_id.split(":")[2]
        full_block = trips_df[trips_df["block_id"].astype(str) == block]
        block_trips.append(f"{bus_number} will be running the following trips today:")

        # Load all the first stop departure times for all trips in the block
        stop_times_df = load_block_departure_times(full_block["trip_id"].tolist())

        # Merge full_block and stop_times_df so that all the relevant info about every trip run by that bus is now in a single dataframe
        full_block = full_block.merge(stop_times_df, on="trip_id", how="left")
        # Allow departure_time to exceed 24:00:00 e.g. 25:00:00
        full_block["departure_time"] = pd.to_timedelta(full_block["departure_time"])
        full_block = full_block.sort_values(by="departure_time")
        # Only keep hours and minutes
        full_block["departure_time"] = full_block["departure_time"].apply(
            lambda t: f"{int(t.total_seconds() // 3600):02d}:{int((t.total_seconds() % 3600) // 60):02d}"
        )

        # Create output detailing all the trips run by that bus
        for _, row in full_block.iterrows():
            departure_time = row["departure_time"]
            route_number = row["route_id"].split("-")[0]
            headsign = row["trip_headsign"]
            block_trip_text = f"{route_number} {headsign} leaving at {departure_time}"
            block_trips.append(block_trip_text)
        block_trips = [html.Div(text) for text in block_trips]

        # Get lon and lat coordinates for all stops on current route to be displayed on map
        stop_times_df = load_stop_times(trip_id)
        current_trip_stop_ids = stop_times_df["stop_id"].astype(float).tolist()
        current_trip_stops_df = stops_df[stops_df["stop_id"].isin(current_trip_stop_ids)]

        # Get the text to be displayed saying how busy that bus currently is
        capacity_text = get_capacity(capacity)

        # If the data is not currently stating the bus' next stop, it is stated that it is Not In Service
        if not current_stop:
            # Initialize the map with it being centered on the bus' current location
            fig.update_layout(
                mapbox = dict(
                    style="open-street-map",
                    center={"lat": lat, "lon": lon},
                    zoom=14,
                ),
                height=600,
                margin={"r":0,"t":0,"l":0,"b":0},
                uirevision=None
            )

            # Add the bus location as a blue marker
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
            return fig, f"{bus_number} is currently Not In Service", "Next Stop: Not Available", capacity_text, speed_text, timestamp_text, [], toggle_future_stops_text, block_trips, reset_url, update_bus_input
            
        # Get the current delay of the next stop, what stop is the next one, the start time of this trip, the eta of the next stop, and its id
        delay, stop_sequence, start_time, eta_time, current_stop_id = (
            current_stop["delay"], current_stop["stop_sequence"], current_stop["start_time"], current_stop["time"], current_stop["stop_id"]
        )
        # Converting the delay into minutes
        delay = delay // 60
        if eta_time == 0 and stop_sequence == 1:
                    eta_time = start_time
                    eta_time = eta_time[:-3]
        else:
            # Converting the eta time into PST and only keeping minutes and hours
            eta_time = datetime.fromtimestamp(eta_time, pytz.timezone("America/Los_Angeles"))
            eta_time = eta_time.strftime("%H:%M")

        # Only keeping the stops that haven't yet been served by that bus
        future_stops = [stop for stop in current_trip if stop["stop_sequence"] >= current_stop["stop_sequence"]]

        # Creating the next stops output
        if future_stops:
            all_future_stops_eta = []
            all_future_stops_eta.append("Next Stop ETAs (click on a stop number to see the next departures at that stop)")
            for stop in future_stops:
                # If the next stop is the first one, get the start time as the eta and remove seconds
                # Otherwise, get the eta time of the next stop and convert it to PST and only keep hours and minutes
                if stop["time"] == 0:
                    future_eta_time = stop["start_time"]
                    future_eta_time = future_eta_time[:-3]
                else:
                    future_eta_time = datetime.fromtimestamp(stop["time"], pytz.timezone("America/Los_Angeles"))
                    future_eta_time = future_eta_time.strftime("%H:%M")
                future_stop_id = int(stop["stop_id"])
                future_stop_name = stops_df.loc[stops_df["stop_id"] == future_stop_id, "stop_name"]
                future_stop_name = future_stop_name.iloc[0]
                # For each line, have the stop number be a link to the next buses page so the user can search up the next buses arriving at that specific stop
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
            # Include all future stops depending on if the "Show All Upcoming Stops" button has been clicked
            else:
                future_stops_eta = all_future_stops_eta
            future_stops_eta = [html.Div(text) for text in future_stops_eta]
        
        
    
    # stop_id in stops_df is a float so stop_id from buses must be converted to a float 
    if stop_id:
        stop_id = float(stop_id)
        stop = stops_df.loc[stops_df["stop_id"] == stop_id, "stop_name"]
        stop = stop.iloc[0]
    # Get rid of the -VIC part of the route_id
    route_number = route.split('-')[0] 
    trip_headsign = trips_df.loc[trips_df["trip_id"] == trip_id, "trip_headsign"]

    # Load the routes.shp file get the lines for all routes and then select the one being currently run by that bus
    fp_routes = os.path.join("data", "routes.shp")
    route_data = gpd.read_file(fp_routes)
    # Route map not shown for buses heading back to a transit yard
    if trip_headsign.empty:
        route = "0"
    current_route = route_data[route_data["route_id"] == route]
    route_geojson = json.loads(current_route.to_json())

    # Add the route line to the map and have it centered on the bus' current position
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
        margin={"r":0,"t":0,"l":0,"b":0},
        uirevision=None
    )

    # If the bus is currently running a route, add the stop locations for that route on the map as red markers
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

    # Add the current bus location as a blue marker
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
    
    if deadheading:
        # If the bus is currently Not In Service and heading to a transit yard, set the below text for the description and next stop text
        if stop_id == 900000 or stop_id == 930000:
            desc_text = f"{bus_id} is currently returning back to a transit yard"
            stop_text = f"Next Stop: {stop}"
        # If the bus is currently Not In Service and sitting at a transit yard, set the below text for the description and next stop text
        elif not stop_id:
            desc_text = f"{bus_id} is sitting at a transit yard"
            stop_text = f"Next Stop: Not Available"
        # If the bus is currently Not In Service and heading to a run another route, set the below text for the description and next stop text
        else:
            desc_text = f"{bus_id} is currently deadheading to run another route"
            stop_text = f"First Stop: {stop}"
    else:
        # Remove seconds from start_time
        start_time = start_time[:5]
        trip_headsign = trip_headsign.iloc[0]
        # Checking if the bus is on schedule
        if delay == 0:
            # Checking if the next stop is the first one
            if stop_sequence == 1:
                desc_text = f"{bus_id} will be running the {route_number} {trip_headsign} departing at {start_time}"
            else:
                desc_text = f"{bus_id} is currently on schedule running the {route_number} {trip_headsign}"
        # Checking if the bus is currently early
        elif delay < 0:
            delay = delay * -1
            # Checking if the next stop is the first one
            if delay == 1:
                desc_text = f"{bus_id} is currently {delay:d} minute early running the {route_number} {trip_headsign}"
            else:
                desc_text = f"{bus_id} is currently {delay:d} minutes early running the {route_number} {trip_headsign}"
        else:
            if delay == 1:
                # Checking if the next stop is the first one
                desc_text = f"{bus_id} is currently {delay:d} minute late running the {route_number} {trip_headsign}"
            else:
                desc_text = f"{bus_id} is currently {delay:d} minutes late running the {route_number} {trip_headsign}"

        # Checking if the bus is currently moving
        if speed > 0:
            stop_text = f"Next Stop: {stop} (ETA: {eta_time})"
        else:
            stop_text = f"Current Stop: {stop}"


    return fig, desc_text, stop_text, capacity_text, speed_text, timestamp_text, future_stops_eta, toggle_future_stops_text, block_trips, reset_url, update_bus_input

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="tracker-url-request"),
    dcc.Store(id="next-buses-url-request"),
    html.Div(id="page-content"),
])


# Callback to set the page layout based on the URL 
@callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    if pathname == "/bus_tracker":
        page_flags["bus_tracker"] = True
        page_flags["next_buses"] = False
        return bus_tracker_layout
    elif pathname == "/next_buses":
        page_flags["next_buses"] = True
        page_flags["bus_tracker"] = False
        return next_buses_layout
    else:
        page_flags["bus_tracker"] = False
        page_flags["next_buses"] = False
        return home_layout

# Callback which sets the outputs of the bus tracker page
@callback(
    [Output("live-map", "figure"),
     Output("desc-text", "children"),
     Output("stop-text", "children"),
     Output("capacity-text", "children"),
     Output("speed-text", "children"),
     Output("timestamp-text", "children"),
     Output("future-stop-text", "children"),
     Output("toggle-future-stops", "children"),
     Output("block-trips", "children"),
     Output("tracker-url-request", "data"),
     Output("bus-search-user-input", "value")],
    [Input("bus-search-user-input", "n_submit"),
     Input("interval-component", "n_intervals"),
     Input("manual-update", "n_clicks"),
     Input("search-for-bus", "n_clicks"),
     Input("toggle-future-stops", "n_clicks"),
     Input("url", "href"),
     Input("clear-bus-input", "n_clicks")],
    [State("bus-search-user-input", "value")]
)
def update_bus_callback(n_submits, n_intervals, manual_update, search_for_bus, toggle_future_stops_clicks, href, clear_bus_input, bus_number):

    if not page_flags.get("bus_tracker", False):
        return (no_update,) * 11 
        
    triggered_id = callback_context.triggered_id
    reset_url = no_update

    # If the Clear button on the bus tracker page is pressed, clear the input
    if triggered_id == "clear-bus-input":
        return (no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, "")
        

    # Check if there is a bus number in the current url and if so, use it as the bus number input
    if href and "/bus_tracker" in href:
        parsed_url = urlparse(href)
        query_params = parse_qs(parsed_url.query)
        if "bus" in query_params:
            bus_number = query_params["bus"][0]
        reset_url = {"url": "/bus_tracker"}
        

    # Clicking the Manual Update or Search buttons or pressing the Enter key triggers a fetch for the most recent trip and bus realtime data
    if triggered_id in ["manual-update", "search-for-bus", "bus-search-user-input"]:
        try:
            fetch_fleet_data.fetch()
            fetch_trip_data.fetch()
        except Exception as e:
            print(f"Error fetching live fleet data: {e}", flush=True)

    # Load the latest data in the /data folder from bus_updates.json, trip_updates.json, trips.csv, and stops.csv
    buses = load_buses()
    current_trips = load_current_trips()
    trips_df = load_trips()
    stops_df = load_stops()
    return get_bus_info(buses, bus_number, current_trips, trips_df, stops_df, toggle_future_stops_clicks, reset_url, triggered_id, no_update)

# Callback which sets the outputs of the next buses page
@callback(
    [Output("next-buses-output", "children"),
     Output("toggle-future-buses", "children"),
     Output("stop-dropdown", "options"),
     Output("route-dropdown", "options"),
     Output("next-buses-url-request", "data")],
    [Input("stop-interval-component", "n_intervals"),
     Input("stop-search", "n_clicks"),
     Input("toggle-future-buses", "n_clicks"),
     Input("url", "href")],
    [State("stop-dropdown", "value"),
     State("route-dropdown", "value"),
     State("variant-checklist", "value")]
)
def update_stop_callback(n_intervals, stop_search, toggle_future_buses_clicks, href, stop_number_input, route_number_input, include_variants):

    if not page_flags.get("next_buses", False):
        return (no_update,) * 5
        
    triggered_id = callback_context.triggered_id    
    reset_url = no_update
        
    # Check if there is a stop number in the url and use it if so
    if href and "/next_buses" in href and triggered_id not in ["stop-search"]:
        parsed_url = urlparse(href)
        query_params = parse_qs(parsed_url.query)
        if "stop_id" in query_params:
            stop_number_input = query_params["stop_id"][0]
        reset_url = {"url": "/next_buses"}

    # Get the most up-to-date realtime data for trip_updates.json and bus_updates.json
    try:
        fetch_fleet_data.fetch()
        fetch_trip_data.fetch()
    except Exception as e:
        print(f"Error fetching live fleet data: {e}", flush=True)

    # Load the latest bus data in the /data folder from bus_updates.json, trip_updates.json, trips.csv, and stops.csv
    buses = load_buses()
    current_trips = load_current_trips()
    trips_df = load_trips()
    service_id_list = get_service_id()
    service_id_list = [np.int64(x) for x in service_id_list]
    today_trips_df = trips_df[trips_df["service_id"].isin(service_id_list)]
    stops_df = load_stops()
    routes_df = load_routes()
    

    # Populate the stop dropdown with the values being the stop ids and the labels having both the stop ids and the stop names
    stop_options = [
        {"label": f"{row['stop_name']} (Stop {int(row['stop_id'])})", "value": int(row['stop_id'])}
        for _, row in stops_df.iterrows()
    ]
    # Populate the route dropdown with the values being the route numbers and the labels having both the route numbers and the destinations
    route_options = [
    {"label": f"{row['route_short_name']} {row['route_long_name']}", "value": row['route_short_name']}
        for _, row in routes_df.iterrows()
    ]    
    # Change the text of the "Show Up To Next 10 Buses"/"Show Up To Next 20 Buses" button depending on how many times it has been clicked
    if toggle_future_buses_clicks % 2:
        toggle_future_buses_text = "Show Up To Next 10 Buses"
    else:
        toggle_future_buses_text = "Show Up To Next 20 Buses"
    # Get the main output for the next buses page containing the table with the next bus arrivals as well as the text stating the user inputs
    next_buses_html = get_next_buses(stop_number_input, route_number_input, stops_df, today_trips_df, current_trips, buses, toggle_future_buses_clicks, include_variants, today_trips_df)
    # Returns the above outputs, populate the dropdowns, and set the text for the "Show Up To Next 10 Buses"/"Show Up To Next 20 Buses" button
    return next_buses_html, toggle_future_buses_text, stop_options, route_options, reset_url

@callback(Output("url", "href"), [Input("tracker-url-request", "data"),  Input("next-buses-url-request", "data")])
def set_url(tracker_request, next_buses_request):
    if page_flags.get("bus_tracker", True):
        if tracker_request:
            return tracker_request["url"]
    elif page_flags.get("next_buses", True):
        if next_buses_request:
            return next_buses_request["url"]
    else:
        return no_update


if __name__ == "__main__":
    app.run(debug=True)

import dash
from dash import html, dcc, register_page, callback
from dash.dependencies import Output, Input, State
import fetch_fleet_data
import fetch_trip_data
from dash import callback_context
import json
import plotly.graph_objects as go
import math
import os
import requests
import pandas as pd
from datetime import datetime
import pytz

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Fallback data
bus_updates = "https://raw.githubusercontent.com/CP8714/BC_Transit_tracker/refs/heads/main/data/bus_updates.json"
trip_updates = "https://raw.githubusercontent.com/CP8714/BC_Transit_tracker/refs/heads/main/data/trip_updates.json"

dash.register_page(__name__, path="/next_buses")

layout = html.Div([
    html.H1("Next Buses Page"),
    dcc.Link("← Back to Bus Tracker", href="/"),
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
    html.Button("Update Now", id="manual-update", n_clicks=0, style={"margin-bottom": "10px"}),

    html.Div([
        dcc.Loading(
            id="loading-component",
            type="circle",
            children=[
                html.H3(id="stop-name-text"),
                # html.H3(id="desc-text"),
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


# --- Helper functions ---
def load_buses():
    """Load latest bus_updates.json safely."""
    data_file = os.path.join(DATA_DIR, "bus_updates.json")
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
    data_file = os.path.join(DATA_DIR, "trip_updates.json")
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            return json.load(f)
    try:
        response = requests.get(trip_updates, timeout=10)
        return response.json()
    except:
        return []

def load_trips():
    trips_file = os.path.join(DATA_DIR, "trips.csv")
    if os.path.exists(trips_file):
        trips_df = pd.read_csv(trips_file)
        return trips_df

def load_stops():
    stops_file = os.path.join(DATA_DIR, "stops.csv")
    if os.path.exists(stops_file):
        stops_df = pd.read_csv(stops_file)
        return stops_df

def load_stop_times(current_trip_id):
    stop_times_file = os.path.join(DATA_DIR, "stop_times.csv")
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


def get_next_buses(stop_number):
    if not stop_number:
        return "Hello", "Hello World"
    return [stop_number, "Hello World"]

@callback(
    [Output("stop-name-text", "children"),
     Output("desc-text", "children")],
    [Input("interval-component", "n_intervals"),
     Input("manual-update", "n_clicks"),
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
    return get_next_buses(stop_number)

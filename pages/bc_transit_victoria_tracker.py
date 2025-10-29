import dash
from dash import html, dcc, callback
from dash.dependencies import Output, Input, State
from dash import callback_context
import fetch_fleet_data
import fetch_trip_data
import json
import os
import requests
import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Fallback URLs
bus_updates_url = "https://raw.githubusercontent.com/CP8714/BC_Transit_tracker/refs/heads/main/data/bus_updates.json"
trip_updates_url = "https://raw.githubusercontent.com/CP8714/BC_Transit_tracker/refs/heads/main/data/trip_updates.json"

dash.register_page(__name__, path="/next_buses")

layout = html.Div([
    html.H1("Next Buses Page"),
    dcc.Link("← Back to Bus Tracker", href="/"),
    
    html.Div([
        html.Label("Enter Bus Stop Number:"),
        dcc.Input(
            id="stop-search-user-input",
            type="text",
            placeholder="Enter stop number e.g. 100032",
            value="100032",
            debounce=True
        ),
        html.Button("Search", id="look-up-next-buses", n_clicks=0),
        html.Button("Update Now", id="manual-update", n_clicks=0),
    ], style={"margin-bottom": "10px"}),

    html.Div([
        dcc.Loading(
            id="loading-component",
            type="circle",
            children=[
                html.H3(id="stop-name-text"),
                html.H3(id="desc-text"),
            ]
        )
    ]),

    dcc.Interval(id="interval-component", interval=60000, n_intervals=0)
])

# ---------------- Helper functions ----------------
def safe_fetch_json(file_path, fallback_url):
    """Load local JSON if exists, otherwise fetch from GitHub."""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    try:
        resp = requests.get(fallback_url, timeout=10)
        return resp.json()
    except Exception:
        return []

def load_buses():
    return safe_fetch_json(os.path.join(DATA_DIR, "bus_updates.json"), bus_updates_url)

def load_current_trips():
    return safe_fetch_json(os.path.join(DATA_DIR, "trip_updates.json"), trip_updates_url)

# ---------------- Callback ----------------
@callback(
    [Output("stop-name-text", "children"),
     Output("desc-text", "children")],
    [Input("interval-component", "n_intervals"),
     Input("manual-update", "n_clicks"),
     Input("look-up-next-buses", "n_clicks")],
    [State("stop-search-user-input", "value")]
)
def update_stop_callback(n_intervals, manual_update, search_clicks, stop_number):
    triggered_id = callback_context.triggered_id

    # Only fetch live data if manual button clicked
    if triggered_id in ["manual-update", "look-up-next-buses"]:
        try:
            fetch_fleet_data.fetch()
            fetch_trip_data.fetch()
        except Exception as e:
            print(f"Error fetching live data: {e}", flush=True)

    # Load latest bus data safely
    buses = load_buses()
    trips = load_current_trips()

    # Build safe display
    stop_text = f"Stop: {stop_number or 'N/A'}"
    desc_text = f"{len(buses)} active buses, {len(trips)} current trips"

    return stop_text, desc_text

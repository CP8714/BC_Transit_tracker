import dash
from dash import html, dcc, register_page, callback
from dash.dependencies import Output, Input, State
import fetch_fleet_data
import fetch_trip_data
from dash import callback_context

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

@callback(
    [Output("stop-name-text", "children"),
     ],
    [Input("interval-component", "n_intervals"),
     Input("manual-update", "n_clicks"),
     Input("look-up-next-buses", "n_clicks"),],
    [State("stop-search-user-input", "value")]
)
def update_map_callback(n_intervals, manual_update, look_up_next_buses, toggle_future_stops_clicks, stop_number):
    triggered_id = callback_context.triggered_id

    # Manual button triggers a live fetch
    if triggered_id == "manual-update" or triggered_id == "stop-search-user-input":
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
    return stop_number

# === Run app ===
if __name__ == "__main__":
    app.run(debug=True)

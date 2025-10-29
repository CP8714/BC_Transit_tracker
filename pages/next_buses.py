import dash
from dash import html, dcc, callback
from dash.dependencies import Output, Input, State
from dash import callback_context

dash.register_page(__name__, path="/next_buses")

layout = html.Div([
    html.H1("Next Buses Page"),
    html.H3(id="stop-name-text"),
    html.H3(id="desc-text"),
    html.Button("Update Now", id="manual-update", n_clicks=0),
    dcc.Interval(id="interval-component", interval=1000, n_intervals=0)
])

@callback(
    [Output("stop-name-text", "children"),
     Output("desc-text", "children")],
    [Input("interval-component", "n_intervals"),
     Input("manual-update", "n_clicks")]
)
def update_stop(n, click):
    return f"Intervals: {n}", f"Clicks: {click}"

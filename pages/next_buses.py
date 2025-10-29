import dash
from dash import html, dcc, register_page, callback
from dash.dependencies import Output, Input, State

dash.register_page(__name__, path="/next_buses")

layout = html.Div([
    html.H1("Next Buses Page"),
    dcc.Link("← Back to Bus Tracker", href="/"),
])

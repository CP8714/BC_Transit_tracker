import dash
from dash import html, dcc, register_page, callback

dash.register_page(__name__, path="/next_buses")

layout = html.Div([
    html.H1("Next Busses Page"),
    dcc.Link("← Back to Bus Tracker", href="/"),
])

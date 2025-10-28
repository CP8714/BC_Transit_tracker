import dash
from dash import html

dash.register_page(__name__, path="/next_busses")

layout = html.Div([
    html.H1("Next Busses Page"),
])

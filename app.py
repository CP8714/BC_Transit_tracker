from dash import Dash, dcc, html
import dash

app = Dash(__name__, use_pages=True)

app.layout = dash.page_container

if __name__ == "__main__":
    app.run(debug=True)

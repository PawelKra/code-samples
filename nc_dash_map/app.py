import json
import urllib.request
import dash
from dash import html
from dash import dcc
import dash_leaflet as dl
from dash.dependencies import Output, Input
from dash import callback

from dash.dependencies import Output, Input
from dash.exceptions import PreventUpdate
from flask import Flask
from config import TC_URL, PARAMS
from terracotta_toolbelt import singleband_url, point_url


cmaps = ["Viridis", "Spectral", "Greys", 'Hot']
srngv = [-10.0, 40.0]

cmap0 = "Viridis"

# App Stuff.
server = Flask(__name__)
app = dash.Dash(__name__, server=server)
app.layout = html.Div(children=[
    # Create the map itself.
    dl.Map(id="map", center=[40, -3], zoom=6, children=[
        dl.TileLayer(),
        dl.TileLayer(id="tc", opacity=0.5),
        dl.Colorbar(id="cbar", width=150, height=20, style={
            "margin-left": "40px", "margin-bottom": '120px'},
            position="bottomleft"),
    ], style={"width": "100%", "height": "100%"}),

    html.Div(children=[
        html.Div("Colorscale"),
        dcc.Dropdown(id="dd_cmap", options=[dict(value=c, label=c) for c in cmaps], value=cmap0),
        html.Br(),
        html.Div("Opacity"),
        dcc.Slider(id="opacity", min=0, max=1, value=0.5, step=0.1, marks={0: "0", 0.5: "0.5", 1: "1"}),
        html.Br(),
        html.Div("Stretch range"),
        dcc.RangeSlider(id="srng", min=srngv[0], max=srngv[1], value=srngv,
                        marks={v: "{:.1f}".format(v) for v in srngv}),
        html.Br(),
        html.Div("Value @ click position"),
        html.P(children="-", id="label"),
    ], className="info",
        style = {'margin-top': '10px'}
    ),

    html.Div(children=[
        dcc.Slider(
            1, len(PARAMS), step=None, value=0,
            marks= {ii: {'label': val[5:-3], 'style': {
                'writing-mode': 'vertical-rl',
                'height': '60px',
                'textOrientation': 'use-glyph-orientation'
            }} for ii, val in enumerate(PARAMS)
            },
            id='map_values',
            updatemode='drag'
        ),
    ], className="info",
        style = {'width': '98%', 'height': '80px', 'margin-top': '90vh'}
    ),
], style={"display": "grid", "width": "100%", "height": "100vh"})


@app.callback(Output("tc", "opacity"), [Input("opacity", "value")])
def update_opacity(opacity):
    return opacity


@app.callback([Output("srng", "min"), Output("srng", "max"), Output("srng", "value"),
               Output("srng", "marks")],
              [Input("map_values", "value")])
def update_stretch_range(param):
    if not param:
        return PreventUpdate
    srnga = [-10, 40]
    return srnga[0], srnga[1], srnga, {v: "{:.1f}".format(v) for v in srnga}


@app.callback([Output("tc", "url"),
               Output("cbar", "colorscale"),
               Output("cbar", "min"),
               Output("cbar", "max"),
               Output("cbar", "unit")],
              [Input("map_values", "value"),
               Input("dd_cmap", "value"),
               Input("srng", "value")])
def update_url(param, cmap, srng):
    if not param or not cmap:
        return PreventUpdate
    srnga = [float(xx) for xx in srng]
    url = singleband_url(TC_URL, 'era5', PARAMS[param], colormap=cmap.lower(), stretch_range=srnga)
    print(url)
    return url, cmap.lower(), float(srnga[0]), float(srnga[1]), "°C"


@app.callback(Output("label", "children"), [Input("map", 'click_lat_lng'), Input("map_values", "value")])
def update_label(click_lat_lng, param):
    if not click_lat_lng:
        return "-"
    url = point_url(TC_URL, 'era5', PARAMS[param], lat=click_lat_lng[0], lon=click_lat_lng[1])
    data = json.load(urllib.request.urlopen(url))
    return "{:.3f} {}".format(float(data), "°C")


if __name__ == '__main__':
    app.run_server(port=8050)

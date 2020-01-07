import functools
import json

import pandas as pd
from flask import Flask, jsonify

# REST - WSGI + Flask
from waitress import serve

import config
import network_gen as nw
import tripdata_gen as tp

# Showing more columns
pd.set_option("display.max_columns", 100)

# Network
G = nw.load_network(config.graph_file_name, folder=config.root_path)
print(
    "# NETWORK -  NODES: {} ({} -> {}) -- #EDGES: {}".format(
        len(G.nodes()), min(G.nodes()), max(G.nodes()), len(G.edges())
    )
)

# Creating distance dictionary [o][d] -> distance
distance_dic = nw.get_distance_dic(config.path_dist_dic, G)

# Reachability dictionary
reachability_dict = nw.get_reachability_dic(
    config.path_reachability_dic,
    distance_dic,
    step=30,
    total_range=600,
    speed_km_h=30,
)
print(
    "\n############## DATA DESCRIPTION #######################################"
)

"""print("\mReading tripdata from '{}'".format(config.path_tripdata_ids))
df = pd.read_csv(config.path_tripdata_ids,
                 parse_dates=True,
                 index_col="pickup_datetime")

print(df.describe())
print(df.info())
print(df.head(10))
print(df.tail(10))
"""
app = Flask(__name__)


@app.route("/sp/<int:o>/<int:d>")
@functools.lru_cache(maxsize=1048576)
def sp(o, d):
    # print(sp.cache_info())
    # http://127.0.0.1:4999/sp/1/900
    return ";".join(map(str, nw.get_sp(G, o, d)))


@app.route("/can_reach/<int:n>/<int:t>")
@functools.lru_cache(maxsize=1048576)
def can_reach(n, t):
    """Return list of nodes that can reach node n in t seconds.
    
    Arguments:
        n {int} -- Node id
        t {int} -- time in seconds
    
    Returns:
        str -- List of nodes that can reach n in t seconds (separated by ";")
    """

    # print(can_reach.cache_info())
    # http://127.0.0.1:4999/can_reach/1/30
    # Result: 0;1;3720;3721;4112;3152;3092;1754;1309;928;929;1572;3623;
    #         3624;169;1897;1901;751;1841;308
    return ";".join(map(str, nw.get_can_reach_set(n, reachability_dict, t)))


@app.route("/sp_coords/<int:o>/<int:d>")
@functools.lru_cache(maxsize=1048576)
def sp_coords(o, d):
    # print(sp.cache_info())
    # http://127.0.0.1:/sp_coords/1/900
    return ";".join(map(str, nw.get_sp_coords(G, o, d)))


@app.route(
    "/linestring_style/<int:o>/<int:d>/<stroke>/<float:width>/<float:opacity>"
)
def linestring_style(o, d, stroke, width, opacity):
    # Color comes with %23 to replace #
    # http://127.0.0.1:4999/linestring_style/1/900/%23FF0000/2.0/1.0
    return jsonify(
        nw.get_linestring(
            G,
            o,
            d,
            **{
                "stroke": stroke,
                "stroke-width": width,
                "stroke-opacity": opacity,
            }
        )
    )


@app.route("/nodes")
def nodes():
    nodes = [
        {"id": id, "x": G.node[id]["x"], "y": G.node[id]["y"]}
        for id in G.nodes()
    ]
    dic = dict(nodes=nodes)
    return jsonify(dic)


@app.route("/point_style/<int:p>/<color>/<size>/<symbol>")
def point_style(p, color, size, symbol):
    # E.g.: http://127.0.0.1:4999/point_style/1/%23FF0000/small/circle
    return jsonify(
        nw.get_point(
            G,
            p,
            **{
                "marker-color": color,
                "marker-size": size,
                "marker-symbol": symbol,
            }
        )
    )


@app.route(
    "/point_info/<int:p>/<color>/<size>/<symbol>/<arrival>/<departure>/"
    "<passenger_count>/<vehicle_load>/<customer_class>"
)
def point_info(
    p,
    color,
    size,
    symbol,
    arrival,
    departure,
    passenger_count,
    vehicle_load,
    user_class,
):
    # E.g.: http://127.0.0.1:4999/point_style/1/%23FF0000/small/circle
    return jsonify(
        nw.get_point(
            G,
            p,
            **{
                "marker-color": color,
                "marker-size": size,
                "marker-symbol": symbol,
                "arrival": arrival,
                "departure": departure,
                "passenger-count": passenger_count,
                "vehicle-load": vehicle_load,
                "user-class": user_class,
            }
        )
    )


@app.route("/location/<int:id>")
def location(id):
    # http://127.0.0.1:4999/location/1
    return jsonify({"location": [G.node[id]["x"], G.node[id]["y"]]})

if __name__ == "__main__":

    serve(app, listen="*:4999")  # With WSGI
    # app.run(port='4999') # No  WSGI (only flask)

import config
import osmnx as ox
import network_gen as gen
from model.Vehicle import Vehicle
from model.Node import *
import tripdata_gen as tp
from datetime import datetime
from pprint import pprint
import sys


def main(args):
    print(args)
    G = gen.get_network_from(config.tripdata["region"],
                            config.root_path,
                            config.graph_name,
                            config.graph_file_name)


    #x.plot_graph(G)

    n_depots = int(args[0])
    depots = []

    n_requests = int(args[1])
    origins = []
    destinations = []
    ods = dict()

    # Creating depots
    for i in range(0,n_depots):
        node_id, lon, lat = gen.get_random_node(G)
        depot = Node.factory_node(Node.TYPE_DEPOT, lon, lat, network_node_id=node_id)
        depots.append(depot)

    # Creating ODs
    for r in range(0,n_requests):
        node_id, lon, lat = gen.get_random_node(G)
        o = Node.factory_node(Node.TYPE_ORIGIN, lon, lat, network_node_id=node_id)
        origins.append(o)

        node_id, lon, lat = gen.get_random_node(G)
        d = Node.factory_node(Node.TYPE_DESTINATION, lon, lat, network_node_id=node_id)
        destinations.append(d)

        ods[r] = (o,d)


    for o in origins:
        print(o)

    for d in destinations:
        print(d)

    pprint(ods)





    for depot in depots:
        print(depot)

    for o in origins:
        print(o)

    for d in destinations:
        print(d)

    pprint(ods)

if __name__ == "__main__":
    # #depots and #requests
    main(sys.argv[1:])


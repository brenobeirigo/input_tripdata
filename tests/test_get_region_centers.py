import os
import sys
from pprint import pprint

# Adding project folder to import config and network_gen
root = os.getcwd().replace("\\", "/")
sys.path.append(root)
sys.path.append('C:/Users/LocalAdmin/OneDrive/Phd_TU/PROJECTS/in/input_tripdata/')

pprint(sys.path)
import config
import network_gen as nw
import milp.ilp_reachability as ilp
import numpy as np

# Network
G = nw.load_network(config.graph_file_name, folder=config.root_path)
print("# NETWORK -  NODES: {} ({} -> {}) -- #EDGES: {}".format(
    len(G.nodes()),
    min(G.nodes()),
    max(G.nodes()),
    len(G.edges())))

# Creating distance dictionary [o][d] -> distance
distance_dic = nw.get_distance_dic(config.path_dist_dic, G)

# Creating reachability dictionary
# 30, 60, ..., 570, 600 (30s to 10min)
steps_sec = 30
total_sec=600
speed_km_h = 30

reachability_dic = nw.get_reachability_dic(
    config.path_reachability_dic,
    distance_dic,
    steps_sec=steps_sec,
    total_sec=total_sec,
    speed_km_h=speed_km_h)

region_centers = nw.get_region_centers(config.path_region_centers,
                                        reachability_dic,
                                        root_path = config.root_reachability,
                                        steps_sec=30,
                                        total_sec=600,
                                        speed_km_h=30)
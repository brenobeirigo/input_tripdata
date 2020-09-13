import json
import os
import sys
from datetime import datetime

# If defined, step and total_range are assumed to be seconds
speed_km_h = 60
MAX_VEHICLE_CAPACITY = 4

# Setup time limit (seconds)
TIME_LIMIT = 5 * 3600

# Experiment starts at
START_DATE = datetime.strptime("2011-02-01 18:00:00", "%Y-%m-%d %H:%M:%S")


print("SYS PATH:", sys.path)
print(os.listdir)

with open('config/config_mapdata.json') as js:
    mapdata = json.load(js)

# Create and store graph name
graph_file_name = mapdata["graph_file_name"]
graph_folder = mapdata["graph_folder"]
root_tripdata = mapdata["root_tripdata"]
tripdata_filename = mapdata["tripdata_filename"]
area_tripdata = mapdata["area_tripdata"]
tripdata_csv_path = root_tripdata + tripdata_filename
nodeset_gps_path = mapdata["nodeset_gps_path"]

with open(nodeset_gps_path) as js:
    nodeset_gps = json.load(js)["nodes"]

root_static_instances = mapdata["output_path"]
root_static_instances_experiments = root_static_instances + "/experiments"
root_static_instances_logs = root_static_instances + "/logs"

root_static_instances_lps = mapdata["mip_logs"]
static_instances_results_path = "{}/results.csv".format(root_static_instances)

path_dist_matrix = mapdata["path_dist_matrix"]
path_dist_dic = mapdata["path_dist_dic"]
path_reachability_dic = mapdata["path_reachability_dic"]
path_region_centers = mapdata["path_region_centers"]
path_tripdata = mapdata["path_tripdata"]

print("### LOADED INFO")
print(path_dist_matrix)
print(path_dist_dic)
print(path_reachability_dic)
print(path_region_centers)
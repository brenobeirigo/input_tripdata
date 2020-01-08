import os
import json
import sys
from datetime import datetime
from pprint import pprint
print("SYS PATH:", sys.path)
print(os.listdir)

def get_excerpt_name(start, stop):
    return "tripdata_excerpt_{}_{}".format(start, stop).replace(":", "").replace(" ", "_")

# Input data
tripdata = None
with open("config_tripdata/config_tripdata.json") as js:
    tripdata = json.load(js)
    #print("Trip data:")
    #pprint(tripdata)

# Config
db_connection = None
with open('config_tripdata/db_config.json') as js:
    db_connection = json.load(js)
    #print("\nDB connection data:")
    #pprint(db_connection)

# Create and store graph name
graph_name = tripdata["region"].lower().replace(" ", "-").replace(",", "")
graph_file_name = "{}.graphml".format(graph_name)

root_path = os.getcwd().replace("\\", "/")
data_path = root_path+"/data/{}".format(graph_name)
root_tripdata = data_path + "/tripdata"
root_dist = data_path + "/dist"

###### Reachability
# Reachability layers (e.g., reachable in 30, 60, ..., total_range steps)
step = 30 
total_range=600
# If defined, step and total_range are assumed to be seconds
speed_km_h = 30
MAX_VEHICLE_CAPACITY = 4

# Setup time limit (seconds)
TIME_LIMIT = 1800

# Experiment starts at
START_DATE = datetime.strptime("2011-02-01 00:00:00", "%Y-%m-%d %H:%M:%S")

root_reachability = data_path + "/reachability_{}_{}{}".format(step, total_range, ("_kmh{}".format(speed_km_h) if speed_km_h else ""))
root_static_instances = data_path + "/static_instances"

root_static_instances_experiments = root_static_instances + "/experiments"
root_static_instances_logs = root_static_instances + "/logs"
root_static_instances_lps = root_static_instances + "/ilps"
static_instances_results_path = "{}/results.csv".format(root_static_instances)

# Create and store graph name
graph_name = tripdata["region"].lower().replace(" ", "-").replace(",", "")

# Distance matrix
path_dist_matrix = "{}/distance_matrix_m_{}.csv".format(root_dist, graph_name)

# Distance dictionary (meters)
path_dist_dic = "{}/distance_dic_m_{}.npy".format(root_dist, graph_name)

# Reachability dictionary {o =  {max_dist =[d1, d2, d3]}
path_reachability_dic = "{}/reachability_{}.npy".format(root_reachability, graph_name)

# Region centers dictionary {max_dist = [c1, c2, c3, c4, c5]}
path_region_centers = "{}/region_centers_{}.npy".format(root_reachability, graph_name)

path_tripdata_ids = None
tripdata_filename = None
path_tripdata_source = None
path_tripdata = None
path_tripdata_clone = None
# Path of trip data with ids
if 'url_tripdata' in tripdata:
    
    excerpt_name = get_excerpt_name(
                            tripdata["start"],
                            tripdata["stop"]
                        )

    path_tripdata_ids = "{}/{}_ids.csv".format(root_tripdata,
                                            excerpt_name)

    # Presumably, the last part of the url is the file name
    tripdata_filename = tripdata["url_tripdata"].split("/")[-1]
    path_tripdata_source = "{}/{}".format(root_tripdata, tripdata_filename)

    path_tripdata = "{}/{}.csv".format(root_tripdata, excerpt_name)


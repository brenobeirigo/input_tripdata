import os
import network_gen as gen
import tripdata_gen as tp
import sys  # Reading arguments
import json
from pprint import pprint
import config


def main(calculate_dist=False):

    if not os.path.exists(config.root_path):
        os.makedirs(config.root_path)

    if not os.path.exists(config.root_dist):
        os.makedirs(config.root_dist)

    if not os.path.exists(config.root_tripdata):
        os.makedirs(config.root_tripdata)

    print("\nFolders: {}\n{}\n{}.".format(
        config.root_path,
        config.root_dist,
        config.root_tripdata))

    # Get network graph and save
    G = gen.get_network_from(config.tripdata["region"],
                             config.root_path,
                             config.graph_name,
                             config.graph_file_name)
    gen.save_graph_pic(G)


    # Creating distance dictionary [o][d] -> distance
    distance_dic = gen.get_distance_dic(config.path_dist_dic, G)

    # Creating distance matrix (n X n)
    distance_matrix = gen.get_distance_matrix(G, distance_dic)
    dt_distance_matrix = gen.get_dt_distance_matrix(
        config.path_dist_matrix, distance_matrix)

    print(dt_distance_matrix.describe())

    ################# Processing trip data ###################################

    # Try downloading the raw data if not exists
    tp.download_file(config.tripdata["url_tripdata"],
                     config.root_tripdata,
                     config.tripdata_filename)

    # Get excerpt (start, stop)
    dt_tripdata = tp.get_trip_data(config.path_tripdata_source,
                                   config.path_tripdata,
                                   config.tripdata["start"],
                                   config.tripdata["stop"])
    # Adding ids to data
    tp.add_ids(config.path_tripdata, config.path_tripdata_ids, G, distance_dic)


if __name__ == "__main__":

    # execute only if run as a script
    main()

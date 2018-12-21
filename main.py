import network_gen as gen
import tripdata_gen as tp
import sys  # Reading arguments

root_path = gen.os.getcwd().replace("\\", "/")+"/data"

def main(calculate_dist=False):

    # Input data
    region="Manhattan Island, New York City, New York, USA"
    tripdata_excerpt_name="tripdata_fev_2011"
    start="2011-2-1"
    stop="2011-2-28"

    print("Root folder: '{}'.".format(root_path))

    # Get network graph and save
    G = gen.get_network_from(root_path, region)
    gen.save_graph(G)
    print("#NODES: {} ({} -> {}) -- #EDGES: {}".format(len(G.nodes()),
                                                       min(G.nodes()),
                                                       max(G.nodes()),
                                                       len(G.edges())))

    # Get distance dictionary, matrix, and dataframe
    if calculate_dist:
        distance_dic = gen.get_distance_dic(G, root_path)
        distance_matrix = gen.get_distance_matrix(G, distance_dic)
        dt_distance_matrix = gen.get_dt_distance_matrix(
            G, distance_matrix, root_path)

    ################# Processing trip data ###################################
    tp.process_trip_data(root_path,tripdata_excerpt_name,
                         start, stop, G=G, cut=True)

if __name__ == "__main__":

    # execute only if run as a script
    main(calculate_dist=bool(sys.argv[0]))
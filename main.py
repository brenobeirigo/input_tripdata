import os
import network_gen as gen
from demand import tripdata_gen as tp
from pprint import pprint
import config


def main():
    print("############################### TRIP DATA SANDBOX ###############################")
    print("Creating trip data for '{}'.".format(config.tripdata["region"]))
    if "url_tripdata" in config.tripdata.keys():
        print("Using request interval from {} to {}.".format(
            config.tripdata["start"],
            config.tripdata["stop"]))
        

    # Create all folders where data will be saved
    if not os.path.exists(config.data_path):
        os.makedirs(config.data_path)

    if not os.path.exists(config.root_dist):
        os.makedirs(config.root_dist)

    if not os.path.exists(config.root_tripdata):
        os.makedirs(config.root_tripdata)
    
    if not os.path.exists(config.root_reachability):
        os.makedirs(config.root_reachability)

    if not os.path.exists(config.root_static_instances):
        os.makedirs(config.root_static_instances)
    
    if not os.path.exists(config.root_static_instances_logs):
        os.makedirs(config.root_static_instances_logs)
    
    if not os.path.exists(config.root_static_instances_lps):
        os.makedirs(config.root_static_instances_lps)

    print(("\n>>>>> Target folders:\n" +
          "\n - Distance matrix (csv) and dictionary (npy): {}" +
          "\n -   Data excerpt from NYC taxi dataset (csv): {}" +
          "\n -  Reachability (npy) & region centers (npy): {}.\n").format(
        config.root_dist,
        config.root_tripdata,
        config.root_reachability))

    # Get network graph and save
    G = gen.get_network_from(config.tripdata["region"],
                             config.data_path,
                             config.graph_name,
                             config.graph_file_name)
    
    
    gen.save_graph_pic(G, config.data_path)

    print( "\n####################### Getting distance data ####################### ")
    # Creating distance dictionary [o][d] -> distance
    distance_dic = gen.get_distance_dic(config.path_dist_dic, G)

    # Creating distance matrix (n X n) from dictionary
    distance_matrix = gen.get_distance_matrix(G, distance_dic)
    
    # Distance matrix as dataframe
    dt_distance_matrix = gen.get_dt_distance_matrix(
        config.path_dist_matrix,
        distance_matrix)
    
    # Dataframe info
    #print(dt_distance_matrix.describe())
   

    ################# Processing trip data ###################################
    if "url_tripdata" in config.tripdata.keys():
        
        print("####################### Processing trip data #######################")
        pprint(config.tripdata['url_tripdata'])

        # Try downloading the raw data if not exists (NY)
        tp.download_file(
            config.tripdata["url_tripdata"],
            config.root_tripdata,
            config.tripdata_filename)

        # Get excerpt (start, stop)
        print('Cleaning trip data...')
        dt_tripdata = tp.get_trip_data(
            config.path_tripdata_source,
            config.path_tripdata,
            config.tripdata["start"],
            config.tripdata["stop"])

        #  street network node ids (from G) to tripdata
        print('Adding ids...')
        tp.add_ids(
            config.path_tripdata,
            config.path_tripdata_ids,
            G,
            distance_dic)
        
    
    if 'data_gen' in config.tripdata:
        
        print(
            '\n#######################'
            ' Generating random data '
            '#######################'
        )
        
        print("Trip data generation settings:")
        pprint(config.tripdata['data_gen'])

        # Loop all generation function (e.g., clone, cluster)
        for random_func_name in config.tripdata['data_gen']['funcs']:
            
            if random_func_name == 'random_clone':
                
                data_gen_path_tripdata_ids = "{}/{}_{}_ids.csv".format(
                    config.root_tripdata,
                    random_func_name,
                    config.get_excerpt_name(
                        config.tripdata['data_gen']['start'],
                        config.tripdata['data_gen']['stop']
                    )
                )

                tp.gen_requests(
                    config.tripdata['data_gen']['source'],
                    config.tripdata['data_gen']['max_passenger_count'],
                    G,
                    data_gen_path_tripdata_ids,
                    start_timestamp = config.tripdata['data_gen']['start'],
                    end_timestamp = config.tripdata['data_gen']['stop'],
                    distance_dic = distance_dic
                )

    # Creating reachability dictionary
    reachability = gen.get_reachability_dic(config.path_reachability_dic,
                                            distance_dic,
                                            step=config.step,
                                            total_range=config.total_range,
                                            speed_km_h=config.speed_km_h)

    # Creating region centers for all max. travel durations
    # in reachability dictionary
    region_centers = gen.get_region_centers(config.path_region_centers,
                                            reachability,
                                            data_path= config.root_reachability,
                                            step=config.step,
                                            total_range=config.total_range,
                                            speed_km_h=config.speed_km_h)

if __name__ == "__main__":

    # execute only if run as a script
    main()

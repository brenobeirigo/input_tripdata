import network_gen as gen
import config

def is_reachable(o, d, reach_dic, max_trip_duration=150):

    trip_duration_list = sorted(list(reach_dic[d].keys()))
    for t in trip_duration_list:
        if t > max_trip_duration:
            break
        if o in reach_dic[d][t]:
            return True
    return False

if __name__ == "__main__":

    # Get network graph and save
    G = gen.get_network_from(config.tripdata["region"],
                                config.root_path,
                                config.graph_name,
                                config.graph_file_name)

    # Creating distance dictionary [o][d] -> distance
    distance_dic = gen.get_distance_dic(config.path_dist_dic, G)

    reach_dic = gen.get_reachability_dic("data/dist/reachability_manhattan-island-new-york-city-new-york-usa.npy", distance_dic)


    for o, targets in distance_dic.items():
        print(o, ["{} -{}".format(i, int(3.6*distance_dic[i][o]/30+0.5) ) for i in all_can_reach(o, reach_dic, max_trip_duration=150)])


    for o, targets in distance_dic.items():
        for d, dist in targets.items():
            if is_reachable(o,d, reach_dic, max_trip_duration=150):
                
                print(o,d, dist, int(3.6*dist/30+0.5), is_reachable(o,d, reach_dic, max_trip_duration=150))
    
    #print("Reachability dictionary:", reach_dic)
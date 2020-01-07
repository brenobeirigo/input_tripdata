import os
import sys

# Adding project folder
root = os.getcwd().replace("\\", "/")
sys.path.append(root)

import config
import network_gen as gen
from milp.ilp_reachability import can_reach

if __name__ == "__main__":

    # Max trip time to test reachability dictionary
    MAX_TRIP_TIME = 180


    # Get network graph and save
    G = gen.get_network_from(config.tripdata["region"],
                                config.root_path,
                                config.graph_name,
                                config.graph_file_name)

    # Creating distance dictionary [o][d] -> distance
    distance_dic = gen.get_distance_dic(config.path_dist_dic, G)
    
    # Try to load from path, if does't exist generate
    reachability_dic = gen.get_reachability_dic(
        config.path_reachability_dic,
        distance_dic
    )

    # Check which nodes can reach target in less than "MAX_TIME" seconds
    for target, origin_dic in distance_dic.items():
        for origin, distance_meters in origin_dic.items():

            origin_can_reach_target = can_reach(
                target, origin, MAX_TRIP_TIME, reachability_dic
            )

            distance_seconds = int(3.6*distance_meters/config.speed_km_h + 0.5)

            if origin_can_reach_target:
                pass
                # print(
                #     ("{o:>4} - {t:>4} ({m:>8.2f}m = {s:>3}s)"
                #     "   REACHABLE").format(
                #         t = target,
                #         o = origin,
                #         m = distance_meters,
                #         s = distance_seconds
                #     )
                # )

            elif distance_seconds <= MAX_TRIP_TIME:
                print(
                    ("{o:>4} - {t:>4} ({m:>8.2f}m = {s:>3}s)"
                    "   ERROR! CAN REACH BUT NOT IN DICTIONARY!").format(
                        t = target,
                        o = origin,
                        m = distance_meters,
                        s = distance_seconds
                    )
                )

    
    #print("Reachability dictionary:", reachability_dic)
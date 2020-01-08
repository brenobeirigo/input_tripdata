import os
import sys
import matplotlib.pyplot as plt
from collections import Counter
import osmnx as ox
import networkx as nx

# Adding project folder
root = os.getcwd().replace("\\", "/")
sys.path.append(root)


import config
import network_gen as gen
from milp.ilp_reachability import ilp_node_reachability

if __name__ == "__main__":

    # Max trip time to test reachability dictionary
    MAX_TRIP_TIME = 180

    # Get network graph and save
    G = gen.get_network_from(config.tripdata["region"],
                             config.data_path,
                             config.graph_name,
                             config.graph_file_name)

    # Creating distance dictionary [o][d] -> distance
    distance_dic = gen.get_distance_dic(config.path_dist_dic, G)

    # Try to load from path, if does't exist generate
    reachability_dic = gen.get_reachability_dic(
        config.path_reachability_dic,
        distance_dic
    )

    min_center_set = ilp_node_reachability(
        reachability_dic, max_delay=MAX_TRIP_TIME, log_path=root+'/tests'
    )

    print(min_center_set)

    # From how many centers each origin can be reached?
    center_count_per_origin_dict = {o: 0 for o in distance_dic.keys()}

    # How many origins each center can reach?
    nodes_per_center_dict = {c: 0 for c in min_center_set}
    center_route_cluster =  {c: list() for c in min_center_set}

    # Check which nodes can reach target in less than "MAX_TIME" seconds
    for origin in distance_dic.keys():
        for center in min_center_set:

            distance_meters = distance_dic[center][origin]

            distance_seconds = int(3.6*distance_meters/config.speed_km_h + 0.5)

            if (distance_seconds <= MAX_TRIP_TIME):

                nodes_per_center_dict[center] += 1
                center_count_per_origin_dict[origin] += 1
                center_route_cluster[center].append(
                    gen.get_sp(G, center, origin)
                )

                # print(
                #     ("{o:>4} - {t:>4} ({m:>8.2f}m = {s:>3}s)"
                #      "   CAN REACH!").format(
                #         t=target,
                #         o=origin,
                #         m=distance_meters,
                #         s=distance_seconds
                #     )
                # )
    
    y = list(center_count_per_origin_dict.values())
    count = Counter(y)
    x, y = zip(*count.items())
    plt.title("Number of nodes per number of reachable region centers")
    plt.xlabel("Number of reachable region centers")
    plt.ylabel("Number of nodes")
    plt.bar(x,y)
    plt.show()
    

    centers = sorted([(v,k) for k,v in nodes_per_center_dict.items()])
    y, x = zip(*centers)
    xticks = range(0, len(min_center_set))
    plt.bar(xticks ,y)
    plt.xticks(xticks, x)
    plt.title("Number of reachable nodes per center")
    plt.xlabel("Center ID")
    plt.ylabel("Number reachable of nodes")
    plt.show()

    # Print all reachable nodes by center
    for cluster, routes in center_route_cluster.items():
        fig, ax = ox.plot_graph_routes(
            G,
            routes, 
            route_linewidth=1,
            fig_height=10,
            node_size=4,
            orig_dest_node_size=6,
            save=True,
            show = False,
            filename = "{}/tests/image/center_id_{:06}_reachable_{:06}".format(
                root,
                cluster,
                len(routes)
            )
        )
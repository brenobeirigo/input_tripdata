from pprint import pprint
import random
from datetime import timedelta, datetime
import json
import config
import network_gen as nw
import tripdata_gen as tp
from model.Request import Request
from model.Node import Node, NodePK, NodeDL, NodeDepot
from model.Vehicle import Vehicle
import milp.darp_sq as sq
import os
import sys
root = os.getcwd().replace("\\", "/")
sys.path.append(root)


# Adding project folder to import config and network_gen
def get_n_requests(n, service_quality_dict, customer_segmentation_dict):
    requests = []
    user_classes = list(service_quality_dict.keys())
    df = tp.get_next_batch(
        "TESTE1",
        chunk_size=2000,
        batch_size=30,
        # tripdata_csv_path="D:/bb/sq/data/delft-south-holland-netherlands/tripdata/random_clone_tripdata_excerpt_2011-02-01_000000_2011-02-02_000000_ids.csv",
        start_timestamp="2011-02-01 00:00:00",
        end_timestamp="2011-02-01 00:01:00",
        classes=user_classes,
        freq=[customer_segmentation_dict[k] for k in user_classes],
    )

    while df is not None:
        df = tp.get_next_batch("TESTE1")

        if not df.empty:
            for row in df.itertuples():

                r = Request(
                    row.Index,
                    service_quality_dict[row.service_class]["pk_delay"],
                    service_quality_dict[row.service_class]["trip_delay"],
                    row.pk_id,
                    row.dp_id,
                    row.passenger_count,
                    pickup_latitude=row.pickup_latitude,
                    pickup_longitude=row.pickup_longitude,
                    dropoff_latitude=row.dropoff_latitude,
                    dropoff_longitude=row.dropoff_longitude,
                    service_class=row.service_class,
                    service_duration=0,
                )

                requests.append(r)

                if len(requests) == n:
                    return requests


def get_list_of_vehicles_in_region_centers(
        max_capacity,
        G,
        start_datetime,
        list_of_region_centers,
        list_of_nodes_to_reach,
        max_delay,
        reachability_dict,
        distance_dict):

    vehicle_list = []

    for node_to_reach in list_of_nodes_to_reach:
        set_centers_can_reach = set(list_of_region_centers).intersection(
            nw.get_can_reach_set(
                node_to_reach.network_node_id,
                reachability_dict,
                max_trip_duration=max_delay,
            )
        )

        # Choose a center randomly to access the origin
        random_center_id = random.choice(list(set_centers_can_reach))
        lon, lat = nw.get_coords_node(random_center_id, G)

        print("\nVehicles in ", random_center_id, ":")
        # Create vehicles of different capacities in this center
        # for capacity in range(node_to_reach.parent.demand, max_capacity + 1):
        for capacity in range(max_capacity, max_capacity + 1):

            # Creating vehicle origin node
            depot_node = Node.factory_node(
                Node.TYPE_DEPOT, lon, lat, network_node_id=random_center_id
            )

            v = Vehicle(depot_node, capacity, start_datetime)
            print("Vehicle", v)

            dist_m = distance_dict[depot_node.network_node_id][
                node_to_reach.network_node_id
            ]
            dist_seconds = int(3.6 * dist_m / 30 + 0.5)
            print("  -", v.pid, dist_seconds)

            vehicle_list.append(v)

        print(
            "Can reach node: {}({})".format(
                node_to_reach.pid, node_to_reach.parent.demand
            )
        )
    return vehicle_list


def get_n_vehicles(n, capacity, G, start_datetime):
    vehicle_list = []

    for _ in range(0, n):

        # Getting random node info
        id, lon, lat = nw.get_random_node(G)

        # Creating vehicle origin node
        o = Node.factory_node(Node.TYPE_DEPOT, lon, lat, network_node_id=id)

        v = Vehicle(o, capacity, start_datetime)

        vehicle_list.append(v)

    return vehicle_list


def run_milp():
    # Request config
    REQUESTS = 10

    MAX_VEHICLE_CAPACITY = 4
    SPEED_KM_H = 30

    # Experiment starts at
    START_DATE = datetime.strptime("2011-02-01 00:00:00", "%Y-%m-%d %H:%M:%S")

    # Setup time limit (seconds)
    TIME_LIMIT = 3600

    # Operational scenario
    SCENARIO_FILE_PATH = (
        "D:/bb/sq/scenario/"
        "week/allow_hiring.json"
    )

    # Reading scenario from file
    with open(SCENARIO_FILE_PATH) as js:

        scenario = json.load(js)

    # Share of each class in customer base
    customer_segmentation_dict = scenario["scenario_config"][
        "customer_segmentation"
    ]["BB"]

    print("### CUSTOMER SEGMENTATION SCENARIO")
    pprint(customer_segmentation_dict)

    # Service quality dict

    service_quality_dict = {
        "A": {"pk_delay": 1800, "sharing_preference": 0, "trip_delay": 1800},
        "B": {"pk_delay": 3000, "sharing_preference": 1, "trip_delay": 6000},
        "C": {"pk_delay": 6000, "sharing_preference": 1, "trip_delay": 9000},
    }

    service_quality_dict = scenario["scenario_config"]["service_level"]

    print("### SERVICE QUALITY SCENARIO")
    pprint(service_quality_dict)

    # Service rate
    service_rate = scenario["scenario_config"]["service_rate"]["S2"]
    print("### SERVICE RATE SCENARIO")
    pprint(service_rate)

    # Getting network
    G = nw.get_network_from(
        config.tripdata["region"],
        config.root_path,
        config.graph_name,
        config.graph_file_name,
    )

    # Creating distance dictionary [o][d] -> distance
    distance_dic = nw.get_distance_dic(config.path_dist_dic, G)

    # Getting requests
    requests = get_n_requests(
        REQUESTS, service_quality_dict, customer_segmentation_dict
    )

    # The reachability dictionary
    reachability = nw.get_reachability_dic(
        config.path_reachability_dic,
        distance_dic,
        step=config.step,
        total_range=config.total_range,
        speed_km_h=config.speed_km_h,
    )

    print("### REACHABILITY")

    # Region centers
    region_centers = nw.get_region_centers(
        config.path_region_centers,
        reachability
    )

    print("### REGION CENTERS")

    # Get the lowest pickup delay from all user class
    # Vehicles have to be able to access all nodes within the minimum delay
    lowest_delay = min(
        [params["pk_delay"] for params in service_quality_dict.values()]
    )

    print(
        "\nRegion centers (maximum pickup delay of {} seconds)".format(
            lowest_delay
        )
    )
    pprint(region_centers[lowest_delay])

    # Getting vehicles
    # vehicles = get_n_vehicles(
    #     VEHICLES, MAX_VEHICLE_CAPACITY, G, START_DATE
    # )

    # Initialize vehicles in region centers
    vehicles = get_list_of_vehicles_in_region_centers(
        MAX_VEHICLE_CAPACITY,
        G,
        START_DATE,
        region_centers[lowest_delay],
        Node.origins,
        lowest_delay,
        reachability,
        distance_dic
    )

    # Dictionary of viable connections (and distances) between vehicle
    # and request nodes. E.g.: viable_nw[NodeDP][NodePK] = DIST_S
    travel_time_dict = sq.get_viable_network(
        Node.depots,
        Node.origins,
        Node.destinations,
        Request.node_pairs_dict,
        distance_dic,
        speed=SPEED_KM_H,
    )

    # Requests
    print("Requests")
    for r in requests:
        print(r.get_info())

    # Creating vehicles
    print("Vehicles")
    for v in vehicles:
        print(
            v.get_info(),
            [
                "{}[#Passengers:{}]({})".format(
                    o.pid, o.parent.demand, travel_time_dict[v.pos][o]
                )
                for o, dist in travel_time_dict[v.pos].items()
                if dist < lowest_delay
            ],
        )

    print("#ODS:", len(Request.od_set))
    print("#DEPOTS:", len(Node.depots))
    print("#ORIGINS:", len(Node.origins))
    print("#DESTINATIONS:", len(Node.destinations))

    print("All pick up points can be accessed by")
    for origin in Node.origins:
        list_accessible_vehicles = []
        for depot_node in Node.depots:

            try:
                if travel_time_dict[depot_node][origin] <= lowest_delay:
                    list_accessible_vehicles.append(depot_node.parent)
            except KeyError:
                pass
        print(
            "Origin {} can be accessed by {} vehicles".format(
                origin, len(list_accessible_vehicles)
            )
        )

    print("### VIABLE NETWORK")
    for n1, target_dict in travel_time_dict.items():
        print(n1)
        for n2, dist in target_dict.items():
            print("   ", n2, dist)

    # Get earliest and latest times for each node
    node_timewindow_dict = sq.get_node_tw_dic(
        vehicles, requests, travel_time_dict
    )

    # Updating earliest and latest times (in seconds) for each node
    for current_node, tw in node_timewindow_dict.items():
        earliest, latest = tw
        current_node.earliest = (earliest - START_DATE).total_seconds()
        current_node.latest = (latest - START_DATE).total_seconds()

    print("### NODE TIME WINDOWS")
    for current_node, tw in node_timewindow_dict.items():
        print(current_node, tw, current_node.demand)

    objective_order = [
        sq.TOTAL_FLEET_CAPACITY,
        sq.TOTAL_PICKUP_DELAY,
        sq.TOTAL_RIDE_DELAY,
    ]

    sq.milp_sq_class(
        vehicles,
        requests,
        travel_time_dict,
        service_quality_dict,
        service_rate,
        objective_order,
        TIME_LIMIT,
        START_DATE,
    )


if __name__ == "__main__":
    run_milp()

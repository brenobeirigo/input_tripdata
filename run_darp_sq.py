import json
import os
from datetime import timedelta, datetime
from pprint import pprint
import random
random.seed(1)
from collections import namedtuple
from collections import defaultdict
import pandas as pd
import numpy as np

import logging

logger = logging.getLogger("run_experiment")
logger.setLevel(logging.DEBUG)

import config
import network_gen as nw
import tripdata_gen as tp
from model.Request import Request
from model.Node import Node, NodePK, NodeDL, NodeDepot
from model.Vehicle import Vehicle

import milp.darp_sq as sq


def get_n_requests(n, service_quality_dict, customer_segmentation_dict):
    requests = []
    user_classes = list(service_quality_dict.keys())
    df = tp.get_next_batch(
        "TESTE1",
        chunk_size=2000,
        batch_size=30,
        tripdata_csv_path="D:/bb/sq/data/delft-south-holland-netherlands/tripdata/random_clone_tripdata_excerpt_2011-02-01_000000_2011-02-02_000000_ids.csv",
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


def get_instances_from_folder(folder):
    print(f'Reading instances from folder "{folder}"...')
    Instance = namedtuple(
        "Instance",
        [
            "file",
            "file_path",
            "base_name",
            "area",
            "demand_size",
            "user_base",
            "class_freq_pairs",
            "id_instance",
            "passenger_count",
            "group_id",
        ],
    )
    instance_list = []

    for file in os.listdir(folder):
        print(f'Processing instance "{file}"')

        file_path = "{}/{}".format(folder, file)

        # Removing extension
        base_name = file[:-4]

        # Get instance info from file path
        area, demand_size, user_base_label, class_freq, id_instance, passenger_count = base_name.split(
            "__"
        )
        class_freq_pairs = [tuple(pair.split("-")) for pair in class_freq.split("_")]

        group_id = "{}_{}".format(demand_size, user_base_label)

        instance_list.append(
            Instance(
                file,
                file_path,
                base_name,
                area,
                demand_size,
                user_base_label,
                class_freq_pairs,
                id_instance,
                passenger_count,
                group_id,
            )
        )

    return instance_list


def get_list_of_vehicles_in_region_centers(
    max_capacity,
    G,
    start_datetime,
    list_of_region_centers,
    list_of_nodes_to_reach,
    max_delay,
    reachability_dict,
    distance_dict,
    fixed_capacity=False,
):

    vehicle_list = []
    logger.info(">>> List of nodes to reach:")
    logger.info("#Nodes to reach: {}".format(len(list_of_nodes_to_reach)))

    for node_to_reach in list_of_nodes_to_reach:
        set_centers_can_reach = set(list_of_region_centers).intersection(
            nw.get_can_reach_set(
                node_to_reach.network_node_id,
                reachability_dict,
                max_trip_duration=max_delay,
            )
        )
        logger.info("#Region centers: {}".format(len(set_centers_can_reach)))

        # Choose a center randomly to access the origin
        random.seed(1)
        random_center_id = random.choice(list(set_centers_can_reach))
        lon, lat = nw.get_coords_node(random_center_id, G)

        logger.info("Region center: {}".format(random_center_id))
        logger.info(
            "Can reach node: {}(Demand: {})".format(
                node_to_reach.pid, node_to_reach.parent.demand
            )
        )
        logger.info(
            "{ruler}\n{v:>10} | {d:<12}\n{ruler}".format(
                ruler="=" * 25, v="Vehicle", d="Distance(s)"
            )
        )

        # Create vehicles of different capacities in this center for
        # capacity in range(request demand, max capacity + 1).
        # This way, all vehicles starting in an origin can service the
        # demand (capacity wise)
        min_capacity = (
            node_to_reach.parent.demand if not fixed_capacity else max_capacity
        )
        # min_capacity = max_capacity
        for capacity in range(min_capacity, max_capacity + 1):

            # Creating vehicle origin node
            depot_node = Node.factory_node(
                Node.TYPE_DEPOT, lon, lat, network_node_id=random_center_id
            )

            v = Vehicle(depot_node, capacity, start_datetime)

            dist_m = distance_dict[depot_node.network_node_id][
                node_to_reach.network_node_id
            ]
            dist_seconds = int(3.6 * dist_m / 30 + 0.5)
            logger.info("{:>10} | {:<12}".format(v.pid, dist_seconds))

            vehicle_list.append(v)

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


def config_log(logger, log_file_path):

    for hdlr in logger.handlers[:]:  # remove all old handlers
        logger.removeHandler(hdlr)

    # create file handler which logs even debug messages
    fh = logging.FileHandler(log_file_path, mode="w")
    fh.setLevel(logging.DEBUG)

    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)

    # create formatter and add it to the handlers
    # formatter = logging.Formatter(
    #     "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    # )

    formatter = logging.Formatter("%(message)s")
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)


def run_milp():

    if not os.path.exists(config.root_static_instances_experiments):
        os.makedirs(config.root_static_instances_experiments)

    if not os.path.exists(config.root_static_instances_logs):
        os.makedirs(config.root_static_instances_logs)

    if not os.path.exists(config.root_static_instances_lps):
        os.makedirs(config.root_static_instances_lps)

    # Hierarchical objective function (most important first)
    objective_function_order = [
        sq.TOTAL_FLEET_CAPACITY,
        sq.TOTAL_DELAY,
        #sq.TOTAL_RIDE_DELAY,
        #sq.TOTAL_PICKUP_DELAY,
    ]

    # Operational scenario
    SCENARIO_FILE_PATH = config.root_path + "/scenario/week/allow_hiring.json"

    # Reading scenario from file
    with open(SCENARIO_FILE_PATH) as js:
        scenario = json.load(js)

        # Share of each class in customer base
        customer_segmentation_dict = scenario["scenario_config"]["customer_segmentation"][
            "BB"
        ]

        print("### CUSTOMER SEGMENTATION SCENARIO")
        pprint(customer_segmentation_dict)

        # Service quality dict
        service_quality_dict = scenario["scenario_config"]["service_level"]

        print("### SERVICE QUALITY SCENARIO")
        pprint(service_quality_dict)

        # Service rate
        service_rate = scenario["scenario_config"]["service_rate"]["S2"]
        print("### SERVICE RATE SCENARIO")
        pprint(service_rate)

    # ******************************************************************
    # ******************************************************************
    # ** Loading map data **********************************************
    # ******************************************************************
    # ******************************************************************

    # Getting network
    G = nw.get_network_from(
        config.tripdata["region"],
        config.data_path,
        config.graph_name,
        config.graph_file_name,
    )

    # Creating distance dictionary [o][d] -> distance
    distance_dic = nw.get_distance_dic(config.path_dist_dic, G)

    # The reachability dictionary
    reachability = nw.get_reachability_dic(
        config.path_reachability_dic,
        distance_dic,
        step=config.step,
        total_range=config.total_range,
        speed_km_h=config.speed_km_h,
    )

    # Region centers
    region_centers = nw.get_region_centers(config.path_region_centers, reachability)

    # ******************************************************************
    # ******************************************************************
    # ** Reading instance data *****************************************
    # ******************************************************************
    # ******************************************************************

    # Process all instance files in folder
    instance_list = get_instances_from_folder(config.root_static_instances_experiments)

    # Stop execution after max_number_instances is reached
    max_number_instances = None

    # Add a feature label to logs such that files can be compared
    feature_label = None

    list_processed_instances = list()
    # Try to read instances already processed
    if os.path.isfile(config.static_instances_results_path):
        try:
            df_results = pd.read_csv(config.static_instances_results_path)
            list_processed_instances = [i for i in df_results["instance"].values]
        except Exception as e:
            print(f"Results is empty. Removing to start clean... {e}")
            os.remove(config.static_instances_results_path)

    sq_paper = {
        "A": {"pk_delay": 180, "sharing_preference": 0, "trip_delay": 180},
        "B": {"pk_delay": 300, "sharing_preference": 1, "trip_delay": 600},
        "C": {"pk_delay": 600, "sharing_preference": 1, "trip_delay": 900},
    }

    sq_baseline_2 = {
        "A": {"pk_delay": 360, "sharing_preference": 0, "trip_delay": 360},
        "B": {"pk_delay": 600, "sharing_preference": 1, "trip_delay": 900},
        "C": {"pk_delay": 1200, "sharing_preference": 1, "trip_delay": 1500},
    }

    sr_paper = {"A": 0.9, "B": 0.8, "C": 0.7}

    sr_baseline_1 = {"A": 1, "B": 1, "C": 1}
    sr_baseline_2 = {"A":1, "B": 1, "C": 1}

    # Test lower and upper end for service rates
    tests = {
        "slevels": (sq_paper, sr_paper),
        "baseline_1": (sq_paper, sr_baseline_1),
        "baseline_2": (sq_baseline_2, sr_baseline_2),
    }


    # Get the lowest pickup delay from all user class
    # Vehicles have to be able to access all nodes within the
    # minimum delay
    minimum_delay = 180

    logger.info(
        "Region centers (maximum pickup delay of {} seconds):".format(minimum_delay)
    )
    pprint(region_centers[minimum_delay])

    pprint(list_processed_instances)
    
    for i, instance in enumerate(instance_list):
        for test_label, (sq_dict, sr_dict) in tests.items():

            instance_label = f"{test_label}__{instance.base_name}"

            if instance_label in list_processed_instances:
                print("Instance '{}' already processed.".format(instance.base_name))
                continue
            
            # Stop reading instaces after max number is reached
            if max_number_instances and i >= max_number_instances:
                break

            print(f">>>>>>>>> {test_label} - {instance.base_name}")

            print("### SERVICE QUALITY SCENARIO")
            pprint(sq_dict)

            print("### SERVICE RATE SCENARIO")
            pprint(sr_dict)

            
            # Where to save solution log
            log_file_path = "{folder}/{test_label}__{basename}{feature}.log".format(
                folder=config.root_static_instances_logs,
                test_label=test_label,
                basename=instance.base_name,
                feature=(feature_label if feature_label else ""),
            )

            # Add loggger handle
            config_log(logger, log_file_path)

            logger.info("#### Saving in '{}'".format(log_file_path))
            # Read instance file and according to the user classes, assign
            # the delays in the service_quality_dict
            requests = Request.get_request_list(
                instance.file_path, sq_dict
            )

            # Requests
            logger.info("Requests")
            for r in requests:
                logger.info(r.get_info())


            # Initialize vehicles in region centers
            vehicles = get_list_of_vehicles_in_region_centers(
                config.MAX_VEHICLE_CAPACITY,
                G,
                config.START_DATE,
                region_centers[minimum_delay],
                Node.origins,
                minimum_delay,
                reachability,
                distance_dic,
                fixed_capacity=True,
            )

            # Dictionary of viable connections (and distances) between
            # vehicle and request nodes.
            # E.g.: viable_nw[NodeDP][NodePK] = DIST_S
            travel_time_dict = sq.get_viable_network(
                Node.depots,
                Node.origins,
                Node.destinations,
                Request.node_pairs_dict,
                distance_dic,
                speed=config.speed_km_h,
            )

            # Creating vehicles
            # print("Vehicles")
            # for v in vehicles:
            #     print(
            #         v.get_info(),
            #         [
            #             "{}[#Passengers:{}]({})".format(
            #                 o.pid, o.parent.demand, travel_time_dict[v.pos][o]
            #             )
            #             for o, dist in travel_time_dict[v.pos].items()
            #             if dist < minimum_delay
            #         ],
            #     )

            logger.info(
                "#ODS:{} | #DEPOTS:{} | #ORIGINS:{} | #DESTINATIONS:{}".format(
                    len(Request.od_set),
                    len(Node.depots),
                    len(Node.origins),
                    len(Node.destinations),
                )
            )

            logger.info("#### All pick up points can be accessed by")
            for origin in Node.origins:
                list_accessible_vehicles = []
                for depot_node in Node.depots:

                    try:
                        if travel_time_dict[depot_node][origin] <= minimum_delay:
                            list_accessible_vehicles.append(depot_node.parent)
                    except KeyError:
                        pass
                logger.info(
                    "Origin {} can be accessed by {} vehicles".format(
                        origin, len(list_accessible_vehicles)
                    )
                )

            # print("### VIABLE NETWORK")
            # for n1, target_dict in travel_time_dict.items():
            #     print(n1)
            #     for n2, dist in target_dict.items():
            #         print("   ", n2, dist)

            # Get earliest and latest times for each node
            node_timewindow_dict = sq.get_node_tw_dic(
                vehicles, requests, travel_time_dict
            )

            # Updating earliest and latest times (in seconds) for each node
            for current_node, tw in node_timewindow_dict.items():
                earliest, latest = tw
                current_node.earliest = (earliest - config.START_DATE).total_seconds()
                current_node.latest = (latest - config.START_DATE).total_seconds()

            # Save model at
            milp_lp = "{}/{}__{}.log".format(
                config.root_static_instances_lps, test_label, instance.base_name
            )

            # Save log at
            milp_log = "{}/{}__{}.log".format(
                config.root_static_instances_lps, test_label, instance.base_name
            )

            # Run MILP for current instance
            result_dict = sq.milp_sq_class(
                vehicles,
                requests,
                travel_time_dict,
                sq_dict,
                sr_dict,
                objective_function_order,
                config.TIME_LIMIT,
                config.START_DATE,
                log_path=milp_log,
                lp_path=milp_lp,
            )

            # **************************************************************
            # **************************************************************
            # ** Saving overal results *************************************
            # **************************************************************
            # **************************************************************

            sol = {
                "test": test_label,
                "instance": instance_label,
                "passenger_count": instance.passenger_count,
                "id_instance": instance.id_instance,
                "demand_size": int(instance.demand_size),
                "group_id": instance.group_id,
                "max_vehicle_capacity": config.MAX_VEHICLE_CAPACITY,
                "fleet_size": len(vehicles),
                "total_capacity": sum([v.capacity for v in vehicles]),
                "user_base": instance.user_base,
                "objective_function": "__".join(objective_function_order),
            }

            # TODO solution is empty
            if result_dict:

                # Makes sure all possible capacities are considered, even when
                # the solution does not include a possible capacity in the
                # capacity range
                capacity = {i: 0 for i in range(1, config.MAX_VEHICLE_CAPACITY + 1)}
                capacity = {**capacity, **result_dict["capacity_count"]}
                capacity_count = {
                    "capacity_{:02}".format(capacity): count
                    for capacity, count in capacity.items()
                }

                # Pull all objective functions considered
                sol_objs = {
                    "{}_obj_val".format(k): int(v["obj_val"])
                    for k, v in result_dict["objective_functions"].items()
                }

                mipgap_objs = {
                    "{}_obj_mip_gap".format(k): float(v["obj_mip_gap"])
                    for k, v in result_dict["objective_functions"].items()
                }

                runtime = {"run_time": "{}".format(float(result_dict["runtime"]))}


                r_info_mean = dict()
                r_info_sum = {
                    "total": 0,
                    "total_delay": 0,
                    "total_pk_delay": 0,
                    "total_ride_delay": 0,
                    "tier_1": 0,
                    "tier_2": 0,
                    "tier_1_pk_delay_sum": 0,
                    "tier_2_pk_delay_sum": 0,
                    "tier_1_ride_delay_sum": 0,
                    "tier_2_ride_delay_sum": 0,
                }
                for sq_label in sq_dict.keys():
                    r_info_mean[f"pk_delay_mean_{sq_label}"] = list()
                    r_info_sum[f"pk_delay_sum_{sq_label}"] = 0
                    r_info_mean[f"ride_delay_mean_{sq_label}"] = list()
                    r_info_sum[f"ride_delay_sum_{sq_label}"] = 0
                    r_info_sum[f"tier_1_{sq_label}"] = 0
                    r_info_sum[f"tier_1_pk_delay_sum_{sq_label}"] = 0
                    r_info_sum[f"tier_1_ride_delay_sum_{sq_label}"] = 0
                    r_info_sum[f"tier_2_{sq_label}"] = 0
                    r_info_sum[f"tier_2_pk_delay_sum_{sq_label}"] = 0
                    r_info_sum[f"tier_2_ride_delay_sum_{sq_label}"] = 0
                    r_info_sum[f"total_{sq_label}"] = 0
                    r_info_sum[f"total_pk_delay_{sq_label}"] = 0
                    r_info_sum[f"total_ride_delay_{sq_label}"] = 0

                for r in requests:
                    r_info_mean[f"pk_delay_mean_{r.service_class}"].append(r.pk_delay)
                    r_info_mean[f"ride_delay_mean_{r.service_class}"].append(
                        r.ride_delay
                    )
                    r_info_sum[f"tier_{r.tier}_{r.service_class}"] += 1
                    r_info_sum[f"tier_{r.tier}"] += 1
                    r_info_sum[f"pk_delay_sum_{r.service_class}"] += r.pk_delay
                    r_info_sum[f"ride_delay_sum_{r.service_class}"] += r.ride_delay
                    r_info_sum[
                        f"tier_{r.tier}_pk_delay_sum_{r.service_class}"
                    ] += r.pk_delay
                    r_info_sum[
                        f"tier_{r.tier}_ride_delay_sum_{r.service_class}"
                    ] += r.ride_delay
                    r_info_sum[f"tier_{r.tier}_pk_delay_sum"] += r.pk_delay
                    r_info_sum[f"tier_{r.tier}_ride_delay_sum"] += r.ride_delay
                    r_info_sum[f"total_pk_delay_{r.service_class}"] += r.pk_delay
                    r_info_sum[f"total_ride_delay_{r.service_class}"] += r.ride_delay
                    r_info_sum[f"total_{r.service_class}"] += 1
                    r_info_sum[f"total"] += 1
                    r_info_sum[f"total_ride_delay"] += r.ride_delay
                    r_info_sum[f"total_pk_delay"] += r.pk_delay
                    r_info_sum[f"total_delay"] += r.pk_delay + r.ride_delay

                r_info = dict(r_info_sum)
                for k, v in r_info_mean.items():
                    r_info[k] = np.mean(v)

                df_r = pd.DataFrame([pd.Series(r_info)])
                df_r.sort_index(axis=1, inplace=True)

                sol = {**sol, **runtime, **sol_objs, **mipgap_objs, **capacity_count}

            df = pd.DataFrame([pd.Series(sol)])
            df = pd.concat([df, df_r], axis=1)
            print(df)

            # Add instance info to the end of the results.csv file in case
            # it already exists. Otherwise, create file first.
            if not os.path.isfile(config.static_instances_results_path):
                df.to_csv(
                    config.static_instances_results_path,
                    header=True,
                    mode="w",
                    index=False,
                )
            else:
                print("SAVING", instance)
                df.to_csv(
                    config.static_instances_results_path,
                    header=False,
                    mode="a",
                    index=False,
                )

            # Clear the environment for the next instance
            Node.reset_elements()
            Request.reset_elements()
            Vehicle.reset_elements()


if __name__ == "__main__":
    run_milp()

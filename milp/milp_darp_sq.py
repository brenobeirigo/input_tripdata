import os
import sys
from pprint import pprint

# Adding project folder to import config and network_gen
root = os.getcwd().replace("\\", "/")
sys.path.append(root)

import numpy as np
import json
from collections import defaultdict
from datetime import timedelta, datetime
from pprint import pprint
import random
random.seed(1)
from gurobipy import Model, GurobiError, GRB, quicksum


import config
import network_gen as nw
import tripdata_gen as tp

from model.Request import Request
from model.Node import Node, NodePK, NodeDL, NodeDepot
from model.Vehicle import Vehicle

from milp.ilp_reachability import can_reach

# Objective function
TOTAL_PICKUP_DELAY = 0
TOTAL_RIDE_DELAY = 5
N_PRIVATE_RIDES = 1
N_FIRST_TIER = 2
TOTAL_FLEET_CAPACITY = 4

OBJECTIVE = "direct_arcs"

#Request config
REQUESTS = 20

# Vehicle config
VEHICLES = 20
MAX_VEHICLE_CAPACITY = 4
SPEED_KM_H = 30

# Experiment starts at
START_DATE = datetime.strptime("2011-02-01 00:00:00", '%Y-%m-%d %H:%M:%S')

# Model settings
DENY_SERVICE = False

# Setup time limit (seconds)
TIME_LIMIT = 3600

# Operational scenario
SCENARIO_FILE_PATH = (config.root_path +
                      "/scenario/week/allow_hiring.json")

# Reading scenario from file
with open(SCENARIO_FILE_PATH) as js:

    scenario = json.load(js)

# Share of each class in customer base
customer_segmentation_dict = (
    scenario["scenario_config"]
            ["customer_segmentation"]
            ["BB"]
)

print("### CUSTOMER SEGMENTATION SCENARIO")
pprint(customer_segmentation_dict)

# Service quality dict

service_quality_dict = {
    'A': {'pk_delay': 1800, 'sharing_preference': 0, 'trip_delay': 1800},
    'B': {'pk_delay': 3000, 'sharing_preference': 1, 'trip_delay': 6000},
    'C': {'pk_delay': 6000, 'sharing_preference': 1, 'trip_delay': 9000}
}

service_quality_dict = scenario["scenario_config"]["service_level"]

print("### SERVICE QUALITY SCENARIO")
pprint(service_quality_dict)

# Service rate
service_rate = scenario['scenario_config']['service_rate']['S2']
print("### SERVICE RATE SCENARIO")
pprint(service_rate)

def get_n_requests(n, service_quality_dict, customer_segmentation_dict):
    requests = []
    user_classes = list(service_quality_dict.keys())
    df = tp.get_next_batch(
        "TESTE1",
        chunk_size=2000,
        batch_size=30,
        tripdata_csv_path='D:/bb/sq/data/manhattan-island-new-york-city-new-york-usa/tripdata/tripdata_excerpt_2011-2-1_2011-2-28_ids.csv',
        start_timestamp='2011-02-01 00:00:00',
        end_timestamp='2011-02-01 00:01:00',
        classes=user_classes,
        freq=[customer_segmentation_dict[k] for k in user_classes]
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
                        service_duration=0)

                    requests.append(r)

                    if len(requests) == n:
                        return requests

def get_list_of_vehicles_in_region_centers(
        max_capacity, G, start_datetime,
        list_of_region_centers, list_of_nodes_to_reach, max_delay,
        reachability_dict, distance_dict):

    vehicle_list = []

    for node_to_reach in list_of_nodes_to_reach:
        set_centers_can_reach = set(list_of_region_centers).intersection(
            nw.get_can_reach_set(
                node_to_reach.network_node_id,
                reachability_dict,
                max_trip_duration=max_delay
            )
        )

        # Choose a center randomly to access the origin
        random_center_id = random.choice(list(set_centers_can_reach))
        lon, lat = nw.get_coords_node(random_center_id, G)

        print("\nVehicles in ", random_center_id, ":")
        # Create vehicles of different capacities in this center
        #for capacity in range(node_to_reach.parent.demand, max_capacity + 1):
        for capacity in range(max_capacity, max_capacity + 1):

            # Creating vehicle origin node
            depot_node = Node.factory_node(
                Node.TYPE_DEPOT,
                lon, lat, network_node_id=random_center_id
            )

            v = Vehicle(depot_node, capacity, start_datetime)
            print("Vehicle", v)

            dist_m = distance_dict[depot_node.network_node_id][node_to_reach.network_node_id]
            dist_seconds = int(3.6 * dist_m / 30 + 0.5)
            print("  -", v.pid, dist_seconds)

            vehicle_list.append(v)

        print("Can reach node: {}({})".format(
            node_to_reach.pid, node_to_reach.parent.demand))
    return vehicle_list

def get_n_vehicles(n, capacity, G, start_datetime):
    vehicle_list = []

    for i in range(0, n):

        # Getting random node info
        id, lon, lat = nw.get_random_node(G)

        # Creating vehicle origin node
        o = Node.factory_node(Node.TYPE_DEPOT, lon, lat, network_node_id=id)

        v = Vehicle(o, capacity, start_datetime)

        vehicle_list.append(v)

    return vehicle_list

def get_viable_network(depot_list, origin_list, destination_list,
                       pair_dic, distance_dic, speed=None):

    def dist_sec(o, d):
        dist_meters = distance_dic[o.network_node_id][d.network_node_id]
        if speed != None:
            dist_seconds = int(3.6 * dist_meters / speed + 0.5)
            return dist_seconds
        else:
            return dist_meters

    # Graph NxN - Remove self connections and arcs arriving in end depot
    nodes_network = defaultdict(dict)

    # Depots only connect to origins
    for depot in depot_list:
        for o in origin_list:
            # But only if vehicle can service demand entirely
            #if o.parent.demand <= depot.parent.capacity:
                nodes_network[depot][o] = dist_sec(depot, o)

    # Origins connect to other origins
    for o1 in origin_list:
        for o2 in origin_list:

            # No loop
            if o1 != o2:
                nodes_network[o1][o2] = dist_sec(o1, o2)

    # Origins connect to destinations
    for o in origin_list:
        for d in destination_list:
            nodes_network[o][d] = dist_sec(o, d)

    # Destination connect to origins
    for d in destination_list:
        for o in origin_list:

            # But not if origin and destination belong to same request
            if d != pair_dic[o]:
                nodes_network[d][o] = dist_sec(d, o)

    # Destinations connect to destinations
    for d1 in destination_list:
        for d2 in destination_list:
            # No loop
            if d1 != d2:
                nodes_network[d1][d2] = dist_sec(d1, d2)

    return nodes_network

def get_node_tw_dic(vehicles, request_list, distance_dict):
    node_timewindow_dict = {}
    for r in request_list:

        dist = distance_dict[r.origin][r.destination]

        o_earliest = r.revealing_datetime
        o_latest = o_earliest + timedelta(seconds=r.max_pickup_delay)

        d_earliest = r.revealing_datetime + timedelta(seconds=dist)
        d_latest = d_earliest + timedelta(seconds=r.max_total_delay)

        node_timewindow_dict[r.origin] = (o_earliest, o_latest)
        node_timewindow_dict[r.destination] = (d_earliest, d_latest)

    for v in vehicles:
        node_timewindow_dict[v.pos] = (
            v.available_at,
            v.available_at + timedelta(hours=24)
        )

    return node_timewindow_dict

def get_valid_rides(
        vehicles, node_timewindow_dict,
        pairs_dict, distance_dict):

    #### VARIABLES ####################################################
    # Decision variable - viable vehicle paths
    # A vehicle can only attend requests that it can fully handle,
    # e.g.:
    # k[A,C] - i[A,C] -- OK! (k,i,j)
    #   k[A] - i[A,C] -- NO!
    valid_rides = set()

    # Create valid rides

    for k in vehicles:
        for i, to_dict in distance_dict.items():

            # A vehicle can only start from its own depot
            if isinstance(i, NodeDepot) and k.pos is not i:
                continue

            for j, dist in to_dict.items():

                earliest_i = node_timewindow_dict[i][0]

                latest_j = node_timewindow_dict[j][1]

                if isinstance(i, NodePK):

                    dl = pairs_dict[i]

                    if j != dl:

                        # Can't access n3 from n2
                        if dl not in distance_dict[j].keys():
                            continue

                        max_ride = distance_dict[i][dl] + \
                            i.parent.max_total_delay

                        t_i_j = dist

                        t_j_dl = distance_dict[j][dl]

                        if t_i_j + t_j_dl > max_ride:
                            continue

                    if earliest_i > latest_j:
                        continue

                # k, i, j is a valid arc
                valid_rides.add((k, i, j))

    return valid_rides

def get_valid_visits(valid_rides):
    valid_visit = set()
    for v, i, j in valid_rides:
        valid_visit.add((v, i))
        valid_visit.add((v, j))
    return valid_visit

def big_m(i, j, t_i_j):
    service_i = (i.service_duration if i.service_duration else 0)
    big_m = max(0, int(i.latest + t_i_j + service_i - j.earliest))
    return big_m

def big_w(k, i):
    return min(2 * k.capacity, 2 * k.capacity + (i.demand if i.demand else 0))

# Getting network
G = nw.get_network_from(
    config.tripdata["region"],
    config.data_path,
    config.graph_name,
    config.graph_file_name
)

# Creating distance dictionary [o][d] -> distance
distance_dic = nw.get_distance_dic(config.path_dist_dic, G)

# Getting requests
requests = get_n_requests(
    REQUESTS,
    service_quality_dict,
    customer_segmentation_dict)

# for r in requests:
#     r.origin.demand = 1
#     r.destination.demand = -1
#     r.demand = 1

# The reachability dictionary
reachability = nw.get_reachability_dic(
    config.path_reachability_dic,
    distance_dic,
    step=config.step,
    total_range=config.total_range,
    speed_km_h=config.speed_km_h)

# Region centers
region_centers = nw.get_region_centers(
    config.path_region_centers,
    reachability,
    data_path=config.root_reachability,
    step=config.step,
    total_range=config.total_range,
    speed_km_h=config.speed_km_h)

# Get the lowest pickup delay from all user class
# Vehicles have to be able to access all nodes within the minimum delay
lowest_delay = min(
    [
        params['pk_delay'] for params in service_quality_dict.values()
    ]
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
    MAX_VEHICLE_CAPACITY, G, START_DATE, region_centers[lowest_delay],
    Node.origins, lowest_delay, reachability, distance_dic)

# Dictionary of viable connections (and distances) between vehicle
# and request nodes. E.g.: viable_nw[NodeDP][NodePK] = DIST_S
travel_time_dict = get_viable_network(
    Node.depots,
    Node.origins,
    Node.destinations,
    Request.node_pairs_dict,
    distance_dic,
    speed=SPEED_KM_H)

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
                o.pid, o.parent.demand, travel_time_dict[v.pos][o])
            for o, dist in travel_time_dict[v.pos].items()
            if dist < lowest_delay
        ]
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
        except:
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
node_timewindow_dict = get_node_tw_dic(vehicles, requests, travel_time_dict)

# Updating earliest and latest times (in seconds) for each node
for current_node, tw in node_timewindow_dict.items():
    e, l = tw
    current_node.earliest = (e - START_DATE).total_seconds()
    current_node.latest = (l - START_DATE).total_seconds()

print("### NODE TIME WINDOWS")
for current_node, tw in node_timewindow_dict.items():
    print(current_node, tw, current_node.demand)

# Eliminate unfeasible (v, o, d) rides:
# - Capacity constraints
# - Time window constraints
# - Node unreachability
valid_rides = get_valid_rides(
    vehicles,
    node_timewindow_dict,
    Request.node_pairs_dict,
    travel_time_dict)

print(" {} valid rides (k, i, j) created.".format(len(valid_rides)))

valid_visits = get_valid_visits(valid_rides)
print(" {} valid visits (k, i) created.".format(len(valid_visits)))

#pprint(valid_visits)
# pprint(valid_rides)

print("STARTING DARP-SQ...")
# Start time - loading model info
preprocessing_start_t = datetime.now()

try:

    # Create a new model
    m = Model("DARP-SQ")

    #m.LogFile = "output/ilp/logs/gurobi.log"
    
    ####################################################################
    #### MODEL VARIABLES ###############################################
    ####################################################################
    
    # 1 if vehicle k travels arc (i,j)
    m_var_flow = m.addVars(
        [(k.pid, i.pid, j.pid) for k, i, j in valid_rides],
        vtype=GRB.BINARY,
        name="x"
    )

    # 1 if user receives first-tier service levels
    m_var_first_tier = m.addVars(
        [i.pid for i in Node.origins],
        vtype=GRB.BINARY,
        name="y"
    )

    # Request pickup delay in [0, 2*request_max_delay]
    m_var_pickup_delay = m.addVars(
        [i.pid for i in Node.origins],
        vtype=GRB.INTEGER,
        lb=0,
        name="d"
    )

    # Arrival time of vehicle k at node i
    m_var_arrival_time = m.addVars(
        [(k.pid, i.pid) for k, i in valid_visits],
        vtype=GRB.INTEGER,
        lb=0,
        name="u"
    )

    # Load of compartment c of vehicle k at pickup node i
    m_var_load = m.addVars(
        [(k.pid, i.pid) for k, i in valid_visits],
        vtype=GRB.INTEGER,
        lb=0,
        name="w"
    )

    # Ride time of request i serviced by vehicle k
    m_var_ride_time = m.addVars(
        [(k.pid, i.pid) for k, i in valid_visits if isinstance(i, NodePK)],
        vtype=GRB.INTEGER,
        lb=0,
        name="r"
    )

    ####################################################################
    #### OBJECTIVE FUNCTION ############################################
    ####################################################################
    total_fleet_capacity = quicksum(
        k.capacity * m_var_flow[k.pid, i.pid, j.pid]
        for k, i, j in valid_rides
        if i in Node.depots)

    number_first_tier_requests = quicksum(
        m_var_first_tier[i.pid]
        for i in Node.origins)

    number_of_private_rides = quicksum(
        m_var_flow[k.pid, i.pid, j.pid]
        for k, i, j in valid_rides
        if i.parent == j.parent
    )

    total_pickup_delay = quicksum(
        m_var_pickup_delay[i.pid]
        for i in Node.origins
    )

    total_ride_delay = quicksum(
        m_var_ride_time[k.pid, i.pid] - travel_time_dict[i][j] 
        for k in vehicles
        for i, j in Request.od_set
        if (k,i) in valid_visits
    )
    
    of = {
        TOTAL_PICKUP_DELAY: total_pickup_delay,
        N_PRIVATE_RIDES: number_of_private_rides,
        N_FIRST_TIER: number_first_tier_requests,
        TOTAL_FLEET_CAPACITY: total_fleet_capacity,
        TOTAL_RIDE_DELAY: total_ride_delay,
    }

    # Hierarchical objectives: finds the best solution for the current 
    # objective, but only from among those that would not degrade the 
    # solution quality for higher-priority objectives.

    # 1st - Total fleet capacity (number of seats across all vehicles)
    m.setObjectiveN(
        of[TOTAL_FLEET_CAPACITY],
        index=0,
        priority = 2,
        name = 'fleet capacity'
    )

    # 2nd - Delay (pickup and ride delay)
    m.setObjectiveN(
        of[TOTAL_PICKUP_DELAY],
        index=1,
        priority = 1,
        name = 'pickup delay'
    )

    # 3rd - Ride delay
    m.setObjectiveN(
        of[TOTAL_RIDE_DELAY],
        index=2,
        priority = 0,
        name = 'ride delay'
    )


    m.Params.timeLimit = TIME_LIMIT

    ####################################################################
    #### ROUTING CONSTRAINTS ###########################################
    ####################################################################

    if DENY_SERVICE:
        print(
            "    # (2) DENY_REQ - Allow service "
            "rejection (less or equal than once)"
        )
        m.addConstrs(
            (
                m_var_flow.sum('*', i.pid, '*') <= 1
                for i in Node.origins
            ),
            "DENY_REQ"
        )
    else:
        print(
            "    # (2) ALL_REQ - User base is serviced "
            "entirely (exactly once)"
        )
        m.addConstrs(
            (
                m_var_flow.sum('*', i.pid, '*') == 1
                for i in Node.origins
            ),
            "ALL_REQ"
        )

    print("    # (3) IF_V_PK_DL - Same vehicle services user's OD")
    m.addConstrs(
        (
            m_var_flow.sum(k.pid, i.pid, '*')
            - m_var_flow.sum(k.pid, '*', j.pid) == 0
            for k in vehicles
            for i, j in Request.od_set
            if (k, i, j) in valid_rides
        ),
        "IF_V_PK_DL")

    print("    # (4) FLOW_V_DEPOT - Vehicles start from their own depot")
    m.addConstrs(
        (
            m_var_flow.sum(k.pid, k.pos.pid, '*') <= 1
            for k in vehicles
        ),
        "FLOW_V_DEPOT"
    )

    print("    # (5a) FLOW_V_O - Vehicles enter and leave pk nodes")
    m.addConstrs(
        (
            m_var_flow.sum(
                k.pid, '*', i.pid) == m_var_flow.sum(k.pid, i.pid, '*')
            for i in Node.origins
            for k in vehicles
        ),
        "FLOW_V_O")

    print(
        "    # (5b) FLOW_V_D - Vehicles enter"
        "and leave/stay destination nodes"
    )
    m.addConstrs(
        (
            m_var_flow.sum(k.pid, '*', i.pid) >=
            m_var_flow.sum(k.pid, i.pid, '*')
            for i in Node.destinations
            for k in vehicles
        ),
        "FLOW_V_D")

    print(
        "    # (10) SERVICE_TIER - Guarantee first-tier"
        " service levels for a share of requests in class"
    )
    for sq_class, sq_class_requests in Request.service_quality.items():
        #print(h, service_rate[h], reqs, [r.origin for r in reqs])

        total_first_tier_requests = quicksum(
            m_var_first_tier[r.origin.pid]
            for r in sq_class_requests
        )

        min_first_tier_requests = int(
            service_rate[sq_class]*len(sq_class_requests) + 0.5
        )

        m.addConstr(
            total_first_tier_requests >= min_first_tier_requests,
            "SERVICE_TIER[{}]".format(sq_class)
        )

        if not service_quality_dict[sq_class]['sharing_preference']:

            print(
                "    # (14) PRIVATE_RIDE {} - vehicle that picks up user"
                " from class {} is empty".format(sq_class, sq_class)
            )
            for r in sq_class_requests:

                a = quicksum(
                    m_var_flow[k.pid, r.origin.pid, r.destination.pid]
                    for k in vehicles
                    if (k, r.origin, r.destination) in valid_rides
                )
                m.addConstr(a == 1, "PRIVATE_RIDE[{}]".format(r))

            for r in sq_class_requests:
                for k in vehicles:
                    if (k, r.origin) in valid_visits:
                        m.addConstr(
                            (
                                m_var_load[k.pid, r.origin.pid] <= r.demand
                            ),
                            "PRIVATE_PK_{}[{},{}]".format(
                                sq_class,
                                k,
                                r.origin.pid
                            )
                        )


    print("    # ( 6) ARRIVAL_TIME - Consistency arrival time")
    m.addConstrs(
        (
            m_var_arrival_time[k.pid, j.pid] >=
            m_var_arrival_time[k.pid, i.pid]
            + travel_time_dict[i][j]
            - big_m(i, j, travel_time_dict[i][j])
            * (1 - m_var_flow[k.pid, i.pid, j.pid])
            for k, i, j in valid_rides
        ), "ARRIVAL_TIME")

    #### RIDE TIME CONSTRAINTS ########################################

    print("    # (7) RIDE_1")
    r1 = datetime.now()
    # (RIDE_1) = Ride time from i to j >= time_from_i_to_j
    m.addConstrs(
        (
            m_var_ride_time[k.pid, i.pid] >= travel_time_dict[i][j]

            for k, i, j in valid_rides
            if (i, j) in Request.od_set
        ),
        "RIDE_1")

    print(
        "    # (12) MAX_RIDE_TIME - Maximum ride "
        "time of user is guaranteed"
    )
    m.addConstrs(
        (
            m_var_ride_time[k.pid, i.pid] <=
            travel_time_dict[i][j]
            + m_var_pickup_delay[i.pid]
            + i.parent.max_in_vehicle_delay
            for k, i, j in valid_rides
            if (i, j) in Request.od_set
        ),
        "MAX_RIDE_TIME")

    print("    # ( 8) RIDE_TIME - Define user ride time")
    m.addConstrs(
        (
            m_var_ride_time[k.pid, i.pid] >=
            m_var_arrival_time[k.pid, j.pid]
            - m_var_arrival_time[k.pid, i.pid]
            for k in vehicles
            for i, j in Request.od_set
            if (k, i, j) in valid_rides
        ),
        "RIDE_TIME")

    ### TIME WINDOW CONSTRAINTS #######################################
    print(
        "    # (11) EARL - Earliest pickup time"
        " >= earliest arrival time"
    )
    m.addConstrs(
        (
            m_var_arrival_time[k.pid, i.pid] ==
            i.earliest + m_var_pickup_delay[i.pid]
            for (k, i) in valid_visits
            if isinstance(i, NodePK)
        ),
        "EARL")

    print("    # (13) FIRST_TIER - pickup delay in [0, max_pk_delay)")
    m.addConstrs(
        (
            m_var_pickup_delay[i.pid] >=
            i.parent.max_pickup_delay*(1-m_var_first_tier[i.pid])
            for i in Node.origins
        ),
        "FIRST_TIER")

    print(
        "    # (13) SECOND_TIER - pickup delay"
        " in [max_pk_delay, 2*max_pk_delay)"
    )
    m.addConstrs(
        (
            m_var_pickup_delay[i.pid] <=
            i.parent.max_pickup_delay
            + i.parent.max_pickup_delay*(1-m_var_first_tier[i.pid])
            for i in Node.origins
        ),
        "SECOND_TIER")

    #### LOADING CONSTRAINTS ##########################################

    print("    # ( 7) LOAD - Guarantee load consistency")
    m.addConstrs(
        (
            m_var_load[k.pid, j.pid] >=
            m_var_load[k.pid, i.pid]
            + (j.demand if j.demand else 0)
            - big_w(k, i) * (1 - m_var_flow[k.pid, i.pid, j.pid])
            for k, i, j in valid_rides
        ),
        "LOAD")


    print("    # (13a) LOAD_MIN -  max(0, node_demand)")
    m.addConstrs(
        (
            m_var_load[k.pid, i.pid] >=
            max(0, (i.demand if i.demand else 0))
            for k, i in valid_visits

        ),
        "LOAD_MIN")

    print("    # (13b) LOAD_MAX - (capacity, capacity + node_demand)")
    m.addConstrs(
        (
            m_var_load[k.pid, i.pid] <=
            min(k.capacity, k.capacity + (i.demand if i.demand else 0))
            for k, i in valid_visits
        ),
        "LOAD_MAX")

    print("    # (13) LOAD_END_D - Terminal delivery nodes have load 0.")

    m.addConstrs(
        (
            m_var_load[k.pid, j.pid] <=
            (k.capacity + j.demand)
            * m_var_flow.sum(k.pid, j.pid, '*')
            for k, j in valid_visits
            if isinstance(j, NodeDL)
        ),
        "LOAD_END_D")


    print("    # ARRI_AT_ORIGIN")

    # Guarantees a vehicle will be available only at an specified time
    # Some vehicles are discarded because they cannot access any node
    # (not a valid visit)
    m.addConstrs(
        (
            m_var_arrival_time[k.pid, k.pos.pid] ==
            (k.available_at - START_DATE).total_seconds()
            for k in vehicles
        ),
        "ARRI_AT_ORIGIN")

    print("    # LOAD_DEPOT_0")
    m.addConstrs(
        (
            m_var_load[k.pid, k.pos.pid] == 0
            for k in vehicles
        ),
        "LOAD_DEPOT_0")




    preprocessing_t = (datetime.now() - preprocessing_start_t).seconds

    m.write("gurobi_model_darp_sq.lp")

    print("Optimizing...")

    # Solve
    m.optimize()

    # Optimize model + lazy constraints
    #m._vars = ride
    #m.params.LazyConstraints = 1
    #m.optimize(subtourelim)

    print("Preprocessing:", preprocessing_t)
    print("Model runtime:", m.Runtime)
    #m.Params.LogFile = "gurobi_model_darp_sq.lp"
    #m.write("gurobi_model_darp_sq.lp")

    ####################################################################
    #### SHOW RESULTS ##################################################
    ####################################################################

    is_umbounded = m.status == GRB.Status.UNBOUNDED
    found_optimal = (m.status == GRB.Status.OPTIMAL)
    found_sol_within_time_limit = (
        m.status == GRB.Status.TIME_LIMIT and m.SolCount > 0
    )

    if is_umbounded:
        print('The model cannot be solved because it is unbounded')

    elif found_optimal or found_sol_within_time_limit:
        print("TIME LIMIT ({} s) RECHEADED.".format(TIME_LIMIT))

        var_flow = m.getAttr('x', m_var_flow)

        var_first_tier = m.getAttr('x', m_var_first_tier)

        var_ride_time = m.getAttr('x', m_var_ride_time)

        var_load = {k:int(v) for k,v in m.getAttr('x', m_var_load).items()}

        var_arrival_time = m.getAttr('x', m_var_arrival_time)

        print("REQUEST DICTIONARY")

        ###################################################################
        # MODEL ATTRIBUTES
        # http://www.gurobi.com/documentation/7.5/refman/model_attributes.html

        # BEST PRACTICES
        # http://www.gurobi.com/pdfs/user-events/2016-frankfurt/Best-Practices.pdf
        # http://www.dcc.fc.up.pt/~jpp/seminars/azores/gurobi-intro.pdf
        # solver_sol = {
        #     "gap": m.MIPGap,
        #     "num_vars": m.NumVars,
        #     "num_constrs": m.NumConstrs,
        #     "obj_bound": m.ObjBound,
        #     "obj_val": m.ObjVal,
        #     "node_count": m.NodeCount,
        #     "sol_count": m.SolCount,
        #     "iter_count": m.IterCount,
        #     "runtime": m.Runtime,
        #     "preprocessing_t": preprocessing_t,
        #     "status": m.status
        # }

        # pprint(solver_sol)

        # Stores vehicle visits k -> from_node-> to_node
        vehicle_visits_dict = {k: dict() for k in vehicles}

        # Ordered list of nodes visited by each vehicle
        vehicle_routes_dict = dict()

        for k, i, j in valid_rides:

            # WARNING - FLOATING POINT ERROR IN GUROBI

            # This can happen due to feasibility and integrality tolerances.
            # You will also find that solution that Gurobi (as all floating-
            # point based MIP solvers) provides may slightly violate your
            # constraints.

            # The reason is that floating-point numeric as implemented in
            # the CPU hardware is not exact. Rounding errors can (and
            # usually will) happen. As a consequence, MIP solvers use
            # tolerances within which a solution is still considered to be
            # correct. The default tolerance for integrality in Gurobi
            # is 1e-5, the default feasibility tolerance is 1e-6. This means
            # that Gurobi is allowed to consider a value that is at most
            # 1e-5 away from an integer to still be integral, and it is
            # allowed to consider a constraint that is violated by at most
            # 1e-6 to still be satisfied.

            # If there is a path from i to j by vehicle k
            # 0.9 accounts for rounding errors (feasibility/integrality
            # tolerances)
            if var_flow[k.pid, i.pid, j.pid] > 0.9:

                # Updating node's arrival and departure times
                arr_i = var_arrival_time[k.pid, i.pid]
                arr_j = var_arrival_time[k.pid, j.pid]

                i.departure = START_DATE + timedelta(seconds=arr_i)
                j.arrival = START_DATE + timedelta(seconds=arr_j)

                # Stores which vehicle picked up request
                if isinstance(i, NodePK):
                    i.parent.serviced_by = k

                vehicle_visits_dict[k][i] = j

        for k, from_to in vehicle_visits_dict.items():
            # Does the vehicle service any request?
            if from_to:
                print("Ordering vehicle {}({})...".format(k.pid, k.pos.pid))
                random_center_id = k.pos
                ordered_list = list()
                while True:
                    ordered_list.append(random_center_id)
                    next_id = from_to[random_center_id]
                    random_center_id = next_id
                    if random_center_id not in from_to.keys():
                        ordered_list.append(random_center_id)
                        break
                vehicle_routes_dict[k] = ordered_list

        def duration_format(t):
            return "{:02}:{:02}:{:02}".format(
                int(t/3600), int((t % 3600)/60), int(t % 60))

        print("###### Routes")
        for k, node_list in vehicle_routes_dict.items():
            print('\n######### Vehicle {} (Departure:{})'.format(
                k.pid,
                k.pos.departure
            )
            )

            precedent_node = None
            for current_node in node_list:
                if precedent_node and precedent_node is not current_node:

                    trip_duration = (
                        travel_time_dict[precedent_node][current_node]
                    )

                    total_duration = (
                        current_node.arrival
                        - precedent_node.departure
                    ).total_seconds()

                    idle_time = total_duration - trip_duration

                    print("   ||    {} (trip)".format(
                        duration_format(trip_duration))
                    )

                    print("   ||    {} (idle)".format(
                        duration_format(idle_time))
                    )

                print(
                    (
                        "   {node_id} - ({arrival} , {departure}) "
                        "[load = {load}]"
                    ).format(
                        load=var_load[k.pid, current_node.pid],
                        node_id=current_node.pid,
                        arrival=(
                            current_node.arrival.strftime('%H:%M:%S')
                            if current_node.arrival else '--:--:--'
                        ),
                        departure=(
                            current_node.departure.strftime('%H:%M:%S')
                            if current_node.departure else '--:--:--'
                        )
                    )
                )

                precedent_node = current_node

        print("###### Requests")
        for r in requests:
            if var_first_tier[r.origin.pid] > 0.9:
                tier = "<1st tier>"
            else:
                tier = "<2nd tier>"

            print(
                r.get_info(
                    min_dist=travel_time_dict[r.origin][r.destination]
                ),
                tier
            )

    elif m.status == GRB.Status.INFEASIBLE:

        status = "infeasible"
        print('Model is infeasible.')
        #raise Exception('Model is infeasible.')
        # exit(0)

    elif m.status != GRB.Status.INF_OR_UNBD and m.status != GRB.Status.INFEASIBLE:
        print('Optimization was stopped with status %d' % m.status)
        status = "interrupted"
        # exit(0)

    # IRREDUCIBLE INCONSISTENT SUBSYSTEM (IIS).
    # An IIS is a subset of the constraints and variable bounds
    # of the original model. If all constraints in the model
    # except those in the IIS are removed, the model is still
    # infeasible. However, further removing any one member
    # of the IIS produces a feasible result.
    # do IIS

    """print('The model is infeasible; computing IIS')
    removed = []

    # Loop until we reduce to a model that can be solved
    while True:

        m.computeIIS()
        print('\nThe following constraint cannot be satisfied:')
        for c in m.getConstrs():
            if c.IISConstr:
                print('%s' % c.constrName)
                # Remove a single constraint from the model
                removed.append(str(c.constrName))
                m.remove(c)
                break
        print('')

        m.optimize()
        status = m.status

        if status == GRB.Status.UNBOUNDED:
            print('The model cannot be solved because it is unbounded')
            exit(0)
        if status == GRB.Status.OPTIMAL:
            break
        if status != GRB.Status.INF_OR_UNBD and status != GRB.Status.INFEASIBLE:
            print('Optimization was stopped with status %d' % status)
            exit(0)

    print('\nThe following constraints were removed to get a feasible LP:')
    print(removed)
    """
    """
    # MODEL RELAXATION
    # Relax the constraints to make the model feasible
    print('The model is infeasible; relaxing the constraints')
    orignumvars = m.NumVars
    m.feasRelaxS(0, False, False, True)
    m.optimize()
    status = m.status
    if status in (GRB.Status.INF_OR_UNBD, GRB.Status.INFEASIBLE, GRB.Status.UNBOUNDED):
        print('The relaxed model cannot be solved \
            because it is infeasible or unbounded')
        exit(1)

    if status != GRB.Status.OPTIMAL:
        print('Optimization was stopped with status %d' % status)
        exit(1)

    print('\nSlack values:')
    slacks = m.getVars()[orignumvars:]
    for sv in slacks:
        if sv.X > 1e-6:
            print('%s = %g' % (sv.VarName, sv.X))
    """

except GurobiError:
    print('Error reported:', str(GurobiError), str(GurobiError.message))

except Exception as e:
    print(str(e))
    raise

finally:
    # Reset indices of nodes
    Node.reset_nodes_ids()
    #Vehicle.reset_vehicles_ids()

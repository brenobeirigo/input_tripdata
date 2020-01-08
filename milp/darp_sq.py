from datetime import timedelta, datetime
from pprint import pprint
from collections import defaultdict
from gurobipy import Model, GurobiError, GRB, quicksum

import logging

from model.Request import Request
from model.Node import Node, NodePK, NodeDL, NodeDepot
from model.Vehicle import Vehicle

# Objective function
TOTAL_PICKUP_DELAY = "pickup_delay"
TOTAL_RIDE_DELAY = "ride_delay"
TOTAL_DELAY = "total_delay"
N_PRIVATE_RIDES = "private_rides"
N_FIRST_TIER = "first_tier_rides"
TOTAL_FLEET_CAPACITY = "fleet_capacity"


def get_viable_network(
        depot_list,
        origin_list,
        destination_list,
        pair_dic,
        distance_dic,
        speed=None):
    def dist_sec(o, d):
        dist_meters = distance_dic[o.network_node_id][d.network_node_id]
        if speed is not None:
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
            # if o.parent.demand <= depot.parent.capacity:
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
            v.available_at + timedelta(hours=24),
        )

    return node_timewindow_dict


def get_valid_rides_set(
        vehicles,
        pairs_dict,
        distance_dict):

    valid_rides = set()

    for k in vehicles:
        for i, to_dict in distance_dict.items():

            # A vehicle can only start from its own depot
            if isinstance(i, NodeDepot) and k.pos is not i:
                continue

            # A vehicle shall not enter an origin node with a demand
            # higher than its own capacity
            if (isinstance(i.parent, Request)
                    and k.capacity < i.parent.demand):
                continue

            for j, dist_i_j in to_dict.items():

                # No vehicle can visit depot
                if isinstance(j, NodeDepot):
                    continue

                # A vehicle shall not enter a destination node with a
                # demand higher than its own capacity
                if (isinstance(j.parent, Request)
                        and k.capacity < j.parent.demand):
                    continue

                if isinstance(i, NodePK):

                    # Destination of pickup node i
                    di = pairs_dict[i]

                    if j != di:

                        # Cannot access i's final destination from
                        # intermediate node j
                        if di not in distance_dict[j].keys():
                            continue

                        max_ride_delay = (
                            distance_dict[i][di]
                            + i.parent.max_total_delay
                        )

                        dist_j_di = distance_dict[j][di]

                        # Can't arrive in i's destination on time
                        # passing by intermediate node j
                        if dist_i_j + dist_j_di > max_ride_delay:
                            continue

                    # Can't get in j on time
                    if i.earliest > j.latest:
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
    service_i = i.service_duration if i.service_duration else 0
    big_m = max(0, int(i.latest + t_i_j + service_i - j.earliest))
    return big_m


def big_w(k, i):
    return min(2 * k.capacity, 2 * k.capacity + (i.demand if i.demand else 0))


def print_sol(
        vehicles,
        requests,
        travel_time_dict,
        valid_rides,
        start_date,
        var_arrival_time,
        var_invehicle_delay,
        var_flow,
        var_load,
        var_first_tier,
        var_pickup_delay):

    logger = logging.getLogger('run_experiment.milp_solution')

    # Stores vehicle visits k -> from_node-> to_node
    vehicle_visits_dict = {k: dict() for k in vehicles}

    # Ordered list of nodes visited by each vehicle
    vehicle_routes_dict = dict()

    for k, i, j in valid_rides:
        # Stores which vehicle picked up request
        if isinstance(i, NodePK):
            i.parent.serviced_by = k
            #print("ALL - Pickup delay", i, ":", var_pickup_delay[i.pid])
            #print("ALL - Ride delay", k, ",", i, ":", var_invehicle_delay[k.pid, i.pid])
    total_pk = 0
    total_ride = 0
    logger.info("#### PICKUP AND RIDE DELAYS")
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

            i.departure = start_date + timedelta(seconds=arr_i)
            j.arrival = start_date + timedelta(seconds=arr_j)

            # Stores which vehicle picked up request
            if isinstance(i, NodePK):
                r = i.parent
                r.serviced_by = k
                r.pk_delay = var_pickup_delay[i.pid]
                r.ride_delay = var_invehicle_delay[k.pid, i.pid]
                r.tier = (
                    1 if var_first_tier[r.origin.pid] > 0.9 else 2)
                total_pk += var_pickup_delay[i.pid]
                total_ride += var_invehicle_delay[k.pid, i.pid]
                logger.info(
                    f"{k} - {i.pid}[{r.service_class}] "
                    f"(pk={r.pk_delay}/{i.parent.max_pickup_delay}, "
                    f"ride={r.ride_delay}/{r.max_in_vehicle_delay}, "
                    f"tier={r.tier}), "
                    f"serviced_by={r.serviced_by}"
                )

            vehicle_visits_dict[k][i] = j

    for k, from_to in vehicle_visits_dict.items():
        # Does the vehicle service any request?
        if from_to:
            logger.info("Ordering vehicle {}({})...".format(k.pid, k.pos.pid))
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

    logger.info(f"#### TOTAL DELAY -> PK={total_pk:>5} RIDE={total_ride:>5}")

    def duration_format(t):
        return "{:02}:{:02}:{:02}".format(
            int(t / 3600), int((t % 3600) / 60), int(t % 60)
        )

    logger.info("###### Routes")
    for k, node_list in vehicle_routes_dict.items():
        logger.info(
            "######### Vehicle {} (Departure:{})".format(
                k.pid, k.pos.departure
            )
        )

        precedent_node = None
        for current_node in node_list:
            if precedent_node and precedent_node is not current_node:

                trip_duration = travel_time_dict[precedent_node][current_node]

                total_duration = (
                    current_node.arrival - precedent_node.departure
                ).total_seconds()

                idle_time = total_duration - trip_duration

                logger.info(
                    "   ||    {} (trip)".format(duration_format(trip_duration))
                )

                logger.info(
                    "   ||    {} (idle)".format(duration_format(idle_time)))

            logger.info(
                (
                    "   {node_id} - ({arrival} , {departure}) "
                    "[load = {load}]"
                ).format(
                    load=var_load[k.pid, current_node.pid],
                    node_id=current_node.pid,
                    arrival=(
                        current_node.arrival.strftime("%H:%M:%S")
                        if current_node.arrival
                        else "--:--:--"
                    ),
                    departure=(
                        current_node.departure.strftime("%H:%M:%S")
                        if current_node.departure
                        else "--:--:--"
                    ),
                )
            )

            precedent_node = current_node

    logger.info("###### Requests")
    for r in requests:

        # logger.info(var_invehicle_delay[(r.serviced_by.pid, r.origin.pid)])
        logger.info("{r_info}{tier}".format(
            r_info=r.get_info(
                min_dist=travel_time_dict[r.origin][r.destination]),
            tier=f"<tier={r.tier}>")
        )

    return vehicle_routes_dict


def milp_sq_class(
        vehicles,
        requests,
        travel_time_dict,
        service_quality_dict,
        service_rate,
        obj_list,
        time_limit,
        start_date,
        log_path=None,
        lp_path=None):

    logger = logging.getLogger('run_experiment.milp_execution')

    print("STARTING DARP-SQ...")

    # Start time - loading model info
    preprocessing_start_t = datetime.now()

    # Eliminate unfeasible (v, o, d) rides:
    # - Capacity constraints
    # - Time window constraints
    # - Node unreachability
    valid_rides = get_valid_rides_set(
        vehicles,
        Request.node_pairs_dict,
        travel_time_dict)
    valid_visits = get_valid_visits(valid_rides)

    preprocessing_t = (datetime.now() - preprocessing_start_t).seconds

    logger.info(" {} valid rides (k, i, j) created.".format(len(valid_rides)))
    logger.info(" {} valid visits (k, i) created.".format(len(valid_visits)))

    try:

        # Create a new model
        m = Model("DARP-SQ")

        # m.LogFile = "output/ilp/logs/gurobi.log"

        # ##############################################################
        # **************************************************************
        # ### MODEL VARIABLES ##########################################
        # ************************************************************##
        # ##############################################################

        # 1 if vehicle k travels arc (i,j)
        m_var_flow = m.addVars(
            [(k.pid, i.pid, j.pid) for k, i, j in valid_rides],
            vtype=GRB.BINARY,
            name="x",
        )

        # 1 if user receives first-tier service levels
        m_var_first_tier = m.addVars(
            [i.pid for i in Node.origins], vtype=GRB.BINARY, name="y"
        )

        # Request pickup delay in [0, 2*request_max_delay]
        m_var_pickup_delay = m.addVars(
            [i.pid for i in Node.origins], vtype=GRB.INTEGER, lb=0, name="d"
        )

        # Arrival time of vehicle k at node i
        m_var_arrival_time = m.addVars(
            [(k.pid, i.pid) for k, i in valid_visits],
            vtype=GRB.INTEGER,
            lb=0,
            name="u",
        )

        # Load of compartment c of vehicle k at pickup node i
        m_var_load = m.addVars(
            [(k.pid, i.pid) for k, i in valid_visits],
            vtype=GRB.INTEGER,
            lb=0,
            name="w",
        )

        # Ride time of request i serviced by vehicle k
        m_var_invehicle_delay = m.addVars(
            [(k.pid, i.pid) for k, i in valid_visits if isinstance(i, NodePK)],
            vtype=GRB.INTEGER,
            lb=0,
            name="r",
        )

        # ##############################################################
        # **************************************************************
        # ### OBJECTIVE FUNCTION #######################################
        # **************************************************************
        # ##############################################################
        total_fleet_capacity = quicksum(
            k.capacity * m_var_flow[k.pid, i.pid, j.pid]
            for k, i, j in valid_rides
            if i in Node.depots
        )

        number_first_tier_requests = quicksum(
            m_var_first_tier[i.pid] for i in Node.origins
        )

        number_of_private_rides = quicksum(
            m_var_flow[k.pid, i.pid, j.pid]
            for k, i, j in valid_rides
            if i.parent == j.parent
        )

        total_pickup_delay = quicksum(
            m_var_pickup_delay[i.pid] for i in Node.origins
        )

        total_ride_delay = quicksum(
            m_var_invehicle_delay[k.pid, i.pid]
            for k in vehicles
            for i, j in Request.od_set
            if (k, i) in valid_visits
        )

        of = {
            TOTAL_PICKUP_DELAY: total_pickup_delay,
            N_PRIVATE_RIDES: number_of_private_rides,
            N_FIRST_TIER: number_first_tier_requests,
            TOTAL_FLEET_CAPACITY: total_fleet_capacity,
            TOTAL_RIDE_DELAY: total_ride_delay,
            TOTAL_DELAY: total_ride_delay + total_pickup_delay
        }

        # Hierarchical objectives: finds the best solution for the
        # current objective, but only from among those that would
        # not degrade the solution quality for higher-priority
        # objectives.
        for obj_number, obj_name in enumerate(obj_list):

            # The higher is the priority, the more important is the
            # objective. The obj_list is sorted in order of priority.
            priority = len(obj_list) - obj_number - 1

            m.setObjectiveN(
                of[obj_name],
                priority=priority,
                index=obj_number,
                name=obj_name
            )

            logger.info(
                "Setting objective {} ({}) - priority: {}".format(
                    obj_number, obj_name, priority
                )
            )

        m.Params.timeLimit = time_limit

        # ##############################################################
        # **************************************************************
        # ### ROUTING CONSTRAINTS ######################################
        # **************************************************************
        # ##############################################################
        logger.info(
            "    # (2) ALL_REQ - User base is serviced "
            "entirely (exactly once)"
        )
        m.addConstrs(
            (m_var_flow.sum("*", i.pid, "*") == 1 for i in Node.origins),
            "ALL_REQ",
        )

        logger.info("    # (3) IF_V_PK_DL - Same vehicle services user's OD")
        m.addConstrs(
            (
                m_var_flow.sum(k.pid, i.pid, "*")
                - m_var_flow.sum(k.pid, "*", j.pid)
                == 0
                for k in vehicles
                for i, j in Request.od_set
                if (k, i, j) in valid_rides
            ),
            "IF_V_PK_DL",
        )

        logger.info(
            "    # (4) FLOW_V_DEPOT - Vehicles start from their own depot")
        m.addConstrs(
            (m_var_flow.sum(k.pid, k.pos.pid, "*") <= 1 for k in vehicles),
            "FLOW_V_DEPOT",
        )

        logger.info("    # (5a) FLOW_V_O - Vehicles enter and leave pk nodes")
        m.addConstrs(
            (
                m_var_flow.sum(k.pid, "*", i.pid)
                == m_var_flow.sum(k.pid, i.pid, "*")
                for i in Node.origins
                for k in vehicles
            ),
            "FLOW_V_O",
        )

        logger.info(
            "    # (5b) FLOW_V_D - Vehicles enter"
            "and leave/stay destination nodes"
        )
        m.addConstrs(
            (
                m_var_flow.sum(k.pid, "*", i.pid)
                >= m_var_flow.sum(k.pid, i.pid, "*")
                for i in Node.destinations
                for k in vehicles
            ),
            "FLOW_V_D",
        )

        logger.info(
            "    # (10) SERVICE_TIER - Guarantee first-tier"
            " service levels for a share of requests in class"
        )
        for sq_class, sq_class_requests in Request.service_quality.items():
            # print(h, service_rate[h], reqs, [r.origin for r in reqs])

            total_first_tier_requests = quicksum(
                m_var_first_tier[r.origin.pid] for r in sq_class_requests
            )

            min_first_tier_requests = int(
                service_rate[sq_class] * len(sq_class_requests) + 0.5
            )

            m.addConstr(
                total_first_tier_requests >= min_first_tier_requests,
                "SERVICE_TIER[{}]".format(sq_class),
            )

            if not service_quality_dict[sq_class]["sharing_preference"]:

                logger.info(
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
                                (m_var_load[k.pid, r.origin.pid] <= r.demand),
                                "PRIVATE_PK_{}[{},{}]".format(
                                    sq_class, k, r.origin.pid
                                ),
                            )

        logger.info("    # ( 6) ARRIVAL_TIME - Consistency arrival time")
        m.addConstrs(
            (
                m_var_arrival_time[k.pid, j.pid]
                >= m_var_arrival_time[k.pid, i.pid]
                + travel_time_dict[i][j]
                - big_m(i, j, travel_time_dict[i][j])
                * (1 - m_var_flow[k.pid, i.pid, j.pid])
                for k, i, j in valid_rides
            ),
            "ARRIVAL_TIME",
        )

        # RIDE TIME CONSTRAINTS ########################################

        logger.info("    # (7) RIDE_1")
        # (RIDE_1) = Ride time from i to j >= time_from_i_to_j
        m.addConstrs(
            (
                m_var_invehicle_delay[k.pid, i.pid] >= 0
                for k, i, j in valid_rides
                if (i, j) in Request.od_set
            ),
            "RIDE_1",
        )

        logger.info(
            "    # (12) MAX_RIDE_TIME - Maximum ride "
            "time of user is guaranteed"
        )
        m.addConstrs(
            (
                m_var_invehicle_delay[k.pid, i.pid]
                <= i.parent.max_in_vehicle_delay
                for k, i, j in valid_rides
                if (i, j) in Request.od_set
            ),
            "MAX_RIDE_TIME",
        )

        logger.info("    # ( 8) RIDE_TIME - Define user ride time")
        m.addConstrs(
            (
                m_var_invehicle_delay[k.pid, i.pid]
                == m_var_arrival_time[k.pid, j.pid]
                - m_var_arrival_time[k.pid, i.pid] - travel_time_dict[i][j]
                for k in vehicles
                for i, j in Request.od_set
                if (k, i, j) in valid_rides
            ),
            "RIDE_TIME",
        )

        # TIME WINDOW CONSTRAINTS ######################################
        logger.info(
            "    # (11) EARL - Earliest pickup time"
            " >= earliest arrival time"
        )
        m.addConstrs(
            (
                m_var_arrival_time[k.pid, i.pid]
                == i.earliest + m_var_pickup_delay[i.pid]
                for (k, i) in valid_visits
                if isinstance(i, NodePK)
            ),
            "EARL",
        )

        logger.info(
            "    # (13) FIRST_TIER - pickup delay in [0, max_pk_delay)")
        m.addConstrs(
            (
                m_var_pickup_delay[i.pid]
                >= i.parent.max_pickup_delay * (1 - m_var_first_tier[i.pid])
                for i in Node.origins
            ),
            "FIRST_TIER",
        )

        logger.info(
            "    # (13) SECOND_TIER - pickup delay"
            " in [max_pk_delay, 2*max_pk_delay)"
        )
        m.addConstrs(
            (
                m_var_pickup_delay[i.pid]
                <= i.parent.max_pickup_delay
                + i.parent.max_pickup_delay * (1 - m_var_first_tier[i.pid])
                for i in Node.origins
            ),
            "SECOND_TIER",
        )

        # LOADING CONSTRAINTS ##########################################

        logger.info("    # ( 7) LOAD - Guarantee load consistency")
        m.addConstrs(
            (
                m_var_load[k.pid, j.pid]
                >= m_var_load[k.pid, i.pid]
                + (j.demand if j.demand else 0)
                - big_w(k, i) * (1 - m_var_flow[k.pid, i.pid, j.pid])
                for k, i, j in valid_rides
            ),
            "LOAD",
        )

        logger.info("    # (13a) LOAD_MIN -  max(0, node_demand)")
        m.addConstrs(
            (
                m_var_load[k.pid, i.pid]
                >= max(0, (i.demand if i.demand else 0))
                for k, i in valid_visits
            ),
            "LOAD_MIN",
        )

        logger.info("    # (13b) LOAD_MAX - (capacity, capacity + node_demand)")
        m.addConstrs(
            (
                m_var_load[k.pid, i.pid]
                <= min(k.capacity, k.capacity + (i.demand if i.demand else 0))
                for k, i in valid_visits
            ),
            "LOAD_MAX",
        )

        logger.info(
            "    # (13) LOAD_END_D - Terminal delivery nodes have load 0.")

        m.addConstrs(
            (
                m_var_load[k.pid, j.pid]
                <= (k.capacity + j.demand) * m_var_flow.sum(k.pid, j.pid, "*")
                for k, j in valid_visits
                if isinstance(j, NodeDL)
            ),
            "LOAD_END_D",
        )

        logger.info("    # ARRI_AT_ORIGIN")

        # Guarantees a vehicle will be available only at an specified time
        # Some vehicles are discarded because they cannot access any node
        # (not a valid visit)
        m.addConstrs(
            (
                m_var_arrival_time[k.pid, k.pos.pid]
                == (k.available_at - start_date).total_seconds()
                for k in vehicles
            ),
            "ARRI_AT_ORIGIN",
        )

        logger.info("    # LOAD_DEPOT_0")
        m.addConstrs(
            (m_var_load[k.pid, k.pos.pid] == 0 for k in vehicles),
            "LOAD_DEPOT_0",
        )

        # Save .lp file
        # if log_path is not None:
        #     m.write(log_path)

        # Save .lp file
        if lp_path is not None:
            # m.write(lp_path)
            m.setParam("LogToConsole", 0)
            m.Params.LogFile = lp_path

        logger.info("Optimizing...")

        # Solve
        m.optimize()

        # Optimize model + lazy constraints
        # m._vars = ride
        # m.params.LazyConstraints = 1
        # m.optimize(subtourelim)

        logger.info("Preprocessing: {}".format(preprocessing_t))
        logger.info("Model runtime: {}".format(m.Runtime))
        # m.Params.LogFile = "gurobi_model_darp_sq.lp"
        # m.write("gurobi_model_darp_sq.lp")

        # ##############################################################
        # ### SHOW RESULTS #############################################
        # ##############################################################

        is_umbounded = m.status == GRB.Status.UNBOUNDED
        found_optimal = m.status == GRB.Status.OPTIMAL
        found_sol_within_time_limit = (
            m.status == GRB.Status.TIME_LIMIT and m.SolCount > 0
        )

        if is_umbounded:
            print("The model cannot be solved because it is unbounded")

        elif found_optimal or found_sol_within_time_limit:
            if found_sol_within_time_limit:
                print("TIME LIMIT ({} s) RECHEADED.".format(time_limit))

            var_flow = m.getAttr("x", m_var_flow)

            var_first_tier = m.getAttr("x", m_var_first_tier)

            var_invehicle_delay = m.getAttr("x", m_var_invehicle_delay)

            var_load = {
                k: int(v) for k, v in m.getAttr("x", m_var_load).items()
            }

            var_pickup_delay = m.getAttr('x', m_var_pickup_delay)

            var_arrival_time = m.getAttr("x", m_var_arrival_time)

            logger.info("REQUEST DICTIONARY")

            ############################################################
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

            # Dictionary of results per objective function
            dict_sol = dict()
            dict_sol["runtime"] = m.Runtime
            dict_sol["objective_functions"] = dict()

            for obj_number, obj_name in enumerate(obj_list):

                m.setParam(GRB.Param.ObjNumber, obj_number)

                solver_sol = {
                    "obj_n": [(i, v) for i, v in enumerate(m.ObjN) if v > 0.0001],
                    "obj_con": m.ObjNCon,
                    "obj_mip_gap": m.Params.MIPGap,
                    "obj_priority": m.ObjNPriority,
                    "obj_weight": m.ObjNWeight,
                    "obj_rel_tol": m.ObjNRelTol,
                    "obj_abs_tol": m.ObjNAbsTol,
                    "obj_val": m.ObjNVal,
                    "obj_name": m.ObjNName,
                    "obj_num": m.NumObj
                }

                dict_sol["objective_functions"][obj_name] = solver_sol

            vehicle_routes_dict = print_sol(
                vehicles,
                requests,
                travel_time_dict,
                valid_rides,
                start_date,
                var_arrival_time,
                var_invehicle_delay,
                var_flow,
                var_load,
                var_first_tier,
                var_pickup_delay
            )

            capacity_count = defaultdict(int)
            for v in vehicle_routes_dict:
                capacity_count[v.capacity] += 1

            dict_sol['capacity_count'] = capacity_count

            return dict_sol

        elif m.status == GRB.Status.INFEASIBLE:
            # IRREDUCIBLE INCONSISTENT SUBSYSTEM (IIS).
            # An IIS is a subset of the constraints and variable bounds
            # of the original model. If all constraints in the model
            # except those in the IIS are removed, the model is still
            # infeasible. However, further removing any one member
            # of the IIS produces a feasible result.
            logger.info('The model is infeasible. Computing IIS...')
            removed = []

            # Loop until we reduce to a model that can be solved
            while True:

                m.computeIIS()
                logger.info('The following constraint cannot be satisfied:')
                for c in m.getConstrs():
                    if c.IISConstr:
                        print('%s' % c.constrName)
                        # Remove a single constraint from the model
                        removed.append(str(c.constrName))
                        m.remove(c)
                        break
                logger.info('')

                m.optimize()
                status = m.status

                if status == GRB.Status.UNBOUNDED:
                    logger.info(
                        'The model cannot be solved because it is unbounded')
                    exit(0)
                if status == GRB.Status.OPTIMAL:
                    logger.info("Optimal found!")
                    break
                if status != GRB.Status.INF_OR_UNBD and status != GRB.Status.INFEASIBLE:
                    logger.info(
                        'Optimization was stopped with status %d' % status)
                    exit(0)

            logger.info(
                '\nThe following constraints were removed to get a feasible LP:')
            logger.info(removed)
            # """
            # """
            # # MODEL RELAXATION
            # # Relax the constraints to make the model feasible
            # print('The model is infeasible; relaxing the constraints')
            # orignumvars = m.NumVars
            # m.feasRelaxS(0, False, False, True)
            # m.optimize()
            # status = m.status
            # if status in (GRB.Status.INF_OR_UNBD, GRB.Status.INFEASIBLE, GRB.Status.UNBOUNDED):
            #     print('The relaxed model cannot be solved \
            #         because it is infeasible or unbounded')
            #     exit(1)

            # if status != GRB.Status.OPTIMAL:
            #     print('Optimization was stopped with status %d' % status)
            #     exit(1)

            # print('\nSlack values:')
            # slacks = m.getVars()[orignumvars:]
            # for sv in slacks:
            #     if sv.X > 1e-6:
            #         print('%s = %g' % (sv.VarName, sv.X))

            #raise Exception('Model is infeasible.')
            # exit(0)

        elif (
            m.status != GRB.Status.INF_OR_UNBD
            and m.status != GRB.Status.INFEASIBLE
        ):
            logger.info("Optimization was stopped with status %d" % m.status)
            # exit(0)
        else:
            logger.info("Cant find %d" % m.status)

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
        logger.info("Error reported: {}".format(str(GurobiError)))

    except Exception as e:
        logger.info(str(e))
        raise

    finally:
        pass
        # Reset indices of nodes
        # Node.reset()
        # Vehicle.reset()
        # Request.reset()

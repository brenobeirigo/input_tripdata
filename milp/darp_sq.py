import logging
from collections import defaultdict
from datetime import timedelta, datetime
from pprint import pprint

from gurobipy import Model, GurobiError, GRB, quicksum
from gurobipy.gurobipy import tuplelist

from milp.darp_sq_preprocessing import get_valid_rides_set, get_valid_visits
from model.Node import Node, NodePK, NodeDL
from model.Request import Request

# Objective function
TOTAL_PICKUP_DELAY = "pickup_delay"
TOTAL_RIDE_DELAY = "ride_delay"
TOTAL_DELAY = "total_delay"
N_PRIVATE_RIDES = "private_rides"
N_FIRST_TIER = "first_tier_rides"
TOTAL_FLEET_CAPACITY = "fleet_capacity"


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


def big_m(i, j, t_i_j):
    service_i = i.service_duration if i.service_duration else 0
    big_m = max(0, int(i.latest + t_i_j + service_i - j.earliest))
    return big_m


def big_w(k, i):
    return min(2 * k.capacity, 2 * k.capacity + (i.demand if i.demand else 0))


class ModelSQ:

    def __init__(
            self,
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

        self.vtype_time = GRB.INTEGER
        self.priority_list_low_to_high = ["C", "B", "A"]
        self.vehicles = vehicles
        self.requests = requests
        self.travel_time_dict = travel_time_dict
        self.service_quality_dict = service_quality_dict
        self.service_rate = service_rate
        self.obj_list = obj_list
        self.time_limit = time_limit
        self.start_date = start_date
        self.log_path = log_path
        self.lp_path = lp_path
        self.m = None

        self.logger = logging.getLogger('run_experiment.milp_execution')

        # Dictionary of results per objective function
        self.dict_sol = dict()

        # 1 if vehicle k travels arc (i,j)
        self.m_var_flow = None

        # 1 if user receives first-tier service levels
        self.m_var_first_tier = None

        # Request pickup delay in [0, 2*request_max_delay]
        self.m_var_pickup_delay = None

        # Arrival time of vehicle k at node i
        self.m_var_arrival_time = None

        # Load of compartment c of vehicle k at pickup node i
        self.m_var_load = None

        # Ride time of request i serviced by vehicle k
        self.m_var_invehicle_delay = None

        self.valid_rides = []

        self.valid_visits = []
        self.times = dict()
        self.class_hierarchical_objectives = {}
        self.hierarchical_objectives = {}

    def print_sol(self):

        vehicle_visits_dict = self.realize_solution_and_get_vehicle_visits_dict()

        vehicle_routes_dict = self.get_vehicle_routes_dict(vehicle_visits_dict)

        self.log_request_status()

        return vehicle_routes_dict

    def log_request_status(self):

        logger = logging.getLogger('run_experiment.milp_solution')
        logger.info("###### Requests")

        for r in self.requests:
            # logger.info(var_invehicle_delay[(r.serviced_by.pid, r.origin.pid)])
            logger.info("{r_info}{tier}".format(
                r_info=r.get_info(
                    min_dist=self.travel_time_dict[r.origin][r.destination]),
                tier=f"<tier={r.tier}>")
            )

    def get_vehicle_routes_dict(self, vehicle_visits_dict):

        logger = logging.getLogger('run_experiment.milp_solution')

        # Ordered list of nodes visited by each vehicle
        vehicle_routes_dict = dict()
        var_load = {
            k: int(v) for k, v in self.m.getAttr("x", self.m_var_load).items()
        }
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
                    trip_duration = self.travel_time_dict[precedent_node][current_node]

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
        return vehicle_routes_dict

    def realize_solution_and_get_vehicle_visits_dict(self):

        logger = logging.getLogger('run_experiment.milp_solution')

        var_flow = self.m.getAttr("x", self.m_var_flow)
        var_first_tier = self.m.getAttr("x", self.m_var_first_tier)
        var_invehicle_delay = self.m.getAttr("x", self.m_var_invehicle_delay)
        var_pickup_delay = self.m.getAttr('x', self.m_var_pickup_delay)
        var_arrival_time = self.m.getAttr("x", self.m_var_arrival_time)

        # Stores vehicle visits k -> from_node-> to_node
        vehicle_visits_dict = {k: dict() for k in self.vehicles}

        for k, i, j in self.valid_rides:
            # Stores which vehicle picked up request
            if isinstance(i, NodePK):
                i.parent.serviced_by = k
                # print("ALL - Pickup delay", i, ":", var_pickup_delay[i.pid])
                # print("ALL - Ride delay", k, ",", i, ":", var_invehicle_delay[k.pid, i.pid])

        total_pk = 0
        total_ride = 0

        logger.info("#### PICKUP AND RIDE DELAYS")
        for k, i, j in self.valid_rides:

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

                i.departure = self.start_date + timedelta(seconds=arr_i)
                j.arrival = self.start_date + timedelta(seconds=arr_j)

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
                        f"(pk={r.pk_delay:6.2f}/{i.parent.max_pickup_delay:6.2f}, "
                        f"ride={r.ride_delay:6.2f}/{r.max_in_vehicle_delay:6.2f}, "
                        f"tier={r.tier}), "
                        f"serviced_by={r.serviced_by}"
                    )

                vehicle_visits_dict[k][i] = j

        logger.info(f"#### TOTAL DELAY -> PK={total_pk:>5} RIDE={total_ride:>5}")
        return vehicle_visits_dict

    def run(self):

        print("STARTING DARP-SQ...")
        self.get_valid_rides_and_visits()

        try:

            self.create_model("DARP-SQ")
            self.declare_variables()

            # ### OBJECTIVE FUNCTION #######################################
            self.setup_objective_function()
            self.limit_time_execution()

            # ### ROUTING CONSTRAINTS ######################################
            self.vehicle_leave_pickup_node_once_only()
            self.single_vehicle_service_od_pair()
            self.vehicle_start_from_own_depot()
            self.vehicle_enter_pickup_node_and_leave()
            self.vehicle_enter_destination_node_and_leave_or_stay()
            self.guarantee_service_levels()
            self.arrival_time_consistency()

            # RIDE TIME CONSTRAINTS ########################################
            self.ride_time_od_greater_than_travel_time_od()
            self.limit_max_ride_time()
            self.ride_time_consistency()

            # TIME WINDOW CONSTRAINTS ######################################
            self.earliest_pickup_greater_than_earliest_arrival()
            self.first_tier_consistency()
            # self.second_tier_consistency()

            # LOADING CONSTRAINTS ##########################################
            self.load_consistency()
            self.load_min()
            self.load_max()
            self.terminal_delivery_nodes_have_no_load()
            self.vehicle_can_service_after_availability_time()
            self.vehicles_start_with_zero_load()

            # ### SHOW RESULTS #############################################
            self.log_model_formulation()

            # ### OPTIMIZE #################################################
            self.optimize_model()

            # ### SHOW RESULTS #############################################

            return self.extract_solution()

        except GurobiError:
            self.logger.info("Error reported: {}".format(str(GurobiError)))

        except Exception as e:
            self.logger.info(str(e))
            raise

        finally:
            pass
            # Reset indices of nodes
            # Node.reset()
            # Vehicle.reset()
            # Request.reset()

    def create_model(self, model_name):
        self.m = Model(model_name)

    def optimize_model(self):
        self.logger.info("Optimizing...")
        self.m.optimize()
        self.logger.info("Preprocessing: {}".format(self.times["preprocessing_t"]))
        self.logger.info("Model runtime: {}".format(self.m.Runtime))

    def extract_solution(self):
        if self.model_is_umbounded():
            print("The model cannot be solved because it is unbounded")

        elif self.model_is_optimal() or self.model_reached_time_limit_but_has_solution():

            if self.model_reached_time_limit_but_has_solution():
                print("TIME LIMIT ({} s) RECHEADED.".format(self.time_limit))

            return self.get_solution_dict()

        elif self.model_is_infeasible():
            self.computeIIS()

        elif (
                self.m.status != GRB.Status.INF_OR_UNBD
                and self.m.status != GRB.Status.INFEASIBLE
        ):
            self.logger.info("Optimization was stopped with status %d" % self.m.status)
            # exit(0)
        else:
            self.logger.info("Cant find %d" % self.m.status)

    def get_solution_dict(self):

        self.logger.info("REQUEST DICTIONARY")

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
        self.extract_runtime_from_model()
        self.extract_objective_functions_from_model()
        print("### Objective functions:")
        pprint(self.dict_sol)
        vehicle_routes_dict = self.print_sol()
        capacity_count = defaultdict(int)

        for v in vehicle_routes_dict:
            capacity_count[v.capacity] += 1
        self.dict_sol['capacity_count'] = capacity_count

        return self.dict_sol

    def log_model_formulation(self):
        try:
            # Save .lp file
            # if log_path is not None:
            #    m.write(log_path)

            if self.lp_path is not None:
                print(f"Saving {self.lp_path}")
                self.m.write(self.lp_path)
                self.m.setParam("LogToConsole", 0)
                self.m.Params.LogFile = self.lp_path

        except Exception as e:
            print(f"Cannot save MIP log! Error: {e}")

    def limit_time_execution(self):
        self.m.Params.timeLimit = self.time_limit

    def declare_variables(self):
        # 1 if vehicle k travels arc (i,j)
        self.add_var_flow()

        # 1 if user receives first-tier service levels
        self.add_var_first_tier()

        # Request pickup delay in [0, 2*request_max_delay]
        self.add_var_pickup_delay()

        # Arrival time of vehicle k at node i
        self.add_var_arrival_time()

        # Load of compartment c of vehicle k at pickup node i
        self.add_var_load()

        # Ride time of request i serviced by vehicle
        self.add_var_invehicle_delay()

    def add_var_flow(self):
        self.m_var_flow = self.m.addVars(
            [(k.pid, i.pid, j.pid) for k, i, j in self.valid_rides],
            vtype=GRB.BINARY,
            name="trip_k_i_j",
        )

    def add_var_first_tier(self):
        self.m_var_first_tier = self.m.addVars(
            [i.pid for i in Node.origins], vtype=GRB.BINARY, name="sq_achieved"
        )

    def add_var_pickup_delay(self):
        self.m_var_pickup_delay = self.m.addVars(
            [i.pid for i in Node.origins],
            vtype=self.vtype_time,
            lb=0,
            ub=[i.parent.max_total_delay for i in Node.origins],
            name="pickup_delay"
        )

    def add_var_arrival_time(self):
        self.m_var_arrival_time = self.m.addVars(
            [(k.pid, i.pid) for k, i in self.valid_visits],
            vtype=self.vtype_time,
            lb=0,
            name="arrival_time",
        )

    def add_var_load(self):
        self.m_var_load = self.m.addVars(
            [(k.pid, i.pid) for k, i in self.valid_visits],
            vtype=GRB.INTEGER,
            lb=0,
            name="load",
        )

    def add_var_invehicle_delay(self):
        invehicle_delay_tuples = []
        ubs = []
        lbs = []
        for k, i in self.valid_visits:
            if isinstance(i, NodePK):
                invehicle_delay_tuples.append((k.pid, i.pid))
                ubs.append(i.parent.max_total_delay)
                lbs.append(0)
        self.m_var_invehicle_delay = self.m.addVars(
            tuplelist(invehicle_delay_tuples),
            vtype=self.vtype_time,
            lb=lbs,
            ub=ubs,
            name="invehicle_delay",
        )

    def setup_objective_function(self):

        total_fleet_capacity = self.obj_total_fleet_capacity()

        class_number_of_private_rides = defaultdict(int)
        class_number_first_tier_requests = defaultdict(int)
        class_total_fleet_capacity = defaultdict(int)
        class_total_ride_delay = defaultdict(int)
        class_total_pickup_delay = defaultdict(int)
        class_total_delay = defaultdict(int)

        number_first_tier_requests = quicksum(
            self.m_var_first_tier[i.pid] for i in Node.origins
        )
        for i in Node.origins:
            print(i, i.parent.service_class, self.m_var_first_tier[i.pid])
            class_number_first_tier_requests[i.parent.service_class] -= self.m_var_first_tier[i.pid]
            class_total_pickup_delay[i.parent.service_class] += self.m_var_pickup_delay[i.pid]
            for k in self.vehicles:
                if (k, i) in self.valid_visits:
                    class_total_ride_delay[i.parent.service_class] += self.m_var_invehicle_delay[k.pid, i.pid]
            class_total_delay[i.parent.service_class] = class_total_ride_delay[i.parent.service_class] + \
                                                        class_total_pickup_delay[i.parent.service_class]
        # print("## NUMBER FIRST TIER REQUESTS")
        # for sq_class, exp in class_number_first_tier_requests.items():
        #     print(sq_class, exp)
        number_of_private_rides = quicksum(
            self.m_var_flow[k.pid, i.pid, j.pid]
            for k, i, j in self.valid_rides
            if i.parent == j.parent
        )
        total_pickup_delay = quicksum(
            self.m_var_pickup_delay[i.pid] for i in Node.origins
        )
        total_ride_delay = quicksum(
            self.m_var_invehicle_delay[k.pid, i.pid]
            for k in self.vehicles
            for i, j in Request.od_set
            if (k, i) in self.valid_visits
        )
        self.hierarchical_objectives = {
            TOTAL_PICKUP_DELAY: total_pickup_delay,
            N_PRIVATE_RIDES: number_of_private_rides,
            N_FIRST_TIER: number_first_tier_requests,
            TOTAL_FLEET_CAPACITY: total_fleet_capacity,
            TOTAL_RIDE_DELAY: total_ride_delay,
            TOTAL_DELAY: total_ride_delay + total_pickup_delay
        }
        self.class_hierarchical_objectives = {
            TOTAL_PICKUP_DELAY: class_total_pickup_delay,
            N_PRIVATE_RIDES: class_number_of_private_rides,
            N_FIRST_TIER: class_number_first_tier_requests,
            TOTAL_FLEET_CAPACITY: class_total_fleet_capacity,
            TOTAL_RIDE_DELAY: class_total_ride_delay,
            TOTAL_DELAY: class_total_delay
        }

        priority = 0
        obj_number = 0

        for obj_name in self.obj_list:

            if obj_name == TOTAL_FLEET_CAPACITY:
                self.setObjectiveN(total_fleet_capacity, obj_name, obj_number, priority)
                priority += 1
                obj_number += 1

            else:
                for sq_class in self.priority_list_low_to_high:
                    lin_expr = self.class_hierarchical_objectives[obj_name][sq_class]
                    classed_obj_name = self.get_classed_obj_name(obj_name, sq_class)
                    self.setObjectiveN(lin_expr, classed_obj_name, obj_number, priority)

                    priority += 1
                    obj_number += 1

        # Hierarchical objectives: finds the best solution for the
        # current objective, but only from among those that would
        # not degrade the solution quality for higher-priority
        # objectives.
        # for obj_name in self.obj_list:
        #
        #     # The higher is the priority, the more important is the
        #     # objective. The obj_list is sorted in order of priority.
        #
        #     self.setObjectiveN(of[obj_name], obj_name, obj_number, priority)
        #
        #     priority += 1
        #     obj_number += 1

    def obj_total_fleet_capacity(self):
        total_fleet_capacity = quicksum(
            k.capacity * self.m_var_flow[k.pid, i.pid, j.pid]
            for k, i, j in self.valid_rides
            if i in Node.depots
        )
        return total_fleet_capacity

    def computeIIS(self):
        # IRREDUCIBLE INCONSISTENT SUBSYSTEM (IIS).
        # An IIS is a subset of the constraints and variable bounds
        # of the original model. If all constraints in the model
        # except those in the IIS are removed, the model is still
        # infeasible. However, further removing any one member
        # of the IIS produces a feasible result.
        self.logger.info('The model is infeasible. Computing IIS...')
        removed = []
        # Loop until we reduce to a model that can be solved
        while True:

            self.m.computeIIS()
            self.logger.info('The following constraint cannot be satisfied:')
            for c in self.m.getConstrs():
                if c.IISConstr:
                    print('%s' % c.constrName)
                    # Remove a single constraint from the model
                    removed.append(str(c.constrName))
                    self.m.remove(c)
                    break
            self.logger.info('')

            self.m.optimize()
            status = self.m.status

            if self.model_is_umbounded():
                self.logger.info(
                    'The model cannot be solved because it is unbounded')
                exit(0)
            if self.model_is_optimal():
                self.logger.info("Optimal found!")
                break
            if self.model_reached_time_limit_but_has_solution():
                self.logger.info(
                    'Optimization was stopped with status %d' % status)
                exit(0)
        self.logger.info(
            '\nThe following constraints were removed to get a feasible LP:')
        self.logger.info(removed)

    def model_is_infeasible(self):
        infeasible = self.m.status == GRB.Status.INFEASIBLE
        return infeasible

    def model_reached_time_limit_but_has_solution(self):
        found_sol_within_time_limit = (
                self.m.status == GRB.Status.TIME_LIMIT and self.m.SolCount > 0
        )
        return found_sol_within_time_limit

    def model_is_optimal(self):
        return self.m.status == GRB.Status.OPTIMAL

    def model_is_umbounded(self):
        is_umbounded = self.m.status == GRB.Status.UNBOUNDED
        return is_umbounded

    def guarantee_service_levels(self):
        self.logger.info(
            "    # (10) SERVICE_TIER - Guarantee first-tier"
            " service levels for a share of requests in class"
        )
        for sq_class in Request.service_quality:
            self.guarantee_min_service_level_of_sq_class(sq_class)
            self.enforce_privacy_of_sq_class(sq_class)

    def enforce_privacy_of_sq_class(self, sq_class):
        sq_class_requests = Request.service_quality[sq_class]
        if not self.service_quality_dict[sq_class]["sharing_preference"]:

            self.logger.info(
                "    # (14) PRIVATE_RIDE {} - vehicle that picks up user"
                " from class {} is empty".format(sq_class, sq_class)
            )
            for request in sq_class_requests:
                self.constr_request_demands_private_ride(request)
                self.vehicle_carries_single_request_in_private_ride(request, sq_class)

    def guarantee_min_service_level_of_sq_class(self, sq_class):

        sq_class_requests = Request.service_quality[sq_class]
        total_first_tier_requests = quicksum(
            self.m_var_first_tier[r.origin.pid] for r in sq_class_requests
        )
        min_first_tier_requests = int(
            self.service_rate[sq_class] * len(sq_class_requests) + 0.5
        )
        self.m.addConstr(
            total_first_tier_requests >= min_first_tier_requests,
            "SERVICE_TIER[{}]".format(sq_class),
        )

    def vehicle_carries_single_request_in_private_ride(self, request, sq_class):
        for k in self.vehicles:
            if (k, request.origin) in self.valid_visits:
                self.m.addConstr(
                    (self.m_var_load[k.pid, request.origin.pid] <= request.demand),
                    "PRIVATE_PK_{}[{},{}]".format(
                        sq_class, k, request.origin.pid
                    ),
                )

    def constr_request_demands_private_ride(self, r):
        a = quicksum(
            self.m_var_flow[k.pid, r.origin.pid, r.destination.pid]
            for k in self.vehicles
            if (k, r.origin, r.destination) in self.valid_rides
        )
        self.m.addConstr(a == 1, "PRIVATE_RIDE[{}]".format(r))

    def vehicle_can_service_after_availability_time(self):
        self.logger.info("    # ARRI_AT_ORIGIN")
        # Guarantees a vehicle will be available only at an specified time
        # Some vehicles are discarded because they cannot access any node
        # (not a valid visit)
        self.m.addConstrs(
            (
                self.m_var_arrival_time[k.pid, k.pos.pid]
                == (k.available_at - self.start_date).total_seconds()
                for k in self.vehicles
            ),
            "ARRI_AT_ORIGIN",
        )

    def vehicles_start_with_zero_load(self):
        self.logger.info("    # LOAD_DEPOT_0")
        self.m.addConstrs(
            (self.m_var_load[k.pid, k.pos.pid] == 0 for k in self.vehicles),
            "LOAD_DEPOT_0",
        )

    def ride_time_od_greater_than_travel_time_od(self):
        self.logger.info("    # (7) RIDE_1")
        # (RIDE_1) = Ride time from i to j >= time_from_i_to_j
        self.m.addConstrs(
            (
                self.m_var_invehicle_delay[k.pid, i.pid] >= 0
                for k, i, j in self.valid_rides
                if (i, j) in Request.od_set
            ),
            "RIDE_1",
        )

    def second_tier_consistency(self):
        self.logger.info(
            "    # (13) SECOND_TIER - pickup delay"
            " in [max_pk_delay, 2*max_pk_delay)"
        )
        self.m.addConstrs(
            (
                self.m_var_pickup_delay[i.pid]
                <=
                i.parent.max_total_delay
                for i in Node.origins
            ),
            "SECOND_TIER",
        )

    def first_tier_consistency(self):
        self.logger.info(
            "    # (13) FIRST_TIER - pickup delay in [0, max_pk_delay)")
        self.m.addConstrs(
            (
                self.m_var_pickup_delay[i.pid]
                <= (
                        i.parent.max_pickup_delay * self.m_var_first_tier[i.pid]
                        + i.parent.max_total_delay * (1 - self.m_var_first_tier[i.pid])
                    )
                for i in Node.origins
            ),
            "FIRST_TIER",
        )

    def earliest_pickup_greater_than_earliest_arrival(self):
        self.logger.info(
            "    # (11) EARL - Earliest pickup time"
            " >= earliest arrival time"
        )
        self.m.addConstrs(
            (
                self.m_var_arrival_time[k.pid, i.pid]
                == i.earliest + self.m_var_pickup_delay[i.pid]
                for (k, i) in self.valid_visits
                if isinstance(i, NodePK)
            ),
            "EARL",
        )

    def ride_time_consistency(self):
        self.logger.info("    # ( 8) RIDE_TIME - Define user ride time")
        self.m.addConstrs(
            (
                self.m_var_invehicle_delay[k.pid, i.pid]
                == self.m_var_arrival_time[k.pid, j.pid]
                - self.m_var_arrival_time[k.pid, i.pid] - self.travel_time_dict[i][j]
                for k in self.vehicles
                for i, j in Request.od_set
                if (k, i, j) in self.valid_rides
            ),
            "RIDE_TIME",
        )

    def limit_max_ride_time(self):
        self.logger.info(
            "    # (12) MAX_RIDE_TIME - Maximum ride "
            "time of user is guaranteed"
        )
        self.m.addConstrs(
            (
                self.m_var_invehicle_delay[k.pid, i.pid]
                <= i.parent.max_total_delay - self.m_var_pickup_delay[i.pid]
                for k, i, j in self.valid_rides
                if (i, j) in Request.od_set
            ),
            "MAX_RIDE_TIME",
        )

    def arrival_time_consistency(self):
        self.logger.info("    # ( 6) ARRIVAL_TIME - Consistency arrival time")
        self.m.addConstrs(
            (
                self.m_var_arrival_time[k.pid, j.pid]
                >= self.m_var_arrival_time[k.pid, i.pid]
                + self.travel_time_dict[i][j]
                - big_m(i, j, self.travel_time_dict[i][j])
                * (1 - self.m_var_flow[k.pid, i.pid, j.pid])
                for k, i, j in self.valid_rides
            ),
            "ARRIVAL_TIME",
        )

    def vehicle_leave_pickup_node_once_only(self):
        self.logger.info(
            "    # (2) ALL_REQ - User base is serviced "
            "entirely (exactly once)"
        )
        self.m.addConstrs(
            (self.m_var_flow.sum("*", i.pid, "*") == 1 for i in Node.origins),
            "ALL_REQ",
        )

    def single_vehicle_service_od_pair(self):
        self.logger.info("    # (3) IF_V_PK_DL - Same vehicle services user's OD")
        self.m.addConstrs(
            (
                self.m_var_flow.sum(k.pid, i.pid, "*")
                - self.m_var_flow.sum(k.pid, "*", j.pid)
                == 0
                for k in self.vehicles
                for i, j in Request.od_set
                if (k, i, j) in self.valid_rides
            ),
            "IF_V_PK_DL",
        )

    def vehicle_start_from_own_depot(self):
        self.logger.info(
            "    # (4) FLOW_V_DEPOT - Vehicles start from their own depot")
        self.m.addConstrs(
            (self.m_var_flow.sum(k.pid, k.pos.pid, "*") <= 1 for k in self.vehicles),
            "FLOW_V_DEPOT",
        )

    def vehicle_enter_pickup_node_and_leave(self):
        self.logger.info("    # (5a) FLOW_V_O - Vehicles enter and leave pk nodes")
        self.m.addConstrs(
            (
                self.m_var_flow.sum(k.pid, "*", i.pid)
                == self.m_var_flow.sum(k.pid, i.pid, "*")
                for i in Node.origins
                for k in self.vehicles
            ),
            "FLOW_V_O",
        )

    def vehicle_enter_destination_node_and_leave_or_stay(self):
        self.logger.info(
            "    # (5b) FLOW_V_D - Vehicles enter"
            "and leave/stay destination nodes"
        )
        self.m.addConstrs(
            (
                self.m_var_flow.sum(k.pid, "*", i.pid)
                >= self.m_var_flow.sum(k.pid, i.pid, "*")
                for i in Node.destinations
                for k in self.vehicles
            ),
            "FLOW_V_D",
        )

    def load_consistency(self):
        self.logger.info("    # ( 7) LOAD - Guarantee load consistency")
        self.m.addConstrs(
            (
                self.m_var_load[k.pid, j.pid]
                >= self.m_var_load[k.pid, i.pid]
                + (j.demand if j.demand else 0)
                - big_w(k, i) * (1 - self.m_var_flow[k.pid, i.pid, j.pid])
                for k, i, j in self.valid_rides
            ),
            "LOAD",
        )

    def load_min(self):
        self.logger.info("    # (13a) LOAD_MIN -  max(0, node_demand)")
        self.m.addConstrs(
            (
                self.m_var_load[k.pid, i.pid]
                >= max(0, (i.demand if i.demand else 0))
                for k, i in self.valid_visits
            ),
            "LOAD_MIN",
        )

    def load_max(self):
        self.logger.info("    # (13b) LOAD_MAX - (capacity, capacity + node_demand)")
        self.m.addConstrs(
            (
                self.m_var_load[k.pid, i.pid]
                <= min(k.capacity, k.capacity + (i.demand if i.demand else 0))
                for k, i in self.valid_visits
            ),
            "LOAD_MAX",
        )

    def terminal_delivery_nodes_have_no_load(self):
        self.logger.info(
            "    # (13) LOAD_END_D - Terminal delivery nodes have load 0.")
        self.m.addConstrs(
            (
                self.m_var_load[k.pid, j.pid]
                <= (k.capacity + j.demand) * self.m_var_flow.sum(k.pid, j.pid, "*")
                for k, j in self.valid_visits
                if isinstance(j, NodeDL)
            ),
            "LOAD_END_D",
        )

    def get_valid_rides_and_visits(self):

        # Start time - loading model info
        preprocessing_start_t = datetime.now()
        # Eliminate unfeasible (v, o, d) rides:
        # - Capacity constraints
        # - Time window constraints
        # - Node unreachability
        self.valid_rides = get_valid_rides_set(
            self.vehicles,
            Request.node_pairs_dict,
            self.travel_time_dict
        )

        self.valid_visits = get_valid_visits(self.valid_rides)
        self.logger.info(" {} valid rides (k, i, j) created.".format(len(self.valid_rides)))
        self.logger.info(" {} valid visits (k, i) created.".format(len(self.valid_visits)))

        self.times["preprocessing_t"] = (datetime.now() - preprocessing_start_t).seconds

    def extract_runtime_from_model(self):
        self.dict_sol["runtime"] = self.m.Runtime

    def extract_objective_functions_from_model(self):
        self.dict_sol["objective_functions"] = dict()
        obj_number = 0
        for obj_name in self.obj_list:
            if obj_name == TOTAL_FLEET_CAPACITY:
                solver_sol = self.get_result_from_objective(obj_number)
                obj_number += 1
                self.dict_sol["objective_functions"][obj_name] = solver_sol

            else:
                for sq_class in self.priority_list_low_to_high:
                    classed_obj_name = self.get_classed_obj_name(obj_name, sq_class)
                    solver_sol = self.get_result_from_objective(obj_number)
                    obj_number += 1

                    self.dict_sol["objective_functions"][classed_obj_name] = solver_sol

    def get_classed_obj_name(self, obj_name, sq_class):
        return obj_name + "_" + sq_class

    def get_result_from_objective(self, obj_number):
        self.m.setParam(GRB.Param.ObjNumber, obj_number)
        solver_sol = {
            "obj_n": [(i, v) for i, v in enumerate(self.m.ObjN) if v > 0.0001],
            "obj_con": self.m.ObjNCon,
            "obj_mip_gap": self.m.Params.MIPGap,
            "obj_priority": self.m.ObjNPriority,
            "obj_weight": self.m.ObjNWeight,
            "obj_rel_tol": self.m.ObjNRelTol,
            "obj_abs_tol": self.m.ObjNAbsTol,
            "obj_val": self.m.ObjNVal,
            "obj_name": self.m.ObjNName,
            "obj_num": self.m.NumObj
        }
        return solver_sol

    def setObjectiveN(self, lin_expr, obj_name, obj_number, priority):
        self.m.setObjectiveN(
            lin_expr,
            priority=priority,
            index=obj_number,
            name=obj_name
        )
        self.logger.info(
            "Setting objective {} ({}) - priority: {}".format(
                obj_number, obj_name, priority
            )
        )

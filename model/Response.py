from model.Node import *
from dao.DaoHybrid import *
import pprint
import collections
import json
import logging
logger = logging.getLogger("main.opt_method.response")

class Response(object):

    # VARIABLES [K,I,J] COMING FROM GUROBI OPTIMIZATION
    # var_ride = binary variables Xkij
    # var_travel_t = Get travel self.times of each request
    # var_load = Get load of vehicle at each point
    # arrival_t = Get arrival time at each point

    def __init__(self,
                 vehicles,
                 requests_dic,
                 arcs,
                 vars,
                 rides,
                 travel_t,
                 load,
                 arrival_t,
                 DAO,
                 solver_sol):
        self.vehicles = vehicles
        self.requests_dic = requests_dic
        self.profit = solver_sol["obj_val"]
        self.solver_sol = solver_sol
        self.DAO = DAO
        self.arcs = arcs
        self.vars = vars
        self.rides = rides
        self.travel_t = travel_t
        self.load = load
        self.arrival_t = {(k,i):arrival_t[(k,i)] + config.start_revealing_tstamp for k,i in arrival_t}
        self.path = None
        # Profit accrued by requests
        self.profit_reqs = 0
        self.overall_detour_discount = 0
        self.all_requests = set([r.id
                                 for r in self.requests_dic.values()])

        self.attended_requests = dict()
        
        # Check rides[k, i, j] and create vehicles and nodes
        self.create_path()

        

        self.denied_requests = self.all_requests - self.attended_requests.keys()

        self.calculate_total_profit()
        
        self.setup_routing_info()

    def calculate_overall_detour_discount(self):
        for r in self.requests_dic.values():
            self.overall_detour_discount += self.DAO.discount_passenger * \
                r.get_detour_ratio()

    # Creates a response for a method, placing the step-by-step information
    # in each node.
    def create_path(self):
        vehicles_dic = self.DAO.vehicle_dic
        v_dic = dict()
        dic_order = dict()

        for k in self.DAO.vehicle_dic.keys():
            dic_order[k] = dict()

        ordered_v_nodes = defaultdict(lambda: defaultdict(str))
        nodes_vehicle = dict()
        for k, i, j in self.vars:
            
            # If there is a path from i to j by vehicle k
            # WARNING - FLOATING POINT ERROR IN GUROBI
            """
            This can happen due to feasibility and integrality tolerances.
            You will also find that solution that Gurobi (as all floating-
            point based MIP solvers) provides may slightly violate your 
            constraints. 

            The reason is that floating-point numeric as implemented in 
            the CPU hardware is not exact. Rounding errors can (and 
            usually will) happen. As a consequence, MIP solvers use 
            tolerances within which a solution is still considered to be 
            correct. The default tolerance for integrality in Gurobi 
            is 1e-5, the default feasibility tolerance is 1e-6. This means 
            that Gurobi is allowed to consider a value that is at most 
            1e-5 away from an integer to still be integral, and it is 
            allowed to consider a constraint that is violated by at most
            1e-6 to still be satisfied.
            """
            
            if self.rides[k, i, j] > 0.9:
                arr_i = self.arrival_t[k, i]
                arr_j = self.arrival_t[k, j]
                ordered_v_nodes[k][i] = j
            
        
        for k, from_to in ordered_v_nodes.items():
            node_id = self.DAO.vehicle_dic[k].pos.id
            ordered_list = list()
            while True:
                ordered_list.append(node_id)
                next_id = from_to[node_id]
                node_id = next_id
                if node_id not in from_to.keys():
                    ordered_list.append(node_id)
                    break
            nodes_vehicle[k] = ordered_list
                
                
            
        #print("ORDERED")
        #pprint.pprint(ordered_v_nodes)
        print("ORDERED")
        pprint.pprint(nodes_vehicle)
                
        for k, route in nodes_vehicle.items():
            vehicle = vehicles_dic[k]
            path = vehicle.path
            
            for i in route:
                # Departure node
                dep_node = self.DAO.nodes_dic[i]
                
                #if isinstance(dep_node, NodePK):
                #    print("DURATION",k,i, "=", Node.get_formatted_duration_h(self.travel_t[k, i]))

 
                #print("--#####",k, i, self.arrival_t[k, i], Node.get_formatted_time_h(self.arrival_t[k, i]))

                path[i] = self.get_updated_node2(vehicle, dep_node)

                if isinstance(dep_node, NodePK):
                    req = self.requests_dic[i]
                    req.update_status(vehicle.id, self.travel_t[k, i], self.arrival_t[k, i])
                    self.attended_requests[i] = req
        
        logger.info("SELECTED REQUESTS: %s", str(self.attended_requests.keys()))
        
        print("SELECTED REQUESTS: ", str(self.attended_requests.keys()), len(self.attended_requests))

    def calculate_total_profit(self):
        for r in self.attended_requests.values():
            # print("R:", r, " --S:", r.get_vehicle_scheduled_id())
            if r.get_vehicle_scheduled_id() != None:
                vehicle_mode = self.DAO.vehicle_dic[r.get_vehicle_scheduled_id()].type_vehicle
                self.profit_reqs += r.get_fare(mode=vehicle_mode)

    def print_requests_info(self):

        # Calculate overall detour discount
        self.calculate_overall_detour_discount()
        
        # Dictionary of vehicles per type
        self.mix_v = defaultdict(set)

        # Print requests ordered by pk time
        for r in self.attended_requests.values():

            #Get type of vehicle that attended the request
            type_v = self.DAO.vehicle_dic[r.get_vehicle_scheduled_id()].type_vehicle
            
            # Add vehicle to dic of type
            self.mix_v[type_v].add(r.get_vehicle_scheduled_id())
            
            print("### %r ### (RE: %r -> PK (%s): %r -> DL (%s): %r) ETA: %r || TRAVEL TIME: %r || DELAY: %r || FARE: $%.2f || DISCOUNT: $%.2f || VEHICLE: %r" %
                  (r.id,
                   Node.get_formatted_time(r.get_revealing_tstamp()),
                   Node.get_formatted_duration_m(r.origin.service_t),
                   Node.get_formatted_time_h(r.get_pk_time()),
                   Node.get_formatted_duration_m(r.destination.service_t),
                   Node.get_formatted_time_h(r.get_dl_time()),
                   Node.get_formatted_duration_h(r.get_eta()),
                   Node.get_formatted_duration_h(r.get_distance(self.DAO)[type_v]),
                   Node.get_formatted_duration_h(r.get_travel_delay(self.DAO)),
                   r.get_fare(mode=type_v),
                   self.DAO.discount_passenger * r.get_detour_ratio(),
                   r.get_vehicle_scheduled_id()))

            logger.info("### %r ### (RE: %r -> PK (%s): %r -> DL (%s): %r) ETA: %r || TRAVEL TIME: %r || DELAY: %r || FARE: $%.2f || DISCOUNT: $%.2f || VEHICLE: %r",
                  r.id,
                   Node.get_formatted_time(r.get_revealing_tstamp()),
                   Node.get_formatted_duration_m(r.origin.service_t),
                   Node.get_formatted_time_h(r.get_pk_time()),
                   Node.get_formatted_duration_m(r.destination.service_t),
                   Node.get_formatted_time_h(r.get_dl_time()),
                   Node.get_formatted_duration_h(r.get_eta()),
                   Node.get_formatted_duration_h(r.get_distance(self.DAO)[type_v]),
                   Node.get_formatted_duration_h(r.get_travel_delay(self.DAO)),
                   r.get_fare(mode=type_v),
                   self.DAO.discount_passenger * r.get_detour_ratio(),
                   r.get_vehicle_scheduled_id())
        
        # Print vehicle mix: type -> list of vehicles from type
        pprint.pprint(self.mix_v)

        # Define vehicle mix: type -> #vehicles
        self.mix_n = {k:len(v) for k,v in self.mix_v.items()}

        # Define mix cost: type -> total cost 
        self.mix_cost = {t_v:sum([self.DAO.vehicle_dic[v].acquisition_cost for v in vehicles]) for t_v, vehicles in self.mix_v.items()}

        # Log route
        print(self.route_v)
        logger.info(self.route_v)

        print("------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        print("OVERALL OCCUPANCY: %.2f || OPERATING VEHICLES: %d [%s] || OF: %.2f { %.2f (REQUESTS REVENUE) -  %.2f (OPERATIONAL COSTS) - [%s] (ACQUISITION) }" %
              (self.overall_occupancy_v,
               self.n_vehicles,
               " | ".join([k + " = " + str(n) for k,n in self.mix_n.items()]),
               round(float(self.profit), 2),
               self.profit_reqs,
               self.overall_operational_cost,
               " | ".join([k + " = " + str("{0}".format(v)) for k,v in self.mix_cost.items()]),
               ))
        print("------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        logger.info("-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        logger.info("OVERALL OCCUPANCY: %.2f || OPERATING VEHICLES: %d [%s] || OF: %.2f { %.2f (REQUESTS REVENUE) -  %.2f (OPERATIONAL COSTS) - [%s] (ACQUISITION) }",
              self.overall_occupancy_v,
               self.n_vehicles,
               " | ".join([k + " = " + str(n) for k,n in self.mix_n.items()]),
               round(float(self.profit), 2),
               self.profit_reqs,
               self.overall_operational_cost,
               " | ".join([k + " = " + str("{0}".format(v)) for k,v in self.mix_cost.items()]),
               )
        logger.info("------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        
    def get_json(self):
        js = '{{"config":{{\
                            "cost_per_s":{0},\
                            "discount_passenger_s":{1},\
                            "compartment_data":{8}\
                            }},\
                    "nodes":[{2}], \
                    "requests":[{3}], \
                    "vehicles":[{4}], \
                    "result_summary":{{\
                            "attended_requests":[{5}],\
                            "all_requests":[{6}],\
                            "denied_requests":[{7}],\
                            "overall_occupancy":{9},\
                            "operating_vehicles":{10},\
                            "profit":{11},\
                            "profit_comp":{{\
                                "requests_revenue":{12},\
                                "operational_costs":{13},\
                                "detour_discount":{14}\
                            }},\
                            "mip_solution":{{\
                                "gap": {15},\
                                "num_vars": {16},\
                                "num_constrs": {17},\
                                "obj_bound": {18},\
                                "obj_val": {19},\
                                "node_count": {20},\
                                "sol_count": {21},\
                                "iter_count": {22},\
                                "runtime": {23}\
                            }}\
                    }}\
                }}'\
        .format(-111111,
                self.DAO.discount_passenger,
                ",".join(n.get_json() for n in self.DAO.nodes_dic.values()),
                ",".join(r.get_json() for r in self.DAO.request_list),
                ",".join(v.get_json() for v in self.DAO.vehicle_dic.values() if v.is_used()),
                ",".join('"' + v + '"' for v in self.attended_requests),
                ",".join('"' + v + '"' for v in self.all_requests),
                ",".join('"' + v + '"' for v in self.denied_requests),
                self.DAO.get_json_compartment_data(),
                self.overall_occupancy_v,
                self.n_vehicles,
                round(float(self.profit), 2),
                self.profit_reqs,
                self.overall_operational_cost,
                self.overall_detour_discount,
                self.solver_sol["gap"],
                self.solver_sol["num_vars"],
                self.solver_sol["num_constrs"],
                self.solver_sol["obj_bound"],
                self.solver_sol["obj_val"],
                self.solver_sol["node_count"],
                self.solver_sol["sol_count"],
                self.solver_sol["iter_count"],
                self.solver_sol["runtime"])
        return js
 
    # Print the route within each vehicle and all routes statistics
    def setup_routing_info(self):

        self.route_v = ""
        self.overall_occupancy = 0
        self.n_vehicles = 0
        self.overall_operational_cost = 0
        self.overall_detour_discount = 0

        # For each vehicle ID
        for k in self.vehicles:
            v = self.DAO.vehicle_dic[k]

            # If vehicle v is used
            if v.is_used():
                # Create vehicle occupancy statistics per compartment
                # in relation to operational time (travel time between points)
                # using DAO data
                v.calculate_vehicle_occupancy(self.DAO)

                # Sum individual overall occupancy of each vehicle (route)
                self.overall_occupancy += v.overall_avg_occupancy

                self.overall_operational_cost += v.operational_cost
                # Increment number of active vehicles
                self.n_vehicles += 1
                self.route_v += str(v)

        self.overall_occupancy_v = (self.overall_occupancy * 100 / self.n_vehicles if self.n_vehicles > 0 else 0)

    # Return a copy of the node with load and arrival values
    # updated. This way, every vehicle has a copy of the
    # departure and arrival nodes.
    def get_updated_node(self, vehicle, node, next):
        node_copy = None
        # Depots don't need to be copied
        if not isinstance(node, NodeDepot):
            node_copy = node
        else:
            node_copy = Node.copy_node(node)
            
        arrival = self.arrival_t[vehicle.id, node_copy.id]
        node_copy.set_arrival_t(arrival)
        node_copy.vehicle =  vehicle
        node_copy.id_next = next
        for c in vehicle.capacity.keys():
            node_copy.load[c] = self.load[c,
                                                vehicle.id,
                                                node_copy.id]
        return node_copy


    # Return a copy of the node with load and arrival values
    # updated. This way, every vehicle has a copy of the
    # departure and arrival nodes.
    def get_updated_node2(self, vehicle, node, id_next=None):
        node_copy = None
        # Depots don't need to be copied
        if not isinstance(node, NodeDepot):
            node_copy = node
        else:
            node_copy = Node.copy_node(node)
        arrival = self.arrival_t[vehicle.id, node_copy.id]
        node_copy.set_arrival_t(arrival)
        node_copy.vehicle = vehicle
        for c in vehicle.capacity.keys():
            node_copy.load[c] = self.load[c,
                                                vehicle.id,
                                                node_copy.id]
        node_copy.id_next = id_next
        return node_copy

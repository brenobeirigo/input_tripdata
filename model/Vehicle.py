import random

random.seed(1)
import collections
from model.Route import Route
from collections import OrderedDict


class Vehicle:
    n_vehicles = 0

    def __init__(self, pos, capacity, available_at, type_vehicle=None):

        self.id = Vehicle.n_vehicles

        self.type_vehicle = type_vehicle

        # Initial position vehicle (Node)
        self.pos = pos

        # Vehicle is the parent of its departure node
        self.pos.parent = self

        # Time when vehicle is available (DateTime)
        self.available_at = available_at

        # Capacity of vehicles (compartments available != 0)
        self.capacity = capacity

        # Update vehicle count
        Vehicle.n_vehicles += 1

        # Setup initial operation settings
        self.reset()

    @classmethod
    def reset_elements(cls):

        cls.n_vehicles = 0

    def reset(self):

        # Average occupancy of vehicle's compartments in relation
        # to travel_time
        self.avg_occupancy_c = {}
        # Overall average occupancy of vehicle considering all
        # compartments throughout the entire travel time
        self.overall_avg_occupancy = 0
        self.operational_cost = 0
        # If requests origin == vehicle origin, departure time, there are two
        # nodes (DP and PK) related to the same key (00:00), since vehicle does
        # not need to travel to arrive in PK. Hence, the key 00:00 will carry a set
        # of nodes to cover this special case.
        self.path = OrderedDict()

    # Check if vehicle is used
    # Case positive -> path > 2 (depot nodes)
    def is_used(self):
        # Don't show not used vehicles
        if len(self.path.keys()) <= 2:
            return False
        return True

    def add_node(self, node):
        self.path[node.id] = node

    # def __str__(self):
    #     current_node = self.pos.id
    #     print(self.path.keys())
    #     s = '#' + str(self.id) + ':\n'
    #     while current_node in self.path.keys():
    #         next_node = self.path[current_node].id_next
    #         s += str(current_node) + ' -> ' + str(next_node)\
    #             + ': ' + str(self.path[current_node]) + '\n'
    #         current_node = next_node
    #     return s

    def __str__(self):
        return "V_{:04}".format(self.id)

    @property
    def pid(self):
        return "V{id}({capacity})".format(
            id=self.id,
            capacity=self.capacity
        )

    def get_info(self):
        return "{} <{}> ### - {} ({})".format(
            self.__str__(),
            self.available_at.strftime('%H:%M:%S'),
            self.pos,
            self.capacity
        )

    def __repr__(self):
        return str(self) + super().__repr__()

    # def __repr__(self):
    #     current_node = self.pos.id
    #     print(self.path.keys())
    #     s = '#' + self.id + ':\n'
    #     while current_node in self.path.keys():
    #         next_node = self.path[current_node].id_next
    #         s += str(current_node) + ' -> ' + str(next_node)\
    #             + ': ' + str(self.path[current_node]) + '\n'
    #         current_node = next_node
    #     return s

    # Calculate vehicle proportional occupancy of each compartment
    # by time ridden
    def calculate_vehicle_occupancy(self, DAO):

        ############### VEHICLE ROUTE OCCUPANCY ####################

        self.route = Route(DAO, self.path, self.pos)

        # Get vehicle's capacity
        capacity_vehicle = self.capacity

        # for i in range(0, len(list_nodes) - 1):
        for leg in self.route.legs_dic.values():

            # Starting node (origin)
            origin = leg.origin

            # Get the current (destination) node
            destination = leg.destination

            # Distance disconsidering pk/dp service time
            dist = self.route.legs_dic[(
                origin, destination)].travel_t

            # Operational cost of leg
            leg_op_cost = self.operation_cost_s * dist

            # Add leg operational cost to the total cost
            self.operational_cost += leg_op_cost

            """print("&&&OC", origin, " -> ", destination, ":", Node.get_formatted_duration_h(dist),
                  self.operation_cost_s, leg_op_cost, self.operational_cost)"""

            origin_dest_delay = leg.invehicle_t

            # Get the load departing from the origin node (after loading)
            load_origin = self.path[origin].load
            load_destination = self.path[destination].load

            # Proportional time of complete route rode from
            # origin to destination
            proportional_time = leg.proportional_t

            # Log of occupation data for each compartment c of vehicle
            occupation_log_c = collections.OrderedDict()

            for c in capacity_vehicle.keys():
                # Determine how full a parcel locker c remained occupied
                # from origin to destination
                from_to_parcel_occup = load_origin[c] / capacity_vehicle[c]

                # Stores the truest occupation of the compartiment
                # in relation to the route total time
                partial_occupation = proportional_time * from_to_parcel_occup

                # If c not yet stored in the the average_occupation array
                if c not in self.avg_occupancy_c.keys():
                    self.avg_occupancy_c[c] = 0

                # Store the sum of all proportional occupation measures
                # for all parcel
                self.avg_occupancy_c[c] += partial_occupation

                # From origin to destination:
                # Compartment "c" is "from_to_parcel_occup" % occupied
                # what corresponds to "partial_occupation" % of the total route
                occupation_log_c[c] = from_to_parcel_occup

            # Remove not occupied compartments
            occupation_log_c = {
                c: occupation_log_c[c]
                for c in occupation_log_c.keys()
                if occupation_log_c[c] != 0}

            # Store leg occupation log
            leg.occupation_log_c = occupation_log_c

            # print("LOAD_ORIGIN", load_origin, "OCC. Log:", occupation_log_c)

            self.route.legs_dic[(
                origin, destination)].load_origin_dic = load_origin

        # Filter compartments not occupied during the whole route
        # (avg_occupation = 0)
        self.avg_occupancy_c = {
            c: self.avg_occupancy_c[c]
            for c in self.avg_occupancy_c.keys()
        }
        #    if self.avg_occupancy_c[c] != 0}

        self.overall_avg_occupancy = sum(self.avg_occupancy_c.values()) / float(len(self.capacity))

        """print("\n TOTAL TIME:", self.route.total_invehicle_t,
              "( travel times + service times from ORIGIN to DESTINATION)")"""

    # def __repr__(self):
    #      # Get the list of nodes ordered by visitation order
    #     #list_nodes = self.route.ordered_list

    #     # print("LIST NODES: ", list_nodes)

    #     # If vehicle is not used, its data is irrelevant and
    #     # therefore not shown
    #     # print("items:", self.capacity.items())
    #     js = '{'
    #     if not self.is_used():
    #         s = self.id + ' - ' + self.type_vehicle + ' - (' + str(self.pos) +')' + ",still,"
    #         s += "-".join(['{0:>3}:{1:<3}'.format(k, v)
    #                        for k, v in self.capacity.items()])

    #         js += '"vehicle_id": "' + self.id + '"'
    #         js += ', "vehicle_is_used": true'
    #         js += ', "vehicle_compartment_set":['
    #         js += ",".join(['{{"compartment_id":"{0}", "compartment_amount":{1}, "compartment_current_occupation": 0}}'.format(k, v)
    #                         for k, v in self.capacity.items()])
    #         js += ']}'
    #         return s

    #     s = '\n###### ' + self.id + \
    #         ' ###############################################################'

    #     # Print route
    #     # e.g.:
    #     # H_006 - 12:45:00  |PK011| - LOAD: {'XL': 4}
    #     # H_006 - 12:48:21  |DL012| - LOAD: {}
    #     # H_007 - 12:48:35  |PK013| - LOAD: {'XL': 2}

    #     s += '\nCAPACITY: '
    #     for c in self.capacity:
    #         s += c + ":" + str(self.capacity[c]) + " / "
    #     s += "\nAVG. OCCUPANCY (COMPARTMENT): "
    #     for c in self.avg_occupancy_c:
    #         s += c + ":" + \
    #             str("%.4f" %
    #                 round(self.avg_occupancy_c[c] * 100, 2)) + "%" + " / "
    #     s += "\nOVERALL AVERAGE OCCUPANCY: " + \
    #         str("%.4f" % round(self.overall_avg_occupancy * 100, 2)) + "%" + "\n"
    #     s += "OPERATIONAL COSTS:  ${0:<2} ".format(self.operational_cost)

    #     s += str(self.route)

    #     """print("LOG LEGS")
    #     print(Leg.get_labels_line())
    #     for v in self.route.legs_dic.values():
    #         print(v)"""

    #     return str(s)

    # def __str__(self):
    #     # Get the list of nodes ordered by visitation order
    #     #list_nodes = self.route.ordered_list

    #     # print("LIST NODES: ", list_nodes)

    #     # If vehicle is not used, its data is irrelevant and
    #     # therefore not shown
    #     if not self.is_used():
    #         s = "->" + self.id +'('+str(self.pos)+')' + "-- STATUS: still"
    #         s += "->" + self.id + "-- STATUS: still"
    #         s += "/".join(['{0:>3}={1:<2}'.format(k, v)
    #                        for k, v in self.capacity.items()])
    #         return s

    #     s = '\n---###### ' + self.id + \
    #         ' ###############################################################'

    #     # Print route
    #     # e.g.:
    #     # H_006 - 12:45:00  |PK011| - LOAD: {'XL': 4}
    #     # H_006 - 12:48:21  |DL012| - LOAD: {}
    #     # H_007 - 12:48:35  |PK013| - LOAD: {'XL': 2}
    #     s += str(self.route)

    #     s += '\nCAPACITY: '
    #     for c in self.capacity:
    #         s += c + ":" + str(self.capacity[c]) + " / "
    #     s += "\nAVG. OCCUPANCY (COMPARTMENT): "
    #     for c in self.avg_occupancy_c:
    #         s += c + ":" + \
    #             str("%.4f" %
    #                 round(self.avg_occupancy_c[c] * 100, 2)) + "%" + " / "
    #     s += "\nOVERALL AVERAGE OCCUPANCY: " + \
    #         str("%.4f" % round(self.overall_avg_occupancy * 100, 2)) + "%" + "\n"
    #     s += "OPERATIONAL COSTS:  ${0:.2f} ".format(self.operational_cost)

    #     """print("LOG LEGS")
    #     print(Leg.get_labels_line())
    #     for v in self.route.legs_dic.values():
    #         print(v)"""
    #     return str(s)

    def get_json(self):
        print("COLOR:", self.color)
        js = '{'
        js += '"vehicle_id": "' + self.id + '"'
        js += ', "vehicle_is_used":' + str(self.is_used()).lower()
        js += ', "vehicle_color": "' + self.color + '"'
        js += ', "available_at":"{0}"'.format(
            Node.get_formatted_time(self.available_at))
        js += ', "lat":' + str(self.pos.coord.y)
        js += ', "lng":' + str(self.pos.coord.x)
        js += ', "autonomy":' + str(self.autonomy)
        js += ', "vehicle_compartment_set":['
        js += ",".join(['{{"compartment_id":"{0}", "compartment_amount":{1}, "compartment_avg_occupancy": {2}}}'.format(
            k, v, self.avg_occupancy_c[k]) for k, v in self.capacity.items()])
        js += ']'
        js += ', "vehicle_overall_avg_occupancy":{0}'.format(
            round(self.overall_avg_occupancy * 100, 2))
        js += ', "vehicle_operational_costs":{0}'.format(self.operational_cost)
        js += ', "vehicle_route":' + self.route.get_json()
        js += '}'
        return js

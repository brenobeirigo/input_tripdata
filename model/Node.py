from model.Coordinate import Coordinate
from datetime import *
import time


# Class node
class Node:
    # Number of pickup/delivery nodes
    n_nodes = 1
    # Number of depots
    d_nodes = 1

    TYPE_ORIGIN = 0
    TYPE_DESTINATION = 1
    TYPE_DEPOT = 3

    depots = set()
    origins = set()
    destinations = set()
    ods = set()

    def __init__(self, x, y, network_node_id=None, service_duration = 0):
        self.id = Node.get_n_nodes()
        self.coord = Coordinate(x, y)
        self.network_node_id = network_node_id
        self.arrival = None
        self.departure = None
        self.service_duration = 0
        Node.increment_id()

    @classmethod
    def reset_elements(cls):
        
        # Number of pickup/delivery nodes
        cls.n_nodes = 1
        # Number of depots
        cls.d_nodes = 1

        cls.depots = set()
        cls.origins = set()
        cls.destinations = set()
        cls.ods = set()

    def reset(self):
        self.arrival_t = 0
        self.load = {}
        self.id_next = None
        self.vehicle = None

    @classmethod
    def reset_nodes_ids(cls):
        # Number of pickup/delivery nodes
        cls.n_nodes = 1
        # Number of depots
        cls.d_nodes = 1

    @staticmethod
    def get_formatted_time(time):
        
        if time == 0:
            return "---------- --:--:--"
        elif type(time) == datetime:
            return time.strftime('%Y-%m-%d %H:%M:%S')
        else:

            return datetime.fromtimestamp(int(time)).strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def get_formatted_time_h(time):
        if time == 0:
            return "--:--:--"
        else:
            return datetime.fromtimestamp(int(time)).strftime('%H:%M:%S')

    @staticmethod
    def get_formatted_duration_h(time):
        if time == 0:
            return "--:--:--"
        else:
            return datetime.fromtimestamp(int(time), timezone.utc).strftime('%H:%M:%S')

    
    @staticmethod
    def get_formatted_duration_m(time):
        if time == 0:
            return "--:--"
        else:
            return datetime.fromtimestamp(int(time), timezone.utc).strftime('%M:%S')

    def set_arrival_t(self, arrival_t):
        self.arrival_t = arrival_t

    def is_visited(self):
        return self.arrival_t > 0

    def get_load_0(self):
        return {id: int(self.load[id]) for id in self.load.keys() if abs(int(self.load[id])) != 0}

    @classmethod
    def increment_id(self):
        Node.n_nodes = Node.n_nodes + 1

    @classmethod
    def increment_id_depot(self):
        Node.d_nodes = Node.d_nodes + 1

    @classmethod
    def get_n_nodes(self):
        return Node.n_nodes

    @classmethod
    def get_d_nodes(self):
        return Node.d_nodes

    @classmethod
    def factory_node(cls, type_node, x, y, demand=None, parent=None, network_node_id=None, service_duration = 0):
        if type_node == cls.TYPE_DESTINATION:
            d = NodeDL(x, y, demand, parent, network_node_id=network_node_id, service_duration = service_duration)
            cls.destinations.add(d)
            cls.ods.add(d)
            return d

        elif type_node == cls.TYPE_ORIGIN:
            o = NodePK(x, y, demand, parent, network_node_id=network_node_id, service_duration = service_duration)
            cls.origins.add(o)
            cls.ods.add(o)
            return o

        elif type_node == cls.TYPE_DEPOT:
            depot = NodeDepot(x, y, network_node_id=network_node_id)
            cls.depots.add(depot)
            return depot
            
        else:
            return None

    def __str__(self):
        return "_{:04}".format(self.id)
    
    def __repr__(self):
        return str(self) + super().__repr__()

# Pickup node
class NodePK(Node):
    def __init__(self, x, y, demand, parent, network_node_id=None, service_duration = 0):
        super().__init__(x, y, network_node_id=network_node_id, service_duration = service_duration)
        self.demand = demand
        self.parent = parent

    def __str__(self):
        return "O{}".format(super().__str__())
    
    @property
    def pid(self):
        """Print node with parent id.
        
        Returns:
            str -- Node alias with parent id.
        """

        return "O{}".format(self.parent.id)
        
    def get_info(self):
        return self.parent + " - " + Node.get_formatted_time(self.arrival_t) \
            + '  |' + self.id + '|' \
            + ' - LOAD: ' \
            + str({id: int(self.load[id])
                   for id in self.load.keys()
                   if int(self.load[id]) > 0})
                
# Delivery node
class NodeDL(Node):
    def __init__(self, x, y, demand, parent, network_node_id=None, service_duration = 0):
        super().__init__(x, y, network_node_id=network_node_id, service_duration = service_duration)
        self.demand = demand
        self.parent = parent

    def __str__(self):
        return "D{}".format(super().__str__())

    @property
    def pid(self):
        """Print node with parent id.
        
        Returns:
            str -- Node alias with parent id.
        """

        return "D{}".format(self.parent.id)


    def get_info(self):
        # return '|DL|' + super().__str__() + ' - LOAD: ' + str({id:int(self.load[id]) for id in self.load.keys() if int(self.load[id])>0}) + ' - ARR: ' + datetime.fromtimestamp(int(self.arrival_t)).strftime('%Y-%m-%d %H:%M:%S')
        return self.parent + " - " + Node.get_formatted_time(self.arrival_t) + '  |' + self.id + '|' + ' - LOAD: ' + str({id: int(self.load[id]) for id in self.load.keys() if int(self.load[id]) > 0})


# Departure/arrival node
class NodeDepot(Node):

    def __init__(self, x, y, parent=None, network_node_id=None, service_duration = 0):
        super().__init__(x, y, network_node_id=network_node_id, service_duration = service_duration)
        self.parent = parent
        self.demand = None

    def __str__(self):
        return "X{}".format(super().__str__())
    
    
    @property
    def pid(self):
        """Print node with parent id.
        
        Returns:
            str -- Node alias with parent id.
        """

        return "X{}".format(self.parent.id)

    def get_info(self):
        # print("STR: ", self.arrival_t)
        # load = (
        #     self.load
        #     if 
        #         type(self.load) == int
        #     else
        #         str(
        #             {
        #                 id: int(self.load[id])
        #                 for id in self.load.keys()
        #                 if int(self.load[id]) > 0
        #             }
        #         )
        # )

        return 'START - {} | {} ({}) | - LOAD: {}'.format(
            Node.get_formatted_time(self.arrival_t),
            self.id,
            str(self.network_node_id),
            str(self.load)
        )
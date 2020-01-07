from model.Coordinate import Coordinate
from model.Node import *
from collections import defaultdict
import time
import pandas as pd


class Request(object):

    count = 0

    parcel_lockers = set(['XS', 'S', 'M', 'L', 'XL'])
    seats = set(['A', 'C', 'B', 'I'])
    
    # Store the overall pairs
    node_pairs_dict = {}
    od_set = set()

    service_quality = defaultdict(list)


    @classmethod
    def reset_elements(cls):
        
        cls.count = 0
        # Store the overall pairs
        cls.node_pairs_dict = {}
        cls.od_set = set()

        cls.service_quality = defaultdict(list)

    def __init__(
        self,
        revealing_datetime,
        max_pickup_delay,
        max_total_delay,
        pickup_id,
        dropoff_id,
        demand,
        pickup_latitude=None,
        pickup_longitude=None,
        dropoff_latitude=None,
        dropoff_longitude=None,
        service_class = None,
        service_duration = 0):
        """[summary]
        
        Arguments:
            id {[type]} -- [description]
            revealing_datetime {datetime} -- Earliest pickup time
            max_pickup_delay {[type]} -- [description]
            max_total_delay {[type]} -- [description]
            pickup_id {[type]} -- [description]
            dropoff_id {[type]} -- [description]
            demand {[type]} -- [description]
        
        Keyword Arguments:
            pickup_latitude {[type]} -- [description] (default: {None})
            pickup_longitude {[type]} -- [description] (default: {None})
            dropoff_latitude {[type]} -- [description] (default: {None})
            dropoff_longitude {[type]} -- [description] (default: {None})
            service_class {[type]} -- [description] (default: {None})
        """



        # Invert the demand for destination nodes
        # e.g.: from(p1:1, p2:2) and to(p1:-1, p2:-2)
        if isinstance(demand, dict):
            destination_demand = {
                id: -demand[id]
                for id in demand.keys()
            }
        else:
            destination_demand = -demand
            
        # Create origin node
        self.origin = Node.factory_node(
            Node.TYPE_ORIGIN,
            pickup_longitude,
            pickup_latitude,
            demand = demand,
            parent=self,
            network_node_id = pickup_id,
            service_duration = service_duration)


        self.destination = Node.factory_node(
            Node.TYPE_DESTINATION,
            dropoff_longitude,
            dropoff_latitude,
            demand = destination_demand,
            parent=self,
            network_node_id = dropoff_id,
            service_duration = service_duration)
        
        # Which vehicle picked up the request?
        self.serviced_by = None

        Request.node_pairs_dict[self.origin] = self.destination
        Request.node_pairs_dict[self.destination] = self.origin

        Request.od_set.add((self.origin, self.destination))
        self.id = Request.count

        Request.count+=1
        # use revealing_datetime.timestamp() to get an integer
        self.revealing_datetime = revealing_datetime
        self.demand = demand
        self.max_pickup_delay = max_pickup_delay
        self.max_total_delay = max_total_delay
        self.service_class = service_class

        if service_class is not None:
            Request.service_quality[service_class].append(self)

        self.ett = -1
        # Dictionary of OD distances per mode
        self.ett_dic_node = None
        self.embarking_t = 0
        self.disembarking_t = 0
        self.reset()
    
    @property
    def max_in_vehicle_delay(self):
        """Maximum time a user can spent inside the vehicle due to
        deviations of the shortest path (to pick up other users).
        
        Returns:
            int -- Max delay in seconds
        """

        return self.max_total_delay - self.max_pickup_delay

    def reset(self):
        self.fare = defaultdict(float)
        self.vehicle_scheduled_id = None
        self.arrival_t = -1
        self.total_travel_time = -1
        self.origin.reset()
        self.destination.reset()

    def print_status(self):
        print(self.id, "---",
              self.vehicle_scheduled_id,
              self.origin.id,
              Node.get_formatted_time_h(self.arrival_t),
              self.destination.id,
              Node.get_formatted_time_h(
                  self.arrival_t + self.total_travel_time),
              self.total_travel_time,
              self.detour_ratio)

    # Remove demands = 0
    def get_demand_short(self):
        return {id: int(self.demand[id]) for id in self.demand.keys() if int(self.demand[id]) != 0}

    def __str__(self):
        return '{sclass}[{id:03}]'.format(
            sclass = (self.service_class if self.service_class else "R"),
            id = self.id
        ) 

    def get_info(self, min_dist=None):
        
        return ("{id}({demand}) <{revealing_datetime}> ##"
        "{origin_id} -> {destination_id} "
        " - SL: ({pickup_delay:>3}/{pk_delay}, {total_delay:>3}/{dl_delay})"
        " - Pk.: {arrival}"
        " - Dp.: {departure}"
        " - Serviced by: {serviced_by}").format(
            id = self.__str__(),
            revealing_datetime = self.revealing_datetime.strftime('%H:%M:%S'),
            origin_id = self.origin,
            demand = self. demand,
            destination_id = self.destination,
            dl_delay = (self.max_total_delay if self.max_total_delay != None else "-"),
            pk_delay = (self.max_pickup_delay if self.max_pickup_delay != None else "-"),
            arrival = (
                self.origin.arrival.strftime('%H:%M:%S')
                if self.origin.arrival else '--:--:--'
            ),
            departure = (
                self.destination.arrival.strftime('%H:%M:%S')
                if self.destination.arrival else '--:--:--'
            ),
            serviced_by = (
                self.serviced_by if self.serviced_by
                else '-'
            ),
            total_delay = (
                int(
                    (self.destination.arrival
                    - (self.revealing_datetime + timedelta(seconds=min_dist))
                    ).total_seconds()
                )
                if self.serviced_by and min_dist else '-'
            ),
            pickup_delay = (
                int(
                    (self.origin.arrival - self.revealing_datetime)
                    .total_seconds()
                )
                if self.serviced_by else '-'
            )
        )
    
    @staticmethod
    def df_to_request_list(df, service_quality_dict):
        
        requests = []

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

        return requests

    @staticmethod
    def get_request_list(file_path, service_quality_dict):
        
        df = pd.read_csv(
            file_path,
            parse_dates=True,
            index_col="pickup_datetime"
        )

        requests = []

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

        return requests

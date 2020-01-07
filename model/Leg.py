import datetime
from model.Node import Node
import json
import logging
logger = logging.getLogger("main.opt_method.response.route.leg")

class Leg:
    def __init__(self, from_node, to_node, travel_t):
        self.from_node = from_node
        self.to_node = to_node
        self.occupation_log_c = dict()
        self.origin = from_node.id
        self.destination = to_node.id
        self.departure = from_node.arrival_t
        self.arrival = to_node.arrival_t
        self.travel_t = travel_t
        # Define the clock time window between origin and destination
        self.clock_t = self.arrival - self.departure
        # Time the vehicle should have spent, starting from the pickup moment
        self.invehicle_t = self.travel_t + self.from_node.service_t
        # Time spent beyond embarking time and transportation time
        self.idle_t = self.clock_t - self.invehicle_t
        self.load_origin_dic = from_node.load
        self.load_destination_dic = to_node.load
        self.proportional_t = -1
        logger.debug("LEG: %s", self.__str__())
        
            
    def __str__(self):
        resp = ""
        resp += self.origin + ","
        resp += self.destination + ","
        resp += Node.get_formatted_time_h(self.departure) + ","
        resp += Node.get_formatted_time_h(self.arrival) + ","
        resp += str(Node.get_formatted_duration_h(self.travel_t)) + ","
        resp += str(Node.get_formatted_duration_h(self.clock_t)) + ","
        resp += str(Node.get_formatted_duration_h(self.from_node.service_t)) + ","
        resp += str(Node.get_formatted_duration_h(self.to_node.service_t)) + ","
        resp += str(Node.get_formatted_duration_h(self.idle_t)) + ","
        resp += str(self.proportional_t) + ","
        # resp += str(self.occupation_log_c) + ","
        #resp += self.get_load_origin_str()
        return resp

    @classmethod
    def get_labels_line(self):
        resp = ""
        resp += "ORIGIN,"
        resp += "DESTINATION,"
        resp += "DEPARTURE,"
        resp += "ARRIVAL,"
        resp += "TRAVEL TIME,"
        resp += "CLOCK TIME,"
        resp += "INVEHICLE,"
        resp += "IDLE TIME,"
        resp += "PROPORTIONAL,"
        resp += "LOAD"
        return resp

    def __repr__(self):
        resp = ""
        resp += self.origin + ","
        resp += self.destination + ","
        resp += Node.get_formatted_time_h(self.departure) + ","
        resp += Node.get_formatted_time_h(self.arrival) + ","
        resp += str(self.travel_t) + ","
        resp += str(self.clock_t) + ","
        resp += str(self.invehicle_t) + ","
        resp += str(self.idle_t) + ","
        resp += str(self.proportional_t) + ","
        resp += str(self.occupation_log_c)
        return resp

    def get_time_profile(self):
        return ("            SERVICE: {0} \n             TRAVEL: {1}\n               IDLE: {2}\n").format(
            Node.get_formatted_duration_h(self.from_node.service_t),
            Node.get_formatted_duration_h(self.travel_t),
            Node.get_formatted_duration_h(self.idle_t))

    # Get array of points connecting the origin and destination point of a leg
    def get_directions_geojson(self):
        
        origin_lat = self.from_node.coord.y
        origin_lng = self.from_node.coord.x
        destination_lat = self.to_node.coord.y
        destination_lng = self.to_node.coord.x
        directions = "driving"
        geometries = "geojson"
        api_key = 'pk.eyJ1IjoiYnJlbm9iZWlyaWdvIiwiYSI6ImNpeHJiMDNidTAwMm0zNHFpcXVzd2UycHgifQ.tWIDAiRhjSzp1Bd40rxaHw'
        url = 'https://api.mapbox.com/directions/v5/mapbox/{0}/{1},{2};{3},{4}?geometries={5}&access_token={6}'.format(directions,
        origin_lng, origin_lat,
        destination_lng, destination_lat,
        geometries,
        api_key)
        print("READING URL:", url)
        response = read_url(url, 100, 60)
        json_obj = json.loads(response.decode('utf-8'))
        # Single out array of points forming the route
        geometry = json_obj["routes"][0]["geometry"]["coordinates"]
        return geometry

    def get_json(self):
        
        js = '{{ "from": {0},\
         "to": {1},\
         "leg_id":"{7}",\
         "geojson_geometry": {8},\
         "time_composition": {{ "service_t": "{2}", \
         "travel_t": "{3}", \
         "idle_t": "{4}", \
         "total_t": "{5}", \
         "proportional_t":{6} }}}}'.format(
            self.from_node.get_json_leg_node(),
            self.to_node.get_json_leg_node(),
            Node.get_formatted_duration_h(self.from_node.service_t),
            Node.get_formatted_duration_h(self.travel_t),
            Node.get_formatted_duration_h(self.idle_t),
            Node.get_formatted_duration_h(self.clock_t),
            self.proportional_t,
            "R_" + self.from_node.id + "_" + self.to_node.id,
            self.get_directions_geojson()
        )
        return js

    def get_load_origin_str(self):
        s = ""
        for k in self.load_origin_dic.keys():
            s += k + ":" + \
                str(self.load_origin_dic[k]) + "(" + \
                str(round(self.occupation_log_c[k], 3)) + ") | "
        return s
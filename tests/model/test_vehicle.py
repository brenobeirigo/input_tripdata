import config
import network_gen as gen
from model.Vehicle import Vehicle
from model.Node import *
from datetime import datetime

G = gen.get_network_from(config.tripdata["region"],
                            config.data_path,
                            config.graph_name,
                            config.graph_file_name)


#x.plot_graph(G)



vehicle_list = []
capacity = 4
start_datetime = datetime.strptime("2011-02-02 00:00:00", '%Y-%m-%d %H:%M:%S')
for i in range(0,10):
    # Getting random node info
    id, lon, lat = gen.get_random_node(G)
    
    # Creating vehicle origin node
    o = Node.factory_node(Node.TYPE_ORIGIN, lon, lat, network_node_id=id)
    
    print(o)
    v = Vehicle(i,o,{'A':4},start_datetime)
    vehicle_list.append(v)

for v in vehicle_list:
    print('Vehicle', str(v))

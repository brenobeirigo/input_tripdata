import osmnx as ox
import networkx as nx
import os
import pandas as pd
import numpy as np
import config


def node_access(G, node, degree=1, direction="backward"):
    """
    Return the set of nodes which lead to "node" (direction = backaward)
    or the set o nodes which can be accessed from "node" (direction = forward)

    Parameters:
        G         - Networkx muldigraph
        node      - Node whose accessibility will be tested
        degree    - Number of hops (backwards or forwards)
        direction - Test forwards or backwards

    Return:
        set of backward/forward nodes
    """

    # Access can be forward or backwards
    func = (G.successors if direction == "forward" else G.predecessors)

    access_set = set()
    access = [node]
    access_set = access_set.union(access)

    for i in range(0, degree):

        # Predecessors i degrees away
        access_i = set()

        for j in access:
            access_i = access_i.union(set(func(j)))

        access = access_i
        access_set = access_set.union(access)

    return access_set


def is_reachable(G, node, degree):

    pre = list(G.predecessors(node))
    suc = list(G.successors(node))
    neighbors = set(pre + suc)

    if node in neighbors:
        # if the node appears in its list of neighbors, it self-loops. this is
        # always an endpoint.
        return False

    if len(node_access(G, node, degree, direction="backward")) < degree:
        return False

    if len(node_access(G, node, 10, direction="forward")) < degree:
        return False

    return True

    # Save the equivalence between nodes


dic_old_new = dict()

# Global id counter
i = -1

# Relabel


def mapping(x):
    global i
    i = i+1
    dic_old_new[x] = i
    return i


def load_network(filename, folder=None):

    path = "{}/{}".format(folder, filename)
    print("Loading ", path)

    # if file does not exist write header
    if not os.path.isfile("{}/{}".format(folder, filename)):
        print("Network is not in '{}'".format(path))
        return None

    # Try to load graph
    return ox.load_graphml(filename=filename, folder=folder)


def download_network(region, network_type, root=None):

    # Download graph
    G = ox.graph_from_place(region, network_type=network_type)

    return G


def get_list_coord(G, o, d):
    """Get the list of intermediate coordinates between
    nodes o and d (inclusive).

    Arguments:
        G {networkx} -- Graph
        o {int} -- origin id
        d {int} -- destination id

    Returns:
        list -- E.g.: [(x1, y1), (x2, y2)]
    """

    edge_data = G.get_edge_data(o, d)[0]
    try:
        return ox.LineString(edge_data['geometry']).coords
    except:
        return [(G.node[o]['x'], G.node[o]['y']), (G.node[d]['x'], G.node[d]['y'])]


def get_point(G, p, **kwargs):

    point = {"type": "Feature", "properties": kwargs, "geometry": {
        "type": "Point", "coordinates":  [G.node[p]["x"], G.node[p]["y"]]}}

    return point


def get_linestring(G, o, d, **kwargs):
    """Return linestring corresponding of list of node ids
    in graph G.

    Arguments:
        G {networkx} -- Graph
        list_ids {list} -- List of node ids

    Returns:
        linestring -- Coordinates representing id list
    """

    linestring = []

    list_ids = get_sp(G, o, d)

    for i in range(0, len(list_ids) - 1):
        linestring.extend(get_list_coord(G,
                                         list_ids[i],
                                         list_ids[i+1]))
        linestring = linestring[:-1]

    # Add last node (excluded in for loop)
    linestring.append((G.node[list_ids[-1]]['x'], G.node[list_ids[-1]]['y']))

    # List of points (x y) connection from_id and to_id
    coords = [[u, v] for u, v in linestring]

    geojson = {"type": "Feature",
               "properties": kwargs,
               "geometry": {"type": "LineString",
                            "coordinates": coords}}

    return geojson


def get_sp(G, o, d):
    return nx.shortest_path(G, source=o, target=d)


def get_graph():

    # Street network
    H = None

    # Try loading region
    try:
        H = load_network(config.tripdata["region"], folder=config.root_path)
        # Print G description
        print("#NODES: {} ({} -> {}) -- #EDGES: {}".format(len(H.nodes()),
                                                           min(H.nodes()), max(H.nodes()), len(H.edges())))

    except Exception as e:
        print("Graph does not exist!")
        print(e)
    finally:
        return H


def get_network_from(region, root_path, graph_name, graph_filename):
    """Download network from region. If exists, load.
    
    Arguments:
        region {string} -- Location. E.g., "Manhattan Island, New York City, New York, USA"
        root_path {string} -- Path where graph is going to saved
        graph_name {string} -- Name to be stored in graph structure
        graph_filename {string} -- File name .graphml to be saved in root_path
    
    Returns:
        [networkx] -- Graph loaeded or downloaded
    """


    # Street network
    G = load_network(graph_filename, folder=root_path)

    if G is None:
    # Try loading region
        try:
            G = download_network(region, "drive")

            # Create and store graph name
            G.graph["name"] = graph_name

            print("#ORIGINAL -  NODES: {} ({} -> {}) -- #EDGES: {}".format(len(G.nodes()),
                                                                            min(G.nodes()),
                                                                            max(G.nodes()),
                                                                            len(G.edges())))

            G = ox.remove_isolated_nodes(G)

            # Set of nodes with low connectivity (end points)
            # Must be eliminated to avoid stuch vehicles (enter but cannot leave)
            not_reachable = set()

            for node in G.nodes():
                # Node must be accessible by at least 10 nodes forward and backward
                # e.g.: 1--2--3--4--5 -- node --6--7--8--9--10
                if not is_reachable(G, node, 10):
                    not_reachable.add(node)

                for target in G.neighbors(node):
                    edge_data = G.get_edge_data(node, target)
                    keys = len(edge_data.keys())
                    try:
                        for i in range(1, keys):
                            del edge_data[i]
                    except:
                        pass

            for node in not_reachable:
                G.remove_node(node)

            # Relabel nodes
            G = nx.relabel_nodes(G, mapping)

            # Save
            ox.save_graphml(G, filename=graph_filename, folder=root_path)
        
        except Exception as e:
            print("Error loading graph:" + e)

    print("# NETWORK -  NODES: {} ({} -> {}) -- #EDGES: {}".format(
        len(G.nodes()),
        min(G.nodes()),
        max(G.nodes()),
        len(G.edges())))
    
    return G


def save_graph_pic(G):
    fig, ax = ox.plot_graph(G,
                            fig_height=15,
                            node_size=0.5,
                            edge_linewidth=0.3,
                            save=True,
                            show=False,
                            file_format='svg',
                            filename='ny')


def get_distance_dic(root_path, G):

    distance_dic_m = None

    try:
        print("Reading '{}'...".format(root_path))
        distance_dic_m = np.load(root_path).item()

    except:
        print("Calculating shortest paths...")
        all_dists_gen = nx.all_pairs_dijkstra_path_length(G, weight="length")

        # Save with pickle (meters)
        distance_dic_m = dict(all_dists_gen)
        np.save(root_path, distance_dic_m)

    print("\n#Nodes in distance dictionary:", len(distance_dic_m.values()))

    return distance_dic_m


def get_distance_matrix(G, distance_dic_m):
    """Return distance matrix (n x n). Value is 'None' when path does not exist
    
    Arguments:
        G {networkx} -- Graph to loop nodes
        distance_dic_m {dic} -- previosly calculated distance dictionary
    
    Returns:
        [list[list[float]]] -- Distance matrix
    """
    # TODO simplify - test:  nx.shortest_path_length(G, source=o, target=d, weight="length")

    # Creating distance matrix
    dist_matrix = []
    for from_node in G.nodes():
        to_distance_list = []
        for to_node in G.nodes():

            try:
                dist = distance_dic_m[from_node][to_node]
                to_distance_list.append(dist)
            except:
                to_distance_list.append(None)

        dist_matrix.append(to_distance_list)

    return dist_matrix


def get_dt_distance_matrix(path, dist_matrix):

    dt = None

    try:
        # Load tripdata
        # https://pandas.pydata.org/pandas-docs/stable/generated/pandas.read_csv.html
        dt = pd.read_csv(path, header=None)

    except Exception as e:
        print(e)
        dt = pd.DataFrame(dist_matrix)
        dt.to_csv(path, index=False,
                  header=False, float_format="%.6f", na_rep="INF")

    return dt

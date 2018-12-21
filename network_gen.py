import osmnx as ox
import networkx as nx
import os
import pandas as pd
import numpy as np


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


def load_network(region, folder=None):

    # Create and store graph name
    file_name = region.lower().replace(" ", "-").replace(",", "")+".graphml"

    # Try to load graph
    return ox.load_graphml(filename=file_name, folder=folder)


def download_network(region, network_type, root=None):

    # Download graph
    G = ox.graph_from_place(region, network_type=network_type)

    # Create and store graph name
    G.graph["name"] = region.lower().replace(" ", "-").replace(",", "")

    return G


def get_network_from(root_path, region):

    # Street network
    G = None

    # Try loading region
    try:
        G = load_network(region, folder=root_path)

    # Download graph
    except:

        G = download_network(region, "drive")
        print("#DOWLOADED -  NODES: {} ({} -> {}) -- #EDGES: {}".format(len(G.nodes()),
                                                                        min(G.nodes()), max(G.nodes()), len(G.edges())))

        G = ox.remove_isolated_nodes(G)

        # Set of nodes with low connectivity (end points)
        # Must be eliminated to avoid stuch vehicles (enter but cannot leave)
        not_reachable = set()

        for node in G.nodes():
            # Node must be accessible 10 by at least 10 nodes forward and backward
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

        print("#  CLEANED NON-REACHABLE -  NODES: {} ({} -> {}) -- #EDGES: {}".format(
            len(G.nodes()), min(G.nodes()), max(G.nodes()), len(G.edges())))

        # Relabel nodes
        G = nx.relabel_nodes(G, mapping)

        # Network
        file_name = '{0}.graphml'.format(G.graph["name"])

        # Save
        ox.save_graphml(G, filename=file_name, folder=root_path)
    return G


def save_graph(G):
    fig, ax = ox.plot_graph(G,
                            fig_height=15,
                            node_size=0.5,
                            edge_linewidth=0.3,
                            save=True,
                            show = False,
                            file_format='svg',
                            filename='ny')


def get_distance_dic(G, root_path):

    root_path = root_path + "/dist"
    if not os.path.exists(root_path):
        os.makedirs(root_path)

    # Distance dictionary (meters)
    file_name_dis_m = "distance_dic_meters_"+G.graph["name"]
    root_file_name_dis_m = "{}/{}.npy".format(root_path, file_name_dis_m)

    distance_dic_m = None

    try:
        print("Reading '{}'...".format(root_file_name_dis_m))
        distance_dic_m = np.load(root_file_name_dis_m).item()

    except:
        print("Calculating shortest paths...")
        all_dists_gen = nx.all_pairs_dijkstra_path_length(G, weight="length")

        # Save with pickle (meters)
        distance_dic_m = dict(all_dists_gen)
        np.save(root_file_name_dis_m, distance_dic_m)

    print("NODES (m):", len(distance_dic_m.values()))

    return distance_dic_m


def get_distance_matrix(G, distance_dic_m):

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


def get_dt_distance_matrix(G, dist_matrix, root_path):

    file_name_dist_matrix = "{}/dist/distance_matrix_m_{}.csv".format(
        root_path, G.graph["name"])

    dt = None

    try:
        # Load tripdata
        # https://pandas.pydata.org/pandas-docs/stable/generated/pandas.read_csv.html
        dt = pd.read_csv(file_name_dist_matrix, header=None)

    except Exception as e:
        print(e)
        dt = pd.DataFrame(dist_matrix)
        dt.to_csv(file_name_dist_matrix, index=False,
                  header=False, float_format="%.6f", na_rep="INF")

    return dt

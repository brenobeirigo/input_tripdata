import osmnx as ox
import networkx as nx
import os
import pandas as pd
import numpy as np
import bisect
import milp.ilp_reachability as ilp
from collections import defaultdict
import functools
import random
random.seed(1)


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
    func = G.successors if direction == "forward" else G.predecessors

    access_set = set()
    access = [node]
    access_set = access_set.union(access)

    for _ in range(0, degree):

        # Predecessors i degrees away
        access_i = set()

        for j in access:
            access_i = access_i.union(set(func(j)))

        access = access_i
        access_set = access_set.union(access)

    return access_set


def is_reachable(G, node, degree):
    """Check if node can be accessed across a chain
    of "degree" nodes (backwards and frontward).

    This guarantees the node is not isolated since it is reachable and
    can reach others.

    Arguments:
        G {networkx} -- Graph that the node belongs too
        node {int} -- Id of node to test reachability
        degree {int} -- Minimum length of path

    Returns:
        boolean -- True, if node can be reached and reach others
    """
    pre = list(G.predecessors(node))
    suc = list(G.successors(node))
    neighbors = set(pre + suc)

    if node in neighbors:
        # if the node appears in its list of neighbors, it self-loops.
        # this is always an endpoint.
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
    i = i + 1
    dic_old_new[x] = i
    return i


def load_network(filename, folder=None):
    """Load and return graph network.

    Arguments:
        filename {string} -- Name of network

    Keyword Arguments:
        folder {string} -- Target folder (default: {None})

    Returns:
        networkx or None -- The loaded network or None if not found
    """

    path = "{}/{}".format(folder, filename)
    print("Loading ", path)

    # if file does not exist write header
    if not os.path.isfile("{}/{}".format(folder, filename)):
        print("Network is not in '{}'".format(path))
        return None

    # Try to load graph
    return ox.load_graphml(filename=filename, folder=folder)


def download_network(region, network_type):
    """Download network from OSM representing the region.

    Arguments:
        region {string} -- Location.
            E.g., "Manhattan Island, New York City, New York, USA"
        network_type {string} -- Options: drive, drive_service, walk,
            bike, all, all_private

    Returns:
        networkx -- downloaded networkx
    """

    # Download graph
    G = ox.graph_from_place(region, network_type=network_type)

    return G


def get_reachability_dic(
    data_path, distance_dic, step=30, total_range=600, speed_km_h=30
):
    """Which nodes are reachable from one another in "step" steps?
    E.g.:
    Given the following distance dictionary:

    FROM    TO   DIST(s)
    2       1     35
    3       1     60
    4       1     7
    5       1     20

    If step = 30, the reachability set for 1 is:
    reachable[1][30] = set([4, 5]).

    In other words, node 1 can be reached from nodes 4 and 5 in
    less than 30 steps.

    Hence, for a given OD pair (o, d) and step = s, if o in 
    reachable[d][s], then d can be reached from o in t steps.

    Arguments:
        distance_dic {dict{float}} -- Distance dictionary
            (dic[o][d] = dist(o,d))
        data_path {str} -- Where to save reachability dictionary

    Keyword Arguments:

        step {int} -- The minimum reachability distance that multiplies
            until it reaches the total range.
        total_range{int} -- Total range used to define concentric
            reachability, step from step. Considered a multiple of step.
        speed_kh_h {int} -- in km/h to convert distance
            (default: {30} km_h). If different of None, 'step' and
            'total_range' are considered in seconds.

    Returns:
        [dict] -- Reachability structure.
                  E.g.: reachable[d][step] = set([o_1, o_2, o_3, o_n])
                  IMPORTANT: for the sake of memory optimization, nodes
                  from step 'x' are NOT included in step 'x+1'.
                  Use 'get_can_reach_set' to derive the overall 
                  reachability, across the full range.
    """

    reachability_dict = None
    try:
        reachability_dict = np.load(data_path).item()
        print("Reading reachability dictionary '{}'...".format(data_path))

    except:

        reachability_dict = defaultdict(lambda: defaultdict(set))

        # E.g., [30, 60, 90, ..., 600]
        steps_in_range_list = [
            i for i in range(step, total_range + step, step)
        ]
        print(
            ("Calculating reachability...\n" + "Steps:{}").format(
                steps_in_range_list
            )
        )

        for o in distance_dic.keys():
            for d in distance_dic[o].keys():

                # Dictionary contains only valid distances
                dist_m = distance_dic[o][d]

                # So far, we are using distance in meters
                dist = dist_m

                # If speed is provided, convert distance to seconds
                # Steps are assumed to be in seconds too
                if speed_km_h:
                    dist_s = int(3.6 * dist_m / speed_km_h + 0.5)
                    dist = dist_s

                # Find the index of which max_duration box dist_s is in
                step_id = bisect.bisect_left(steps_in_range_list, dist)
                if step_id < len(steps_in_range_list):
                    reachability_dict[d][steps_in_range_list[step_id]].add(o)
                    # print("o: {} -> d: {} - dist_km: {} - dist_s: {} - index: {} - reachable in(s): {}".format(o,d, dist_m, dist_s, step, max_travel_time_list[step]))
        # print(reachability_dict)
        np.save(data_path, dict(reachability_dict))

    return reachability_dict


def get_can_reach_set(n, reach_dic, max_trip_duration=150):
    """Return the set of all nodes whose trip to node n takes
    less than "max_trip_duration" seconds.

    Arguments:
        n {int} -- target node id
        reach_dic {dict[int][dict[int][set]]} -- Stores the node ids
            whose distance to n is whitin max. trip duration (e.g., 30,
            60, etc.)

    Keyword Arguments:
        max_trip_duration {int} -- Max. trip duration in seconds a node
            can be distant from n (default: {150})

    Returns:    
        Set -- Set of nodes that can reach n in less than
            max_trip_duration seconds.
    """

    can_reach_target = set()
    for t in reach_dic[n].keys():
        if t <= max_trip_duration:
            can_reach_target.update(reach_dic[n][t])
    return can_reach_target


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
        return ox.LineString(edge_data["geometry"]).coords
    except:
        return [
            (G.node[o]["x"], G.node[o]["y"]),
            (G.node[d]["x"], G.node[d]["y"]),
        ]


def get_point(G, p, **kwargs):
    """Get geojson point from node id

    Arguments:
        G {networkx} -- Base graph
        p {int} -- Node id

    Returns:
        dict -- Point geojson
    """

    point = {
        "type": "Feature",
        "properties": kwargs,
        "geometry": {
            "type": "Point",
            "coordinates": [G.node[p]["x"], G.node[p]["y"]],
        },
    }

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
        linestring.extend(get_list_coord(G, list_ids[i], list_ids[i + 1]))
        linestring = linestring[:-1]

    # Add last node (excluded in for loop)
    linestring.append((G.node[list_ids[-1]]["x"], G.node[list_ids[-1]]["y"]))

    # List of points (x y) connection from_id and to_id
    coords = [[u, v] for u, v in linestring]

    geojson = {
        "type": "Feature",
        "properties": kwargs,
        "geometry": {"type": "LineString", "coordinates": coords},
    }

    return geojson


def get_sp_coords(G, o, d):
    """Return coordinates of the shortest path.
    E.g.: [[x, y], [z,w]]

    Arguments:
        G {networkx} -- Graph
        list_ids {list} -- List of node ids

    Returns:
        linestring -- Coordinates representing id list
    """

    linestring = []

    list_ids = get_sp(G, o, d)

    for i in range(0, len(list_ids) - 1):
        linestring.extend(get_list_coord(G, list_ids[i], list_ids[i + 1]))
        linestring = linestring[:-1]

    # Add last node coordinate (excluded in for loop)
    linestring.append((G.node[list_ids[-1]]["x"], G.node[list_ids[-1]]["y"]))

    # List of points (x y) connection from_id and to_id
    coords = [[u, v] for u, v in linestring]

    return coords


def get_sp_linestring_durations(G, o, d, speed):
    """Return coordinates of the shortest path.
    E.g.: [[x, y], [z,w]]

    Arguments:
        G {networkx} -- Graph
        list_ids {list} -- List of node ids

    Returns:
        linestring -- Coordinates representing id list
    """

    linestring = []

    list_ids = get_sp(G, o, d)

    for i in range(0, len(list_ids) - 1):
        linestring.extend(get_list_coord(G, list_ids[i], list_ids[i + 1]))
        linestring = linestring[:-1]

    # Add last node (excluded in for loop)
    linestring.append((G.node[list_ids[-1]]["x"], G.node[list_ids[-1]]["y"]))

    # List of points (x y) connection from_id and to_id
    coords = [[u, v] for u, v in linestring]

    return coords


def get_sp(G, o, d):
    """Return shortest path between node ids o and d

    Arguments:
        G {networkx} -- [description]
        o {int} -- Origin node id
        d {int} -- Destination node id

    Returns:
        list -- List of nodes between o and d (included)
    """
    return nx.shortest_path(G, source=o, target=d)


def get_network_from(region, data_path, graph_name, graph_filename):
    """Download network from region. If exists (check graph_filename),
    try loading.

    Arguments:
        region {string} -- Location. E.g., "Manhattan Island,
            New York City, New York, USA"
        data_path {string} -- Path where graph is going to saved
        graph_name {string} -- Name to be stored in graph structure
        graph_filename {string} -- File name .graphml to be saved
            in data_path

    Returns:
        [networkx] -- Graph loaeded or downloaded
    """
    # Street network
    G = load_network(graph_filename, folder=data_path)

    if G is None:
        # Try to download
        try:
            G = download_network(region, "drive")

            # Create and store graph name
            G.graph["name"] = graph_name

            print(
                "#ORIGINAL -  NODES: {} ({} -> {}) -- #EDGES: {}".format(
                    len(G.nodes()),
                    min(G.nodes()),
                    max(G.nodes()),
                    len(G.edges()),
                )
            )

            G = ox.remove_isolated_nodes(G)

            # Set of nodes with low connectivity (end points)
            # Must be eliminated to avoid stuch vehicles
            # (enter but cannot leave)
            not_reachable = set()

            for node in G.nodes():
                # Node must be accessible by at least 10 nodes
                # forward and backward
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

            # Only the strongest connected component is kept
            disconnected = G.nodes() - get_largest_connected_component(G)
            G.remove_nodes_from(disconnected)

            # Relabel nodes
            G = nx.relabel_nodes(G, mapping)

            # Save
            ox.save_graphml(G, filename=graph_filename, folder=data_path)

        except Exception as e:
            print("Error loading graph:", e)

    print(
        "# NETWORK -  NODES: {} ({} -> {}) -- #EDGES: {}".format(
            len(G.nodes()), min(G.nodes()), max(G.nodes()), len(G.edges())
        )
    )

    return G


def save_graph_pic(G, path):
    """Save a picture (svg) of graph G.

    Arguments:
        G {networkx} -- Working graph
    """

    fig, ax = ox.plot_graph(
        G,
        fig_height=15,
        node_size=0.5,
        edge_linewidth=0.3,
        save=True,
        show=False,
        file_format="svg",
        filename="{}/{}".format(path, G.graph["name"]),
    )


@functools.lru_cache(maxsize=1)
def get_number_of_nodes(G):
    return nx.number_of_nodes(G)


def get_random_node(G):
    random_node = random.randint(0, nx.number_of_nodes(G) - 1)
    return random_node, G.node[random_node]["x"], G.node[random_node]["y"]


def get_coords_node(n, G):
    return G.node[n]["x"], G.node[n]["y"]


@functools.lru_cache(maxsize=1048576)
def get_distance(G, o, d):
    return nx.dijkstra_path_length(G, o, d, weight="length")


def get_distance_dic(data_path, G):
    """Get distance dictionary (Dijkstra all to all using path length).
    E.g.: [o][d]->distance

    Arguments:
        data_path {string} -- Try to load path before generating
        G {networkx} -- Street network

    Returns:
        dict -- Distance dictionary (all to all)
    """
    distance_dic_m = None
    try:
        print(
            "Trying to read distance data from file:\n'{}'.".format(data_path)
        )
        distance_dic_m = np.load(data_path).item()

    except:
        print("Reading failed! Calculating shortest paths...")
        all_dists_gen = nx.all_pairs_dijkstra_path_length(G, weight="length")

        # Save with pickle (meters)
        distance_dic_m = dict(all_dists_gen)
        np.save(data_path, distance_dic_m)

    print(
        "Distance data load successfully. #Nodes:",
        len(distance_dic_m.values()),
    )

    return distance_dic_m


def get_largest_connected_component(G):
    """Return the largest strongly connected component of graph G.

    Arguments:
        G {networkx} -- Graph

    Returns:
        set -- Set of nodes pertaining to the component
    """

    largest_cc = max(nx.strongly_connected_components(G), key=len)
    s_connected_component = [
        len(c)
        for c in sorted(
            nx.strongly_connected_components(G), key=len, reverse=True
        )
    ]
    print("Strongly connected:", s_connected_component)
    return set(largest_cc)


def get_distance_matrix(G, distance_dic_m):
    """Return distance matrix (n x n). Value is 'None' when path does
    not exist

    Arguments:
        G {networkx} -- Graph to loop nodes
        distance_dic_m {dic} -- previosly calculated distance dictionary

    Returns:
        [list[list[float]]] -- Distance matrix
    """
    # TODO simplify - test:  nx.shortest_path_length(G, source=o,
    # target=d, weight="length")

    # Creating distance matrix
    dist_matrix = []
    for from_node in G.nodes():
        to_distance_list = []
        for to_node in G.nodes():

            try:
                dist_km = distance_dic_m[from_node][to_node]
                to_distance_list.append(dist_km)
            except:
                to_distance_list.append(None)

        dist_matrix.append(to_distance_list)

    return dist_matrix


def get_dt_distance_matrix(path, dist_matrix):
    """Get dataframe from distance matrix

    Arguments:
        path {string} -- File path of distance matrix
        dist_matrix {list[list[float]]} -- Matrix of distances

    Returns:
        pandas dataframe -- Distance matrix
    """

    dt = None

    try:
        # Load tripdata
        # https://pandas.pydata.org/pandas-docs/stable/generated/pandas.read_csv.html
        dt = pd.read_csv(path, header=None)

    except Exception as e:
        print(e)
        dt = pd.DataFrame(dist_matrix)
        dt.to_csv(
            path, index=False, header=False, float_format="%.6f", na_rep="INF"
        )

    return dt


def get_region_centers(
        path_region_centers,
        reachability_dic,
        data_path=None,
        time_limit=60):
    """Find minimum number of region centers, every 'step'
    
    ILP from:
      Wallar, A., van der Zee, M., Alonso-Mora, J., & Rus, D. (2018).
      Vehicle Rebalancing for Mobility-on-Demand Systems with 
      Ride-Sharing. Iros, 4539–4546.
    
    Why using regions?
    The region centers are computed a priori and are used to aggregate
    requests together so the rate of requests for each region can be
    computed. These region centers are also used for rebalancing as
    they are the locations that vehicles are proactively sent to.
    
    Arguments:
        path_region_centers {str} -- Path to save/load dictionary of
            region centers.
        reachability_dic {dict{int:dict{int:set}} -- Stores the set
            's' of nodes that can reach 'target' node in less then 't'
            time steps.  E.g.: reachability_dic[target][max_delay] = s
    
    Keyword Arguments:
        data_path {str} -- Location where intermediate work (i.e.,
            previous max. durations from reachability dictionary), and
            model logs should be saved. (default: {None})
        time_limit {int} -- Expiration time (in seconds) of the ILP
            model execution (default: {60})
    
    Returns:
        [type] -- [description]
    """

    

    # Dictionary relating max_delay to region centers

    centers_dic = None
    if  os.path.isfile(path_region_centers):
        centers_dic = np.load(path_region_centers).item()
        print(
            "\nReading region center dictionary...\nSource: '{}'.".format(
                path_region_centers
            )
        )

    else:
        # TODO invert keys in reachability dict. First: steps!
        any_key = next(iter(reachability_dic))
        max_trip_duration_list = list(reachability_dic[any_key].keys())

        print(
            (
                "\nCalculating region center dictionary..."
                "\nMax. durations: {}"
                "\nTarget path: '{}'."
                
            ).format(
                max_trip_duration_list,
                path_region_centers
            )
        )
        # If not None, defines the location of the steps of a solution
        centers_gurobi_log = None
        centers_sub_sols = None

        if data_path is not None:
            # Create folder to save logs
            centers_gurobi_log = "{}/region_centers/gurobi_log".format(
                data_path
            )

            if not os.path.exists(centers_gurobi_log):
                os.makedirs(centers_gurobi_log)
            
            # Create folder to save intermediate work, that is, previous
            # max_delay steps.
            centers_sub_sols = "{}/region_centers/sub_sols".format(data_path)
            
            if not os.path.exists(centers_sub_sols):
                os.makedirs(centers_sub_sols)

        centers_dic = dict()
        for max_delay in sorted(max_trip_duration_list):
            
            if centers_sub_sols is not None:
                # Name of intermediate region centers file for 'max_delay'
                file_name = "{}/{}.npy".format(centers_sub_sols, max_delay)

                # Pre-calculated region center is loaded in case it exists.
                # This helps filling the complete 'centers_dic' without
                # starting the process from the beginning, in case an error
                # has occured.
                if os.path.isfile(file_name):
                    # Load max delay in centers_dic
                    centers_dic[max_delay] = np.load(file_name)
                    print(file_name, "already calculated.")
                    continue

            try:
                # Find the list of centers for max_delay
                centers = ilp.ilp_node_reachability(
                    reachability_dic,
                    max_delay=max_delay,
                    log_path=centers_gurobi_log,
                    time_limit=time_limit,
                )
            except Exception as e:
                print(e)
            else:
                centers_dic[max_delay] = centers
                print(
                    "Max. delay: {} = # Nodes: {}".format(max_delay, len(centers))
                )

                # Save intermediate steps (region centers of 'max_delay')
                if data_path:
                    np.save(file_name, centers)

                np.save(path_region_centers, centers_dic)
                
    return centers_dic

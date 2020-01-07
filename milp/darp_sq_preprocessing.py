
def get_n_requests(n, service_quality_dict, customer_segmentation_dict):
    requests = []
    user_classes = list(service_quality_dict.keys())
    df = tp.get_next_batch(
        "TESTE1",
        chunk_size=2000,
        batch_size=30,
        # tripdata_csv_path='D:/bb/sq/data/delft-south-holland-netherlands/tripdata/random_clone_tripdata_excerpt_2011-02-01_000000_2011-02-02_000000_ids.csv',
        start_timestamp='2011-02-01 00:00:00',
        end_timestamp='2011-02-01 00:01:00',
        classes=user_classes,
        freq=[customer_segmentation_dict[k] for k in user_classes]
    )

    while df is not None:
        df = tp.get_next_batch("TESTE1")

        if not df.empty:
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
                    service_duration=0)

                requests.append(r)

                if len(requests) == n:
                    return requests


def get_list_of_vehicles_in_region_centers(
        max_capacity, G, start_datetime,
        list_of_region_centers, list_of_nodes_to_reach, max_delay,
        reachability_dict, distance_dict):

    vehicle_list = []

    for node_to_reach in list_of_nodes_to_reach:
        set_centers_can_reach = set(list_of_region_centers).intersection(
            nw.get_can_reach_set(
                node_to_reach.network_node_id,
                reachability_dict,
                max_trip_duration=max_delay
            )
        )

        # Choose a center randomly to access the origin
        random_center_id = random.choice(list(set_centers_can_reach))
        lon, lat = nw.get_coords_node(random_center_id, G)

        print("\nVehicles in ", random_center_id, ":")
        # Create vehicles of different capacities in this center
        # for capacity in range(node_to_reach.parent.demand, max_capacity + 1):
        for capacity in range(max_capacity, max_capacity + 1):

            # Creating vehicle origin node
            depot_node = Node.factory_node(
                Node.TYPE_DEPOT,
                lon, lat, network_node_id=random_center_id
            )

            v = Vehicle(depot_node, capacity, start_datetime)
            print("Vehicle", v)

            dist_m = distance_dict[depot_node.network_node_id][node_to_reach.network_node_id]
            dist_seconds = int(3.6 * dist_m / 30 + 0.5)
            print("  -", v.pid, dist_seconds)

            vehicle_list.append(v)

        print("Can reach node: {}({})".format(
            node_to_reach.pid, node_to_reach.parent.demand))
    return vehicle_list


def get_n_vehicles(n, capacity, G, start_datetime):
    vehicle_list = []

    for _ in range(0, n):

        # Getting random node info
        id, lon, lat = nw.get_random_node(G)

        # Creating vehicle origin node
        o = Node.factory_node(Node.TYPE_DEPOT, lon, lat, network_node_id=id)

        v = Vehicle(o, capacity, start_datetime)

        vehicle_list.append(v)

    return vehicle_list


def get_viable_network(depot_list, origin_list, destination_list,
                       pair_dic, distance_dic, speed=None):

    def dist_sec(o, d):
        dist_meters = distance_dic[o.network_node_id][d.network_node_id]
        if speed != None:
            dist_seconds = int(3.6 * dist_meters / speed + 0.5)
            return dist_seconds
        else:
            return dist_meters

    # Graph NxN - Remove self connections and arcs arriving in end depot
    nodes_network = defaultdict(dict)

    # Depots only connect to origins
    for depot in depot_list:
        for o in origin_list:
            # But only if vehicle can service demand entirely
            # if o.parent.demand <= depot.parent.capacity:
            nodes_network[depot][o] = dist_sec(depot, o)

    # Origins connect to other origins
    for o1 in origin_list:
        for o2 in origin_list:

            # No loop
            if o1 != o2:
                nodes_network[o1][o2] = dist_sec(o1, o2)

    # Origins connect to destinations
    for o in origin_list:
        for d in destination_list:
            nodes_network[o][d] = dist_sec(o, d)

    # Destination connect to origins
    for d in destination_list:
        for o in origin_list:

            # But not if origin and destination belong to same request
            if d != pair_dic[o]:
                nodes_network[d][o] = dist_sec(d, o)

    # Destinations connect to destinations
    for d1 in destination_list:
        for d2 in destination_list:
            # No loop
            if d1 != d2:
                nodes_network[d1][d2] = dist_sec(d1, d2)

    return nodes_network


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
            v.available_at + timedelta(hours=24)
        )

    return node_timewindow_dict


def get_valid_rides(
        vehicles, node_timewindow_dict,
        pairs_dict, distance_dict):

    #### VARIABLES ####################################################
    # Decision variable - viable vehicle paths
    # A vehicle can only attend requests that it can fully handle,
    # e.g.:
    # k[A,C] - i[A,C] -- OK! (k,i,j)
    #   k[A] - i[A,C] -- NO!
    valid_rides = set()

    # Create valid rides

    for k in vehicles:
        for i, to_dict in distance_dict.items():

            # A vehicle can only start from its own depot
            if isinstance(i, NodeDepot) and k.pos is not i:
                continue

            for j, dist in to_dict.items():

                earliest_i = node_timewindow_dict[i][0]

                latest_j = node_timewindow_dict[j][1]

                if isinstance(i, NodePK):

                    dl = pairs_dict[i]

                    if j != dl:

                        # Can't access n3 from n2
                        if dl not in distance_dict[j].keys():
                            continue

                        max_ride = distance_dict[i][dl] + \
                            i.parent.max_total_delay

                        t_i_j = dist

                        t_j_dl = distance_dict[j][dl]

                        if t_i_j + t_j_dl > max_ride:
                            continue

                    if earliest_i > latest_j:
                        continue

                # k, i, j is a valid arc
                valid_rides.add((k, i, j))

    return valid_rides


def get_valid_visits(valid_rides):
    valid_visit = set()
    for v, i, j in valid_rides:
        valid_visit.add((v, i))
        valid_visit.add((v, j))
    return valid_visit

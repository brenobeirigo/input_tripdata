from collections import defaultdict

from model.Node import NodeDepot, NodePK
from model.Request import Request


def get_valid_rides_set(
        vehicles,
        pairs_dict,
        distance_dict):
    valid_rides = set()

    for k in vehicles:
        for i, to_dict in distance_dict.items():

            # A vehicle can only start from its own depot
            if isinstance(i, NodeDepot) and k.pos is not i:
                continue

            # A vehicle shall not enter an origin node with a demand
            # higher than its own capacity
            if (isinstance(i.parent, Request)
                    and k.capacity < i.parent.demand):
                continue

            for j, dist_i_j in to_dict.items():

                # No vehicle can visit depot
                if isinstance(j, NodeDepot):
                    continue

                # A vehicle shall not enter a destination node with a
                # demand higher than its own capacity
                if (isinstance(j.parent, Request)
                        and k.capacity < j.parent.demand):
                    continue

                if isinstance(i, NodePK):

                    # Destination of pickup node i
                    di = pairs_dict[i]

                    if j != di:

                        # Cannot access i's final destination from
                        # intermediate node j
                        if di not in distance_dict[j].keys():
                            continue

                        max_ride_delay = (
                                distance_dict[i][di]
                                + i.parent.max_total_delay
                        )

                        dist_j_di = distance_dict[j][di]

                        # Can't arrive in i's destination on time
                        # passing by intermediate node j
                        if dist_i_j + dist_j_di > max_ride_delay:
                            continue

                    # Can't get in j on time
                    if i.earliest > j.latest:
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


def get_viable_network(
        depot_list,
        origin_list,
        destination_list,
        pair_dic,
        distance_dic,
        speed=None,
        unit="sec"):

    def dist(o, d):
        dist_meters = distance_dic[o.network_node_id][d.network_node_id]
        if speed is not None:
            dist_seconds = int(3.6 * dist_meters / speed + 0.5)
            if unit == "min":
                return dist_seconds/60
            else:
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
            nodes_network[depot][o] = dist(depot, o)

    # Origins connect to other origins
    for o1 in origin_list:
        for o2 in origin_list:

            # No loop
            if o1 != o2:
                nodes_network[o1][o2] = dist(o1, o2)

    # Origins connect to destinations
    for o in origin_list:
        for d in destination_list:
            nodes_network[o][d] = dist(o, d)

    # Destination connect to origins
    for d in destination_list:
        for o in origin_list:

            # But not if origin and destination belong to same request
            if d != pair_dic[o]:
                nodes_network[d][o] = dist(d, o)

    # Destinations connect to destinations
    for d1 in destination_list:
        for d2 in destination_list:
            # No loop
            if d1 != d2:
                nodes_network[d1][d2] = dist(d1, d2)

    return nodes_network
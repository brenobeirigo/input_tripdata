from gurobipy import Model, GurobiError, GRB, quicksum


def can_reach(origin, target, max_delay, reachability_dic):
    """ Check if 'target' can be reached from 'origin' in less than
    'max_delay' time steps

    Arguments:
        origin {int} -- id of departure node
        target {int} -- id of node to reach
        max_delay {int} -- Maximum trip delay between origin and target
        reachability_dic {dict{int:dict{int:set}} -- Stores the set
            's' of nodes that can reach 'target' node in less then 't'
            time steps.  E.g.: reachability_dic[target][max_delay] = s

    Returns:
        [bool] -- True if 'target' can be reached from 'origin' in
            less than 'max_delay' time steps
    """

    for step in reachability_dic[target].keys():
        if step <= max_delay:
            if origin in reachability_dic[target][step]:
                return 1
    return 0


def ilp_node_reachability(
        reachability_dic,
        max_delay=180,
        log_path=None,
        time_limit=None):

    # List of nodes ids
    node_ids = sorted(list(reachability_dic.keys()))

    try:

        # Create a new model
        m = Model("region_centers")

        if log_path:
            m.Params.LogFile = "{}/region_centers_{}.log".format(
                log_path, max_delay
            )

            m.Params.ResultFile = "{}/region_centers_{}.lp".format(
                log_path, max_delay
            )

        # xi = 1, if vertex Vi is used as a region center
        # and 0 otherwise
        x = m.addVars(node_ids, vtype=GRB.BINARY, name="x")

        # Ensures that every node in the road network graph is reachable
        # within 'max_delay' travel time by at least one region center
        # selected from the nodes in the graph.
        # To extract the region centers, we select from V all vertices
        # V[i] such that x[i] = 1.

        for origin in node_ids:
            m.addConstr(
                (
                    quicksum(
                        x[center]
                        * can_reach(
                            center, origin, max_delay, reachability_dic
                        )
                        for center in node_ids
                    )
                    >= 1
                ),
                "ORIGIN_{}".format(origin),
            )

        # Set objective
        m.setObjective(quicksum(x), GRB.MINIMIZE)

        if time_limit is not None:
            m.Params.timeLimit = time_limit

        # Solve
        m.optimize()

        region_centers = list()

        # Model statuses
        is_unfeasible =  m.status == GRB.Status.INFEASIBLE
        is_umbounded = m.status == GRB.Status.UNBOUNDED
        found_optimal = m.status == GRB.Status.OPTIMAL
        found_time_expired = (
            m.status == GRB.Status.TIME_LIMIT and m.SolCount > 0
        )

        if is_umbounded:
            raise Exception(
                "The model cannot be solved because it is unbounded"
            )

        elif found_optimal or found_time_expired:

            if found_time_expired:
                print("TIME LIMIT ({} s) RECHEADED.".format(time_limit))

            # Sweep x_n = 1 variables to create list of region centers
            var_x = m.getAttr("x", x)
            for n in node_ids:
                if var_x[n] > 0.0001:
                    region_centers.append(n)

            return region_centers

        elif is_unfeasible:

            print("Model is infeasible.")
            raise Exception('Model is infeasible.')
            # exit(0)

        elif (
            m.status != GRB.Status.INF_OR_UNBD
            and m.status != GRB.Status.INFEASIBLE
        ):
            print("Optimization was stopped with status %d" % m.status)
            raise Exception('Model is infeasible.')

    except GurobiError as e:
        raise Exception(" Gurobi error code " + str(e.errno))

    except AttributeError as e:
        raise Exception("Encountered an attribute error:" + str(e))

# Copyright 2018, Gurobi Optimization, LLC

# This example formulates and solves the following simple MIP model:
#  maximize
#        x +   y + 2 z
#  subject to
#        x + 2 y + 3 z <= 4
#        x +   y       >= 1
#  x, y, z binary

from gurobipy import Model, GurobiError, GRB, quicksum

def is_reachable(reachability_dic, o,d, max_delay):
    for step in reachability_dic[d].keys():
        if step <= max_delay:
            if o in reachability_dic[d][step]:
                return 1
    return 0


def ilp_node_reachability(reachability_dic, max_delay = 180, log_path = None):

    # List of nodes ids
    node_ids = sorted(list(reachability_dic.keys()))
    #node_ids = node_ids[:100]
    
    try:

        # Create a new model
        m = Model("region_centers")

        if log_path:
            m.Params.LogFile='{}/region_centers_{}.log'.format(log_path, max_delay)
            

        # xi = 1, if vertex Vi is used as a region center and 0 otherwise
        x = m.addVars(node_ids, vtype=GRB.BINARY, name="x")

        # Ensures that every node in the road network graph is reachable
        # within 'max_delay' travel time by at least one region center
        # selected from the nodes in the graph.
        # To extract the region centers, we select from V all vertices
        # V[i] such that x[i] = 1.
        for d in node_ids:
            m.addConstr(quicksum(x[o] * is_reachable(reachability_dic, o, d, max_delay) for o in node_ids)>= 1)

        # Set objective
        m.setObjective(quicksum(x), GRB.MINIMIZE)

        # Solve
        m.optimize()
        
        region_centers = list()

        if m.status == GRB.Status.OPTIMAL:

            var_x = m.getAttr('x', x)
            for n in node_ids:
                if var_x[n] > 0.0001:
                    region_centers.append(n)
        
            return region_centers
                    
        else:
            print('No solution')
            return None


    except GurobiError as e:
        print('Error code ' + str(e.errno) + ": " + str(e))

    except AttributeError as e:
        print('Encountered an attribute error:' + str(e))

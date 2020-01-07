from milp.OptMethod import *
from collections import defaultdict
from gurobipy import Model, GurobiError, GRB, quicksum
from datetime import datetime

class DARP_SL(OptMethod):

    def __init__(self,
                 DAO,
                 TIME_LIMIT):
        self.TIME_LIMIT = TIME_LIMIT
        self.DISCOUNT_PASSENGER_S = DAO.discount_passenger
        OptMethod.__init__(self, DAO)
        self.start()
    
    ##########################################################################
    ########### MILP SARP_PL (SHARE-A-RIDE PROBLEM WITH PARCEL LOCKERS) ######
    ##########################################################################
    def start(self):
        ##########################################################################
        #### SUBTOUR ELIMINATION + LAZY CONSTRAINTS ##############################
        ##########################################################################
        # Callback - use lazy constraints to eliminate sub-tours

        def subtourelim(model, where):
            if where == GRB.callback.MIPSOL:
                print("#### SUBTOUR ELIMINATION")
                print(len(self.nodes_dic))
                print("MODEL:", model)
                sol = model.cbGetSolution(model._vars)
                
                selected = defaultdict(list)
                # Get ride arcs
                for ride in sol:
                    if sol[ride] > 0.5:
                        selected[ride[0]].append(ride)

                
                print("SELECTED:", selected)
                """
                selected = []
                # make a list of edges selected in the solution
                for i in self.nodes_dic:
                    sol = model.cbGetSolution([model._vars[k,i,j] for j in self.nodes_dic])
                    print("SOL:", sol)
                    selected += [(k,i,j) for j in self.nodes_dic if sol[j] > 0.5]
                print("SELECTED:", selected)
                """
                """
                # find the shortest cycle in the selected edge list
                tour = subtour(selected)
                if len(tour) < n:
                # add a subtour elimination constraint
                expr = 0
                for i in range(len(tour)):
                    for j in range(i+1, len(tour)):
                    expr += model._vars[tour[i], tour[j]]
                model.cbLazy(expr <= len(tour)-1)
                """

        # Given a list of edges, finds the shortest subtour
        """
        def subtour(edges):
            
            visited = [False]*n
            cycles = []
            lengths = []
            selected = [[] for i in range(n)]
            for x,y in edges:
                selected[x].append(y)
            while True:
                current = visited.index(False)
                thiscycle = [current]
                while True:
                visited[current] = True
                neighbors = [x for x in selected[current] if not visited[x]]
                if len(neighbors) == 0:
                    break
                current = neighbors[0]
                thiscycle.append(current)
                cycles.append(thiscycle)
                lengths.append(len(thiscycle))
                if sum(lengths) == n:
                break
            return cycles[lengths.index(min(lengths))]
        """
        print("STARTING MILP...")
        # Start time - loading model info
        t1 = datetime.now()

        deny_service = True
        acquisition_cost_fsm = False

        try:

            valid_rides = self.get_valid_rides()
            valid_visits_dic = self.get_valid_visits(valid_rides)
            valid_visits = valid_visits_dic["all"]
            valid_visits_pk = valid_visits_dic["pk"]
            valid_loads = self.get_valid_loads(valid_visits)

            # Create a new model
            m = Model("DARP-SQ")

            #m.LogFile = "output/ilp/logs/gurobi.log"

            # Ex.:
            #  k     i   j      lockers in k         d_i      d_j
            # AV1_0 dl4 dl2 {'XS', 'C', 'L', 'A'} {'A', 'C'} {'A'}
            # AV1_0 pk1 dp2 {'XS', 'C', 'L', 'A'} {'A'} set()
            # AV1_0 dp1 dp2 {'XS', 'C', 'L', 'A'} set() set()
            
            # Binary variable, 1 if a vehicle k goes from model.Node i to node j
            
            ride = m.addVars(valid_rides,
                             vtype=GRB.BINARY,
                             name="x")

            # Arrival time of vehicle k at node i
            arrival_t = m.addVars(list(valid_visits),
                                  vtype=GRB.INTEGER,
                                  lb=0,
                                  name="u")

            print("Setting constraints...")
            logger.debug(
                "############################# VALID LOADS ##########################")
            logger.debug(pprint.pformat(valid_visits))

            # Load of compartment c of vehicle k at pickup node i
            load = m.addVars(valid_loads,
                             vtype=GRB.INTEGER,
                             lb=0,
                             name="w")

            # Ride time of request i served by vehicle k
            travel_t = m.addVars(list(valid_visits_pk),
                                 vtype=GRB.INTEGER,
                                 lb=0,
                                 name="r")

            #### ROUTING CONSTRAINTS ##########################################
            print("    # MAX_1_OUT")
            # (ONLY_PK) = Max. one outbound arc in pickup nodes
            m.addConstrs((ride.sum('*', i, '*') <= 1 for i in self.pd_nodes), "MAX_1_OUT")

            print("    # ALL_REQ")
            # (ALL_REQ) = All requests are attended?
            if deny_service:
                m.addConstrs((ride.sum('*', i, '*') <= 1 for i in self.pk_points), "DENY_REQ")
            else:
                m.addConstrs((ride.sum('*', i, '*') == 1 for i in self.pk_points), "ALL_REQ")

            print("    # ONLY_1_IN")
            # (ONLY_DL) = There is only one vehicle arriving at a pk/dl point
            m.addConstrs((ride.sum('*', '*', j) <= 1
                          for j in self.pd_nodes), "ONLY_1_IN")

            print("    # BEGIN")
            # (BEGIN) = Every vehicle leaves the start depot
            m.addConstrs((ride.sum(k, self.starting_locations, '*') <= 1
                          for k in self.vehicles), "BEGIN")

            print("    # SERVICE TIER")
            #pprint.pprint(valid_rides)
            for h, reqs in self.req_class_dic.items():
                #print(h, reqs, [r.origin.id for r in reqs])
                
                a = quicksum(ride[k, i, j]
                            for k, i, j in valid_rides
                            if i in [r.origin.id for r in reqs])
                
                b = int(self.sl_config[h]["overall_sl"] * len(reqs)+0.5)
                
                #print("a:", a)
                
                #print("b({}*{}={})".format(self.sl_config[h]["overall_sl"], len(reqs), b))
                
                m.addConstr(a>=b, "SERVICE_TIER[%s]" % (h))



            print("    # IF_PK_DL1 / IF_PK_DL2")
            # Same vehicle services pickup and delivery:
            m.addConstrs((ride.sum(k, i, '*') - ride.sum(k, '*', j) == 0
                          for i, j in self.pd_pairs.items()
                          for k in self.vehicles
                          if (k, i) in valid_visits
                          and (k, j) in valid_visits), name="IF_V_PK_DL")

            """m.addConstrs((ride.sum('*', i, '*') + ride.sum('*','*', j)  == 2*selected_req[i]
                          for i, j in self.pd_pairs.items()), name="IF_PK_DL2")
            """

            print("    # FLOW_VEH_PK")
            # (IN_OUT_PK) = self.vehicles enter and leave pk nodes
            m.addConstrs((ride.sum(k, '*', i) == ride.sum(k, i, '*')
                          for i in self.pk_points
                          for k in self.vehicles), name="FLOW_VEH_PK")

            print("    # FLOW_VEH_DL")
            # (IN_OUT) = self.vehicles enter and leave/stay dl nodes
            m.addConstrs((ride.sum(k, '*', i) >= ride.sum(k, i, '*')
                          for i in self.dl_points
                          for k in self.vehicles), name="FLOW_VEH_DL")

            print("    # ARRI_T")
            # (ARRI_T) = Arrival time at location j (departing from i) >=
            #            arrival time in i +
            #            service time in i +
            #            time to go from i to j
            #            IF there is a ride from i to j
            m.addConstrs((arrival_t[k, j] >=
                          arrival_t[k, i] +
                          self.nodes_dic[i].service_t +
                          self.times[i, j, self.vehicles_dic[k].type_vehicle] -
                          self.get_big_m(k, i, j) * (1 - ride[k, i, j])
                          for k, i, j in valid_rides), "ARRI_T")

            #### RIDE TIME CONSTRAINTS ########################################

            print("    # RIDE_1")
            r1 = datetime.now()
            # (RIDE_1) = Ride time from i to j >=
            #            time_from_i_to_j
            m.addConstrs((travel_t[k, i] >= self.times[i, j, self.vehicles_dic[k].type_vehicle]
                          for k in self.vehicles
                          for i, j in self.pd_tuples
                          if (k, i, j) in valid_rides), "RIDE_1")

            print("    # RIDE_2")
            # (RIDE_2) = Ride time from i to j <=
            #            time_from_i_to_j + MAX_LATENESS
            m.addConstrs((travel_t[k, i] <=
                          self.times[i, j, self.vehicles_dic[k].type_vehicle] + self.max_delivery_delay[i]
                          for k in self.vehicles
                          for i, j in self.pd_tuples
                          if (k, i, j) in valid_rides), "RIDE_2")

            print("    # RIDE_3")
            # (RIDE_3) = Ride time from i to j is >=
            # arrival_time_j - (arrival_time_i + self.service_time_i)
            m.addConstrs((travel_t[k, i] ==
                          arrival_t[k, j] -
                          (arrival_t[k, i] +
                           self.nodes_dic[i].service_t)
                          for k in self.vehicles
                          for i, j in self.pd_tuples
                          if (k, i, j) in valid_rides), "RIDE_3")

            ### TIME WINDOW CONSTRAINTS #######################################
            print("    # EARL")
            #>>>>>> TIME WINDOW FOR PICKUP
            # (EARL) = Arrival time in i >=
            #          earliest arrival time in i
            m.addConstrs((arrival_t[k, i] >= self.earliest_latest[(self.vehicles_dic[k].type_vehicle, i)]["earliest"]
                          for (k, i) in valid_visits_pk), "EARL")

            print("    # LATE")
            # (LATE) = Arrival time in i <=
            #          earliest arrival time + MAX_PICKUP_LATENESS
            m.addConstrs((arrival_t[k, i] <= self.earliest_latest[(self.vehicles_dic[k].type_vehicle, i)]["latest"]
                          for (k, i) in valid_visits_pk), "LATE")

            #>>>>>> TIME WINDOW FOR MAX. DURATION OF ROUTE
            # (POWER) = Maximal duration of route k <= POWER_K autonomy
            """
            for veh in self.vehicles:
                a = quicksum(self.cost_in_s[i, j, self.vehicles_dic[k].type_vehicle] * ride[k, i, j]
                             for k, i, j in valid_rides
                                 if k == veh )
                m.addConstr(a <= self.DAO.vehicle_dic[k]
                                     .autonomy * 3600, "POWER[%s]" % (k))
            """
            #### LOADING CONSTRAINTS ##########################################

            print("    # LOAD")
            # (LOAD) = Guarantee load flow
            #          Load of compartment c of vehicle k in node j >=
            #          Load of compartment c of vehicle k in node i +
            #          Load collected for compartment c at node j
            #          IF there is a ride of vehicle k from i to j
            m.addConstrs((load[c, k, j] >=
                          (load[c, k, i] + self.pk_dl[j, c]) -
                          self.get_big_w(c, k, j) * (1 - ride[k, i, j])
                          for k, i, j in valid_rides
                          for c in self.lockers_v[k]
                          if (c, k, i) in valid_loads
                          and (c, k, j) in valid_loads), "LOAD")

            print("    # LOAD_END_DL")
            for c, v, dl in valid_loads:
                if dl in self.dl_points:
                    m.addConstr((load[c, v, dl] <= (
                        self.capacity_vehicle[v, c] + self.pk_dl[dl, c]) * ride.sum(v, dl, '*')), "LOAD_END_DL[%s,%s,%s]" % (c, v, dl))

            print("    # LOAD_MIN")
            # (LOAD_MIN) = Load of vehicle k in node i >=
            #              MAX(0, PK/DL demand in i)
            m.addConstrs((load[c, k, i] >= max(0, self.pk_dl[i, c])
                          for c, k, i in valid_loads), "LOAD_MIN")

            print("    # LOAD_MAX")
            # (LOAD_MAX) = Load of compartment c of vehicle k in node i <=
            #              MIN(MAX_LOAD, MAX_LOAD - DL demand in i)
            #              Every time a DL node is visited, it is KNOWN
            #              that the load will be decremented. Hence, it
            #              is impossible that the remaining load is higher than
            #              MAX_LOAD, MAX_LOAD - DL
            m.addConstrs((load[c, k, i] <= min(self.capacity_vehicle[k, c],
                                               self.capacity_vehicle[k, c]
                                               + self.pk_dl[i, c])
                          for c, k, i in valid_loads
                          ), "LOAD_MAX")

            # The constrainst only applies to nodes that can be visited by
            # vehicle k. Suppose the following:
            # LOAD(XS,AV2,DL2) <= MIN(Q(AV2, XS), Q(AV2, XS) + D(DL2,XS))
            #   must be >=0!   <=         1            1     +   (-2)
            #                  <= -1
            # Vehicle AV2 cannot visit node DL2

            #### FEASIBILITY CONSTRAINTS ######################################
            print("    # LOAD_0")
            m.addConstrs((load[c, k, i] >= 0
                          for c, k, i in valid_loads),  "LOAD_0")

            print("    # ARRI_0")
            m.addConstrs((arrival_t[k, i] >= 0
                          for k, i in arrival_t), "ARRI_0")

            print("    # ARRI_AT_ORIGIN")
            # Guarantees a vehicle will be available only at an specified time
            # Some vehicles are discarded because they cannot access any node
            # (not a valid visit)
            m.addConstrs((arrival_t[k, i] ==
                          self.vehicles_dic[k]
                          .pos
                          .arrival_t - config.start_revealing_tstamp
                          for k, i in arrival_t
                          if i == self.vehicles_dic[k]
                          .pos
                          .id), "ARRI_AT_ORIGIN")

            start_end_nodes = list(self.starting_locations)

            print("    # LOAD_DEPOT_0")
            m.addConstrs((load[c, k, i] == 0
                          for c, k, i in valid_loads
                          if i in start_end_nodes), "LOAD_DEPOT_0")

            #### OPTIMIZE MODEL ###############################################
            print("Setting fares of lockers...")
            fare_locker_dis = self.DAO.fare_locker_dis
            fare_locker = self.DAO.fare_locker

            print("Setting Objective function...")
            # OBJECTIVE FUNCTION 1 - INCREASE PROFIT
            # B: fare_locker[c] = fixed fare to deliver commodity c
            # Y: fare_locker_km[c] = variable fare (according to distance)
            #                        to deliver commodity c
            # C_ij: cost_in_s[i,j] = travel time(s) to go from i to j
            # Function = (B + Y*C_kij)*X_kij

            # Is acquisition cost considered
            acquistion_cost = 0
            if acquisition_cost_fsm:
                # Acquisition cost of vehicles (Fleet size and mix)
                acquistion_cost = quicksum(self.vehicles_dic[k].acquisition_cost
                                    * ride[k, self.vehicles_dic[k].pos.id, j]
                                    for k in self.vehicles_dic
                                    for j in self.nodes
                                    if (k, self.vehicles_dic[k].pos.id, j) in valid_rides)
            
            # Fixed fare + varied fare
            revenue = quicksum(d * (fare_locker[c]
                                    + fare_locker_dis[c]
                                    * self.cost_in_s[i, j, self.vehicles_dic[k].type_vehicle])
                                    * ride[k, i, j]
                                    for k in self.vehicles_dic
                                    for i, j in self.pd_pairs.items()
                                    if (k, i) in valid_visits and (k, j) in valid_visits
                                    for c, d in self.nodes_dic[i].get_demand_short().items())
            
            # Total operational cost
            operational_cost = quicksum(self.vehicles_dic[k].operation_cost_s
                                    * self.cost_in_s[i, j, self.vehicles_dic[k].type_vehicle]
                                    * ride[k, i, j]
                                    for k, i, j in valid_rides)
            
            # OF with acquisition cost
            # m.setObjective(revenue -operational_cost -acquistion_cost, GRB.MAXIMIZE)

            # OF profit
            m.setObjective(revenue -operational_cost -acquistion_cost, GRB.MAXIMIZE)

            logger.debug(
                "########################## COSTS #################################")
            for k, i, j in valid_rides:
                logger.debug("(%s) %s -> %s COST: %.4f (%.4f$/s * %ss)",
                             k,
                             i,
                             j,
                             self.vehicles_dic[k].operation_cost_s *
                             self.cost_in_s[i, j,
                                            self.vehicles_dic[k].type_vehicle],
                             self.vehicles_dic[k].operation_cost_s,
                             self.cost_in_s[i, j, self.vehicles_dic[k].type_vehicle])

            # DISCOUNT
            # Ride time of request i (minus service time (embarking
            # /disembarking)) served by vehicle k over the minimum
            # time spent to go travel from i to j

            # Setup time limit
            m.Params.timeLimit = self.TIME_LIMIT
            preprocessing_t = (datetime.now() - t1).seconds
            print("Optimizing...")
            
            # Optimize model + lazy constraints
            m._vars = ride
            m.params.LazyConstraints = 1
            m.optimize(subtourelim)
            
            print("Preprocessing:", preprocessing_t)
            print("Model runtime:", m.Runtime)
            m.write(config.debug_path)

            #### SHOW RESULTS #################################################
            # m.update()

            # Store route per vehicle

            # Model is unbounded
            if m.status == GRB.Status.UNBOUNDED:
                print('The model cannot be solved because it is unbounded')
                self.status = "unbounded"
                # exit(0)

            # If status is optimal
            elif m.status == GRB.Status.OPTIMAL or (m.status == GRB.Status.TIME_LIMIT and m.SolCount > 0):
                
                self.status = "optimal"

                if m.status == GRB.Status.TIME_LIMIT:
                    print("TIME LIMIT (%d s) RECHEADED." % (self.TIME_LIMIT))

                # Get binary variables Xkij
                var_ride = m.getAttr('x', ride)

                # Get travel self.times of each request
                var_travel_t = m.getAttr('x', travel_t)

                # Get load of vehicle at each point
                var_load = m.getAttr('x', load)

                # Get arrival time at each point
                var_arrival_t = m.getAttr('x', arrival_t)

                # Convert loads to integer
                for k in var_load.keys():
                    var_load[k] = int(var_load[k])

                print("REQUEST DICTIONARY")
                pprint.pprint(self.request_dic)
                print("ALL:", [r.id for r in self.request_dic.values()])

                ###################################################################

                # MODEL ATTRIBUTES
                # http://www.gurobi.com/documentation/7.5/refman/model_attributes.html
                # BEST PRACTICES
                # http://www.gurobi.com/pdfs/user-events/2016-frankfurt/Best-Practices.pdf
                # http://www.dcc.fc.up.pt/~jpp/seminars/azores/gurobi-intro.pdf
                solver_sol = {
                    "gap": m.MIPGap,
                    "num_vars": m.NumVars,
                    "num_constrs": m.NumConstrs,
                    "obj_bound": m.ObjBound,
                    "obj_val": m.ObjVal,
                    "node_count": m.NodeCount,
                    "sol_count": m.SolCount,
                    "iter_count": m.IterCount,
                    "runtime": m.Runtime,
                    "preprocessing_t": preprocessing_t,
                    "status": m.status
                }

                # Create DARP answer
                darp_answer = Response(self.vehicles,
                                       self.request_dic,
                                       self.arcs,
                                       valid_rides,
                                       var_ride,
                                       var_travel_t,
                                       var_load,
                                       var_arrival_t,
                                       self.DAO,
                                       solver_sol
                                       )
                # Return answer
                self.response = darp_answer

                print("RESPONSE:", solver_sol)
                
                # exit(0)

            elif m.status == GRB.Status.INFEASIBLE:

                self.status = "infeasible"
                print('Model is infeasible.')
                #raise Exception('Model is infeasible.')
                # exit(0)

            elif m.status != GRB.Status.INF_OR_UNBD and m.status != GRB.Status.INFEASIBLE:
                print('Optimization was stopped with status %d' % m.status)
                self.status = "interrupted"
                # exit(0)

            # IRREDUCIBLE INCONSISTENT SUBSYSTEM (IIS).
            # An IIS is a subset of the constraints and variable bounds
            # of the original model. If all constraints in the model
            # except those in the IIS are removed, the model is still
            # infeasible. However, further removing any one member
            # of the IIS produces a feasible result.
            # do IIS

            """print('The model is infeasible; computing IIS')
            removed = []

            # Loop until we reduce to a model that can be solved
            while True:

                m.computeIIS()
                print('\nThe following constraint cannot be satisfied:')
                for c in m.getConstrs():
                    if c.IISConstr:
                        print('%s' % c.constrName)
                        # Remove a single constraint from the model
                        removed.append(str(c.constrName))
                        m.remove(c)
                        break
                print('')

                m.optimize()
                status = m.status

                if status == GRB.Status.UNBOUNDED:
                    print('The model cannot be solved because it is unbounded')
                    exit(0)
                if status == GRB.Status.OPTIMAL:
                    break
                if status != GRB.Status.INF_OR_UNBD and status != GRB.Status.INFEASIBLE:
                    print('Optimization was stopped with status %d' % status)
                    exit(0)

            print('\nThe following constraints were removed to get a feasible LP:')
            print(removed)
            """
            """
            # MODEL RELAXATION
            # Relax the constraints to make the model feasible
            print('The model is infeasible; relaxing the constraints')
            orignumvars = m.NumVars
            m.feasRelaxS(0, False, False, True)
            m.optimize()
            status = m.status
            if status in (GRB.Status.INF_OR_UNBD, GRB.Status.INFEASIBLE, GRB.Status.UNBOUNDED):
                print('The relaxed model cannot be solved \
                    because it is infeasible or unbounded')
                exit(1)

            if status != GRB.Status.OPTIMAL:
                print('Optimization was stopped with status %d' % status)
                exit(1)

            print('\nSlack values:')
            slacks = m.getVars()[orignumvars:]
            for sv in slacks:
                if sv.X > 1e-6:
                    print('%s = %g' % (sv.VarName, sv.X))
            """

        except GurobiError:
            print('Error reported:', GurobiError.message)

        except:
            print('CARAIO!')
            raise

        finally:
            # Reset indices of nodes
            Node.reset_nodes_ids()
            Vehicle.reset_vehicles_ids()

    ##########################################################################
    ##########################################################################
    ##########################################################################
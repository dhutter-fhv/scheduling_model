from solver import GurobiSolver
from translation import GurobiEncoder, FJSSPInstancesTranslator
from model import Order

def write_result(source : str, instance : int, expected_result, runtime : float, optimal : bool, fitness : float, gap : float):
    path = r'C:\Users\huda\Documents\GitHub\scheduling_model\code\reworked_data_model\results\gurobi_experiment_results.txt'
    with open(path, 'a') as f:
        f.write(f'{source};{instance};{runtime};{optimal};{expected_result};{fitness}\n')

experiments = 1
instances = [['5_Kacem', 1, 11], ['5_Kacem', 4, 12]]
for instance in instances:
    for i in range(experiments):
        source = instance[0]#'5_Kacem'
        benchmark_id = instance[1]#4
        best_known = instance[2] # 0 if unknown

        simple_translator = FJSSPInstancesTranslator()
        production_environment = simple_translator.translate(source=source, benchmark_id=benchmark_id)

        orders : list[Order] = []
        for i in range(len(production_environment.resources.values())): # should be the same amount as recipes for now
            orders.append(Order(delivery_time=1000, latest_acceptable_time=1000, resources=[(production_environment.get_resource(i), 1)], penalty=100.0, tardiness_fee=50.0, divisible=False, profit=500.0))

        encoder = GurobiEncoder()
        nb_machines, nb_jobs, nb_operations, job_ops_machs, durations, job_op_suitable, upper_bound, jobs = encoder.encode(production_environment, orders)
        solver = GurobiSolver(production_environment)
        solver.initialize(nb_jobs, nb_operations, nb_machines, job_ops_machs, durations, job_op_suitable, upper_bound)
        solver.m.Params.TIME_LIMIT = 20 # time limit in seconds
        solver.run()

        #if solver.m.Status == 2:
        #    # Optimum found
        #    print(solver.m.ObjVal)
        #elif solver.m.Status == 9:
        #    # Time Limit Exceeded
        #    print(f'Bounds: {solver.m.ObjBound}')
        #NOTE: Gurobi does not count initialization (including creating all constraints) for the time limit 
        #print(solver.get_best_fitness())
        #print(f'Optimal: {solver.m.Status == 2}') # NOTE: status 2 = optimal, status 9 = time limit reached
        #print(f'Time Limit Reached: {solver.m.Status == 9}')
        #xsol, ysol, csol = solver.get_best() # TODO: change signature
        #print(f'XSOL: {xsol}')
        #print(f'YSOL: {ysol}')
        #print(f'CSOL: {csol}')
        #print(f'Runtime: {solver.m.Runtime}')
        #print(f'Gap: {solver.m.MIPGap}')
        #values = solver.m.getVars()
        #print(solver.Cmax.X)
        print(solver.Cmax.UB)
        print(solver.Cmax.X)
        print(solver.m.Xn)
        print(f'MAX BOUND: {solver.m.MaxBound}')
        print(f'MAX COEFF: {solver.m.MaxCoeff}')
        print(f'MIN COEFF: {solver.m.MinCoeff}')
        print(f'POOL OBJ BOUND: {solver.m.PoolObjBound}')
        #solver.m.write(r'C:\Users\huda\Documents\GitHub\scheduling_model\code\reworked_data_model\results\gurobi_results.sol')
        write_result(instance[0], instance[1], instance[2], solver.m.Runtime, solver.m.Status == 2, solver.Cmax.X, solver.m.MIPGap) # TODO: best feasible fitness
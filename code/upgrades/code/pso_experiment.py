import pyswarms as ps
import numpy as np

def rosenbrock_with_args(x, a, b, c=0):
    f = (a - x[:, 0]) ** 2 + b * (x[:, 1] - x[:, 0] ** 2) ** 2 + c
    return f

def select(value, options):
    for i in range(len(options)):
        if value <= (i+1)/len(options):
            return options[i]
    return options[-1]

def create_solution(x, y, z, durations):
    sequence = np.argsort(x).tolist()
    machines = []
    #workers = []
    for i in range(n_operations):
        available_machines = [j for j in range(len(durations[i])) if max(durations[i][j]) > 0]
        machine = select(y[i], available_machines)

        #available_workers = [j for j in range(len(durations[i][machine])) if max(durations[i][machine]) > 0]
        #worker = select(z[i], available_workers)

        machines.append(machine)
        #workers.append(worker)
    return sequence, machines#, workers

def fitness(solution, n_operations : int, durations : list[list[int]], job_sequence : list[int]):
    x = solution[:n_operations]
    y = solution[n_operations:]#solution[n_operations:2*n_operations]
    z = []#solution[2*n_operations:]
    #sequence, machines, workers = create_solution(x, y, z, durations)
    sequence, machines = create_solution(x, y, z, durations) # just FJSSP for testing
    end = 0
    ends_on_machines = [0] * max(machines)
    ends_on_jobs = [0] * max(job_sequence)
    for i in range(len(sequence)):
        start = max(ends_on_jobs[job_sequence[i]], ends_on_machines[machines[i]])
        if start + durations[i][machines[i]] > end:
            end = start + durations[i][machines[i]]
        ends_on_jobs[job_sequence[i]] = start + durations[i][machines[i]]
        ends_on_machines[machines[i]] = start + durations[i][machines[i]]
    return end

from benchmark_parser import BenchmarkParser
parser = BenchmarkParser()
path = ''
instance = parser.parse_benchmark(path)
n_operations = instance.n_operations()
durations = instance.durations()
kwargs={"n_operations": n_operations, "durations": durations, "job_sequence": instance.job_sequence()}

# Set-up hyperparameters
options = {'c1': 0.5, 'c2': 0.3, 'w':0.9}

n_operations = 50
x_max = [1.0] * n_operations
x_min = [0.0] * n_operations
bounds = (x_min, x_max)

# Call instance of PSO with bounds argument
optimizer = ps.single.GlobalBestPSO(n_particles=10, dimensions=2, options=options, bounds=bounds)
# Perform optimization
cost, pos = optimizer.optimize(fitness, iters=1000, **kwargs)



"""def fitness_function(x):
    sum = 0
    for i in range(len(x)):
        sum += x[i]
    return sum

x0 = 8 * [0]
xopt, es = cma.fmin2(fitness_function, x0 , 0.5, {'integer_variables': list(range(len(x0))), 'bounds': [0, 100]})#'bounds': [-1, 15 - 1e-9]})#, {'verb_disp': 1})
int_result = [np.floor(x) for x in es.result[0]] #NOTE: the cma library truncates/rounds all values in the background itself, apparently np.floor
print(f'Result: {int_result}')

print(xopt)"""
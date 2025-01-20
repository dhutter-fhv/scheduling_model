import numpy as np

n_operations = 5
n_machines = 3
n_workers = 4
omw = [
    [[0, 2, 3, 2], [1, 0, 2, 1], [3, 3, 3, 2]],
    [[1, 3, 2, 0], [2, 1, 3, 2], [0, 0, 3, 3]],
    [[3, 2, 1, 1], [0, 0, 0, 2], [0, 3, 3, 0]],
    [[0, 3, 3, 3], [1, 3, 2, 3], [3, 0, 1, 0]],
    [[3, 2, 1, 1], [1, 0, 2, 0], [3, 2, 3, 2]]
]

example = [0.1, 0.2, 0.15, 0.3, 0.7, 0.3, 0.5, 0.3, 0.5, 0.1, 0.4, 0.3, 0.6, 0.7, 0.1]

def select(value, options):
    for i in range(len(options)):
        if value <= (i+1)/len(options):
            return options[i]
    return options[-1]

def create_solution(x, y, z):
    sequence = np.argsort(x).tolist()
    machines = []
    workers = []
    for i in range(n_operations):
        available_machines = [j for j in range(len(omw[i])) if max(omw[i][j]) > 0]
        machine = select(y[i], available_machines)

        available_workers = [j for j in range(len(omw[i][machine])) if max(omw[i][machine]) > 0]
        worker = select(z[i], available_workers)

        machines.append(machine)
        workers.append(worker)
    return sequence, machines, workers

def fitness(solution):
    x = solution[:n_operations]
    y = solution[n_operations:2*n_operations]
    z = solution[2*n_operations:]
    sequence, machines, workers = create_solution(x, y, z)
    print(sequence)
    print(machines)
    print(workers)
    # ...

fitness(example)
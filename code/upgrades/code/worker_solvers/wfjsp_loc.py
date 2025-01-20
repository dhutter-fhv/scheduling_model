# -*- coding: utf-8 -*-
"""
Created on Tue May  7 07:46:16 2024

@author: tst
"""

#WFJSP with Hexaly Local Solver

# nach dem localsover (hexaly) fjsp Example: file:///C:/localsolver_12_5/docs/exampletour/flexiblejobshop.html

import localsolver

#Callback Bsp siehe https://www.hexaly.com/docs/last/technicalfeatures/callbacks.html
class SolutionListener:
    def __init__(self):
        self.last_best_value = 1000000
        self.solution_count = 0
        self.known_best = 0#885
    def my_callback(self, ls, cb_type):
        time = ls.statistics.running_time
        obj = round(ls.model.objectives[0].value)
        bnd = round(ls.solution.get_objective_bound(0))
        if (ls.solution.status.value == 2 or ls.solution.status.value == 3) and obj < self.last_best_value: 
            self.solution_count += 1
            self.last_best_value = obj
            print(
                "Solution %i, time = %f s, objective = %i, bound = %i"
                % (self.solution_count, time, obj, bnd)
                )
            if self.last_best_value - self.known_best < 0:
                print('Stop early - known_best achieved')
                ls.stop()

#read and arrange Data
#Small Size Data: SFJW-01.txt to SFJW-10.txt
#filename = r'C:\Users\tst\OneDrive - FH Vorarlberg\Forschung\JobShopScheduling\MO-FJSPW_BenchmarkDataInstances\SFJW\SFJW-10.txt'
#Medium size Data: MFJW-01.txt to MFJW-07.txt
#filename = r'C:\Users\tst\OneDrive - FH Vorarlberg\Forschung\JobShopScheduling\MO-FJSPW_BenchmarkDataInstances\MFJW\MFJW-03.txt'

#von David erzeugte Probleme
filename = r'C:\Users\tst\OneDrive - FH Vorarlberg\Forschung\JobShopScheduling\changed_benchmarks\6_Fattahi_18_updated.fjs'
f = open(filename)

lines = f.readlines()
first_line = lines[0].split()
# Number of jobs
nb_jobs = int(first_line[0])
# Number of machines
nb_machines = int(first_line[1])
# Number of workers
nb_workers = int(first_line[2])
# Number of operations for each job
nb_operations = [int(lines[j + 1].split()[0]) for j in range(nb_jobs)]

# Constant for incompatible machines
INFINITE = 1000000

# Number of tasks
nb_tasks = sum(nb_operations[j] for j in range(nb_jobs))
        
# Processing time for each task, for each machine-worker combination

task_processing_time_data = [[[INFINITE for s in range(nb_workers)] 
                                    for m in range(nb_machines)] 
                                    for i in range(nb_tasks)]

# For each job, for each operation, the corresponding task id
job_operation_task = [[0 for o in range(nb_operations[j])] for j in range(nb_jobs)]


task__machsuitable = {}
task__workersuitable = {}
id = 0
for j in range(nb_jobs):
    line = lines[j + 1].split()
    tmp_idx = 1
    for o in range(nb_operations[j]):
        nb_machines_operation = int(line[tmp_idx])
        tmp_idx += 1
        suitable_machine_helper = []
        suitable_worker_helper = []
        for i in range(nb_machines_operation):
            machine = int(line[tmp_idx])
            suitable_machine_helper += [machine-1]
            nb_m_workers = int(line[tmp_idx + 1])
            tmp_idx += 2
            for s in range(nb_m_workers):
                worker = int(line[tmp_idx])
                time = int(line[tmp_idx + 1])
                tmp_idx += 2
                task_processing_time_data[id][machine-1][worker-1] = time
                suitable_worker_helper += [worker-1]
                
        task__workersuitable[id] = suitable_worker_helper
        task__machsuitable[id] = suitable_machine_helper
        job_operation_task[j][o] = id
        id = id + 1


# Trivial upper bound for the completion times of the tasks
L=0
for i in range(nb_tasks):
    L += max(task_processing_time_data[i][m][s] 
             for m in range(nb_machines) 
             for s in range(nb_workers) if task_processing_time_data[i][m][s] != INFINITE )

 #-----------------------------------------------------------------------------
 # Build the model
 #-----------------------------------------------------------------------------

with localsolver.LocalSolver() as ls: 
    # Declare the optimization model
    model = ls.model
    
    # Sequence of tasks on each machine worker combination *******************
    jobs_m_order = [model.list(nb_tasks) for m in range(nb_machines)]
    machines = model.array(jobs_m_order)
    
    # Each task is scheduled on a machine
    model.constraint(model.partition(machines))   
    
    # Only compatible machines can be selected for a task
    for i in range(nb_tasks):
        for m in range(nb_machines):
            if task__machsuitable[i].count(m) == 0:
                    model.constraint(model.not_(model.contains(jobs_m_order[m], i)))
    
    # For each task, the selected machine
    task_machine = [model.find(machines, i) for i in range(nb_tasks)]
    
    # Sequence of tasks for each worker ***********************************
    jobs_w_order = [model.list(nb_tasks) for s in range(nb_workers)]
    workers = model.array(jobs_w_order)
    
    # Each task is scheduled for a worker
    model.constraint(model.partition(workers)) 
    
    # Only compatible workers can be selected for a task
    for i in range(nb_tasks):
        for s in range(nb_workers):
            if task__workersuitable[i].count(s) == 0:
                model.constraint(model.not_(model.contains(jobs_w_order[s], i)))
    
    # For each task, the selected worker
    task_worker = [model.find(workers, i) for i in range(nb_tasks)]
    
    task_processing_time = model.array(task_processing_time_data)
    
    # Interval decisions: time range of each task
    tasks = [model.interval(0, L) for i in range(nb_tasks)]
    
    # The task duration depends on the selected machine and worker
    duration = [model.at(task_processing_time, i, task_machine[i], task_worker[i]) for i in range(nb_tasks)]
    for i in range(nb_tasks):
        model.constraint(model.length(tasks[i]) == duration[i])
    
    task_array = model.array(tasks)
    
    # Precedence constraints between the operations of a job
    for j in range(nb_jobs):
        for o in range(nb_operations[j] - 1):
            i1 = job_operation_task[j][o]
            i2 = job_operation_task[j][o + 1]
            model.constraint(tasks[i1] < tasks[i2])
    
    # Disjunctive resource constraints between the tasks on a machine
    for m in range(nb_machines):
        sequence_m = jobs_m_order[m]
        sequence_m_lambda = model.lambda_function(
            lambda i: task_array[sequence_m[i]] < task_array[sequence_m[i + 1]])
        model.constraint(model.and_(model.range(0, model.count(sequence_m) - 1), sequence_m_lambda))
    
    # Disjunctive resource constraints between the tasks of a worker
    for s in range(nb_workers):
        sequence_w = jobs_w_order[s]
        sequence_w_lambda = model.lambda_function(
            lambda i: task_array[sequence_w[i]] < task_array[sequence_w[i + 1]])
        model.constraint(model.and_(model.range(0, model.count(sequence_w) - 1), sequence_w_lambda))
    
    # Minimize the makespan: end of the last task
    makespan = model.max([model.end(tasks[i]) for i in range(nb_tasks)])
    model.minimize(makespan)
    
    model.close()
    
    # Parameterize the solver
    ls.param.time_limit = 30
    ls.param.verbosity = 0 #1 defaul 0 quiet 2 detailed
    
    #---------- ohne solution listener--------
    #ls.solve()

    #---------- mit solution listener--------
    ls.param.time_between_ticks = 1 # default 1sec INT!!
    cb = SolutionListener()
    ls.add_callback(localsolver.LSCallbackType.TIME_TICKED, cb.my_callback)
    ls.solve()
    #----------------------------------------
    
    #stats = ls.get_statistics()
    
    # Print final solution.
    # - for each operation of each job, the selected machine, the start and end dates
    
    for j in range(nb_jobs):
        for o in range(0, nb_operations[j]):
            taskIndex = job_operation_task[j][o]
            print('Job %i Operation %i on Maschine %i by Worker %i starts at %i ends at %i (duration %i)' 
                  %(j,
                    o,
                    task_machine[taskIndex].value + 1,
                    task_worker[taskIndex].value + 1,
                    tasks[taskIndex].value.start(),
                    tasks[taskIndex].value.end(),
                    tasks[taskIndex].value.end()-tasks[taskIndex].value.start()))
    
    print("solve status: " + str(ls.solution.status))
    print("solve status value: " + str(ls.solution.status.value))
    print("Best objective value: %i" % makespan.value)
    print('Objektive lower bound: %i' % ls.solution.get_objective_bound(0))
    print("Wall time : %f s" % ls.statistics.running_time)
    
    #graphische Darstellung
    import docplex.cp.utils_visu as visu
    if visu.is_visu_enabled():
        # Draw solution
        visu.timeline('HexalyLocalSolver Solution for flexible job-shop problem with worker constraint ' + filename)
        visu.panel('Machines')
        for m in range(nb_machines):
            visu.sequence(name='M' + str(m+1))
            for j in range(nb_jobs):
                for o in range(0, nb_operations[j]):
                    taskIndex = job_operation_task[j][o]
                    start_value = tasks[taskIndex].value.start()
                    end_value = tasks[taskIndex].value.end()
                    mach = task_machine[taskIndex].value
                    wrkr = task_worker[taskIndex].value + 1
                    if m == mach:
                        visu.interval(start_value, end_value, j, 'J{}_O{} by W{}'.format(j+1,o+1,wrkr))
        visu.show()
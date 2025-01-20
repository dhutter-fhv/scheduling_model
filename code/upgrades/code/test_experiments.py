import os
import psutil
from multiprocessing import Process, Value
from test_monitor import monitor_resources
# import gurobi stuff
import gurobipy as gp

# import cplex solver stuff
from docplex.cp.model import *
import docplex.cp.utils_visu as visu
from docplex.cp.solver.solver_listener import *
from docplex.mp.model import Model
from docplex.mp.progress import ProgressListener, ProgressClock

# import ortools stuff
from ortools.sat.python import cp_model
import collections

# import hexaly stuff
import localsolver


import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

TIME_LIMIT_IN_SECONDS = 1200

def get_cpu_ram_stats():
    return psutil.cpu_percent(), psutil.virtual_memory().percent

def run_gurobi(path):
    history = [(0, float('inf'), -float('inf'))]
    resources = [(0, 0)]

    def SolutionListener(model, where):
        cpu, ram = get_cpu_ram_stats()
        resources.append((cpu, ram))
        if where == gp.GRB.Callback.MIPSOL:
            time = model.cbGet(gp.GRB.Callback.RUNTIME)
            obj_best = round(model.cbGet(gp.GRB.Callback.MIPSOL_OBJBST))
            bnd = round(model.cbGet(gp.GRB.Callback.MIPSOL_OBJBND))
            #print(obj_best)
            #input("prompt")
            #if obj_best < history[-1][1] or bnd > history[-1][2]:
            history.append((time, obj_best, bnd))

    f = open(path)
    lines = f.readlines()
    first_line = lines[0].split()
    nb_jobs = int(first_line[0])
    nb_machines = int(first_line[1])
    nb_operations = [int(lines[j + 1].split()[0]) for j in range(nb_jobs)]
    INFINITE = 1000000

    nb_tasks = sum(nb_operations[j] for j in range(nb_jobs))

    task_processing_time = [[[INFINITE for m in range(nb_machines)] for o in range(nb_operations[j])] for j in range(nb_jobs)]

    job_op_dur_helper = {}
    job_op_suitable = {}
    for j in range(nb_jobs):
        line = lines[j + 1].split()
        tmp = 0
        for o in range(nb_operations[j]):
            nb_machines_operation = int(line[tmp + o + 1])
            suitable_helper =[]
            for i in range(nb_machines_operation):
                machine = int(line[tmp + o + 2 * i + 2]) - 1
                time = int(line[tmp + o + 2 * i + 3])
                task_processing_time[j][o][machine] = time
                suitable_helper += [machine+1]
                job_op_dur_helper[j+1,o+1,machine+1] = time
                
            job_op_suitable[j+1,o+1] = suitable_helper
            tmp = tmp + 2 * nb_machines_operation

    job_ops_machs, duration = gp.multidict(job_op_dur_helper)

    L=0
    for j in range(nb_jobs):
        for o in range(nb_operations[j]):
            L += max(task_processing_time[j][o][m] for m in range(nb_machines) if task_processing_time[j][o][m] != INFINITE)

    m = gp.Model('fjsp_lp_gurobi')

    jobs = [j for j in range(1,nb_jobs+1)]
    job_ops = [(j+1,k+1) for j in range(nb_jobs) for k in range(nb_operations[j])] 
    machines = [m for m in range(1,nb_machines+1)]
    list_X_var = []
    for j, k in job_ops :
        if j < nb_jobs :
            for jp, kp in job_ops:
                if jp > j:
                    list_X_var.append((j,k,jp,kp))
    
    # Variables
    Y = m.addVars(job_ops_machs, obj = 0.0, vtype=gp.GRB.BINARY, name ="Y")
    X = m.addVars(list_X_var, obj = 0.0, vtype=gp.GRB.BINARY, name ="X")
    C = m.addVars(job_ops,  obj = 0.0, lb = 0.0, vtype=gp.GRB.CONTINUOUS, name ="C")
    Cmax = m.addVar(obj = 1.0, name="Cmax")

    m.addConstrs((Y.sum(j,k,'*') == 1 for j, k in job_ops), "Y_const")

    m.addConstrs((Y.prod(duration,j,k,'*') <= C[j,k] for j, k in job_ops if k == 1),"C_time")

    m.addConstrs((Y.prod(duration,j,k,'*') + C[j,k-1] <= C[j,k] for j, k in job_ops if k != 1), "C_time")

    m.addConstrs((C[j,k] >= C[jp,kp] + duration[j,k,i] - L*(3 - X[j,k,jp,kp] - Y[j,k,i] - Y[jp,kp,i]) 
                for j, k in job_ops if j < nb_jobs
                for jp, kp in job_ops if jp > j 
                for i in machines if i in job_op_suitable[j,k] if i in job_op_suitable[jp,kp]), "l1")

    m.addConstrs((C[jp,kp] >= C[j,k] + duration[jp,kp,i] - L*(X[j,k,jp,kp] + 2 - Y[j,k,i] - Y[jp,kp,i]) 
                for j, k in job_ops if j < nb_jobs
                for jp, kp in job_ops if jp > j 
                for i in machines if i in job_op_suitable[j,k] if i in job_op_suitable[jp,kp]), "l2")

    m.addConstrs((Cmax>=C[j,nb_operations[j-1]] for j in jobs),"Cmax")

    timelimit = TIME_LIMIT_IN_SECONDS
    m.Params.TimeLimit = timelimit
    m.Params.LogToConsole = 0

    m.update()
    m.display()

    m.optimize(SolutionListener)
    
    status = m.status
    xsol = m.getAttr('X', X)
    ysol = m.getAttr('X', Y)
    csol = m.getAttr('X', C)
    C_max_SOL = Cmax.X
    C_max_LB = m.ObjBound

    start_times = []
    assignments = []
    for j, k, i in job_ops_machs:
        if ysol[j,k,i] > 0:
            start_times.append(csol[j,k]-duration[j,k,i])
            assignments.append(i)

    return m.status, m.objVal, m.objBound, m.Runtime, start_times, assignments, resources, history

def run_cplex_lp(path):
    history = [(0, float('inf'), -float('inf'))]
    resources = [(0,0)]
    class SolutionPrinter(ProgressListener):
    
        def __init__(self):
            ProgressListener.__init__(self, ProgressClock.Objective)
            
        def notify_progress(self, pdata):
            cpu, ram = get_cpu_ram_stats()
            resources.append((cpu, ram))
            #Called at each new solution (better objective).
            objective = round(pdata.current_objective)
            bnd = round(pdata.best_bound)
            time = pdata.time
            #if objective < history[-1][1] or bnd > history[-1][2]:
            history.append((time, objective, bnd))
                

    f = open(path)

    lines = f.readlines()
    first_line = lines[0].split()
    nb_jobs = int(first_line[0])
    nb_machines = int(first_line[1])
    nb_operations = [int(lines[j + 1].split()[0]) for j in range(nb_jobs)]
    INFINITE = 1000000
    nb_tasks = sum(nb_operations[j] for j in range(nb_jobs))

    task_processing_time = [[[INFINITE for m in range(nb_machines)] for o in range(nb_operations[j])] for j in range(nb_jobs)]

    duration = {}
    job_op_suitable = {}
    for j in range(nb_jobs):
        line = lines[j + 1].split()
        tmp = 0
        for o in range(nb_operations[j]):
            nb_machines_operation = int(line[tmp + o + 1])
            suitable_helper =[]
            for i in range(nb_machines_operation):
                machine = int(line[tmp + o + 2 * i + 2]) - 1
                time = int(line[tmp + o + 2 * i + 3])
                task_processing_time[j][o][machine] = time
                suitable_helper += [machine+1]
                duration[j+1,o+1,machine+1] = time
                
            job_op_suitable[j+1,o+1] = suitable_helper
            tmp = tmp + 2 * nb_machines_operation

    L=0
    for j in range(nb_jobs):
        for o in range(nb_operations[j]):
            L += max(task_processing_time[j][o][m] for m in range(nb_machines) if task_processing_time[j][o][m] != INFINITE)

    mdl = Model('FJSP MILP Cplex')

    jobs = [j for j in range(1,nb_jobs+1)]
    job_ops = [(j+1,k+1) for j in range(nb_jobs) for k in range(nb_operations[j])] 
    machines = [m for m in range(1,nb_machines+1)]
    list_X_var = []
    for j, k in job_ops :
        if j < nb_jobs :
            for jp, kp in job_ops:
                if jp > j:
                    list_X_var.append((j,k,jp,kp))

    list_Y_var = []
    for j, o in job_ops :
        for m in job_op_suitable[j,o] :
            list_Y_var.append((j,o,m))

    Y = mdl.binary_var_dict(list_Y_var, name=lambda y: 'Y_%s_%s_%s' % y)
    mdl.Y = Y
    X = mdl.binary_var_dict(list_X_var, name=lambda x: 'X_%s_%s_%s_%s' % x)
    mdl.X = X
    C = mdl.continuous_var_dict(job_ops, lb = 0, ub = L, name=lambda c: 'C_%s_%s' % c)
    mdl.C = C
    Cmax = mdl.continuous_var(lb = 0, ub = L, name = "Cmax")
    mdl.Cmax = Cmax

    mdl.add_constraints((mdl.sum(mdl.Y[j,o,m] for m in job_op_suitable[j,o]) == 1, 'Y_const__%s_%s' %(j,o)) for j, o in job_ops)

    mdl.add_constraints((mdl.sum(mdl.Y[j,o,m] * duration[j,o,m] for m in job_op_suitable[j,o]) <= mdl.C[j,o], 'C_time_%s_%s' %(j,o))  
                        for j, o in job_ops 
                        if o == 1)

    mdl.add_constraints((mdl.sum(mdl.Y[j,o,m] * duration[j,o,m] for m in job_op_suitable[j,o]) + mdl.C[j,o-1] <= mdl.C[j,o], 'C_time_%s_%s' %(j,o)) 
                        for j, o in job_ops 
                        if o != 1)

    mdl.add_constraints((mdl.C[j,o] >= mdl.C[jp,op] + duration[j,o,m] - L*(3 - mdl.X[j,o,jp,op] - mdl.Y[j,o,m] - mdl.Y[jp,op,m]), 'NO1_%s_%s_%s_%s_%s' %(j,o,jp,op,m)) 
                for j, o in job_ops if j < nb_jobs
                for jp, op in job_ops if jp > j 
                for m in machines if m in job_op_suitable[j,o] if m in job_op_suitable[jp,op])

    mdl.add_constraints((mdl.C[jp,op] >= mdl.C[j,o] + duration[jp,op,m] - L*(mdl.X[j,o,jp,op] + 2 - mdl.Y[j,o,m] - mdl.Y[jp,op,m]), 'NO2_%s_%s_%s_%s_%s' %(j,o,jp,op,m)) 
                for j, o in job_ops if j < nb_jobs
                for jp, op in job_ops if jp > j 
                for m in machines if m in job_op_suitable[j,o] if m in job_op_suitable[jp,op])

    mdl.add_constraints((mdl.Cmax >= mdl.C[j,nb_operations[j-1]] for j in jobs),"Cmax")
    mdl.minimize(mdl.Cmax)

    mdl.parameters.timelimit = TIME_LIMIT_IN_SECONDS
    mdl.add_progress_listener(SolutionPrinter())
    res = mdl.solve()

    xsol = res.get_value_dict(X)
    csol = res.get_value_dict(C)
    start_times = []
    assignments = []
    ysol={}
    for j, k, i in list_Y_var:
        ysol[j,k,i] = res.get_value(Y[j,k,i])
        if ysol[j,k,i] > 0:
            start_times.append(round(csol[j,k]-duration[j,k,i]))
            assignments.append(round(csol[j,k]))

    mdl.end()

    return res.solve_status, res.solution.objective_values[0], res.solution.objective_bounds[0], res.get_solve_time(), start_times, assignments, resources, history

def run_cplex_cp(path):
    history = [(0, float('inf'), -float('inf'))]
    resources = [(0,0)]

    class SolutionPrinter(CpoSolverListener):
        
        def __init__(self):
            pass

        def new_result(self, solver, msol):
            cpu, ram = get_cpu_ram_stats()
            resources.append((cpu, ram))
            if msol:
                time = msol.get_solve_time()
                obj = msol.get_objective_value()
                bnd = msol.get_objective_bound()
                #if obj < history[-1][1] or bnd > history[-1][2]:
                history.append((time, obj, bnd))
                    
    f = open(path)

    lines = f.readlines()
    first_line = lines[0].split()

    nb_jobs = int(first_line[0])
    nb_machines = int(first_line[1])
    nb_operations = [int(lines[j + 1].split()[0]) for j in range(nb_jobs)]
    INFINITE = 1000000

    JOBS =  [[[(INFINITE,INFINITE) for m in range(nb_machines)] for o in range(nb_operations[j])] for j in range(nb_jobs)]

    for j in range(nb_jobs):
        line = lines[j + 1].split()
        tmp = 0
        for o in range(nb_operations[j]):
            nb_machines_operation = int(line[tmp + o + 1])
            machine_helper =[]
            for i in range(nb_machines_operation):
                machine = int(line[tmp + o + 2 * i + 2]) - 1
                time = int(line[tmp + o + 2 * i + 3])
                machine_helper += [(machine,time)]
            JOBS[j][o] = machine_helper
            tmp = tmp + 2 * nb_machines_operation
    mdl = CpoModel()
    ops  = { (j,o) : interval_var(name='J{}_O{}'.format(j,o))
            for j,J in enumerate(JOBS) for o,O in enumerate(J)}
    mops = { (j,o,k,m) : interval_var(name='J{}_O{}_C{}_M{}'.format(j,o,k,m), optional=True, size=d)
            for j,J in enumerate(JOBS) for o,O in enumerate(J) for k, (m, d) in enumerate(O)}
    mdl.add(end_before_start(ops[j,o-1], ops[j,o]) for j,o in ops if 0<o)
    mdl.add(alternative(ops[j,o], [mops[a] for a in mops if a[0:2]==(j,o)]) for j,o in ops)
    mdl.add(no_overlap(mops[a] for a in mops if a[3]==m) for m in range(nb_machines))
    mdl.add(minimize(max(end_of(ops[j,o]) for j,o in ops)))

    context.solver.solve_with_search_next = True
    mdl.add_solver_listener(SolutionPrinter())

    res = mdl.solve(execfile=r"C:\Program Files\IBM\ILOG\CPLEX_Studio2211\cpoptimizer\bin\x64_win64\cpoptimizer.exe", TimeLimit = TIME_LIMIT_IN_SECONDS, LogVerbosity = 'Quiet')
    start_times = []
    assignments = []
    for a in mops:
        itv = res.get_var_solution(mops[a])
        for m in range(nb_machines):
            if a[3]==m and itv.is_present():
                start_times.append(itv.start)
                assignments.append(a[3])

    return res.solve_status, res.solution.objective_values[0], res.solution.objective_bounds[0], res.get_solve_time(), start_times, assignments, resources, history

def run_ortools(path):
    history = [(0, float('inf'), -float('inf'))]
    resources = [(0,0)]

    class SolutionPrinter(cp_model.CpSolverSolutionCallback):

        def __init__(self):
            cp_model.CpSolverSolutionCallback.__init__(self)

        def on_solution_callback(self):
            cpu, ram = get_cpu_ram_stats()
            resources.append((cpu, ram))
            if round(self.objective_value) < history[-1][1] or round(self.best_objective_bound) > history[-1][2]:
                history.append((self.wall_time, self.objective_value, self.best_objective_bound))

    f = open(path)
    lines = f.readlines()
    first_line = lines[0].split()
    nb_jobs = int(first_line[0])
    nb_machines = int(first_line[1])
    nb_operations = [int(lines[j + 1].split()[0]) for j in range(nb_jobs)]
    INFINITE = 1000000
    task_processing_time = [[[INFINITE for m in range(nb_machines)] for o in range(nb_operations[j])] for j in range(nb_jobs)]
    
    jobs =  [[[(INFINITE,INFINITE) for m in range(nb_machines)] for o in range(nb_operations[j])] for j in range(nb_jobs)]

    for j in range(nb_jobs):
        line = lines[j + 1].split()
        tmp = 0
        for o in range(nb_operations[j]):
            nb_machines_operation = int(line[tmp + o + 1])
            machine_helper =[]
            for i in range(nb_machines_operation):
                machine = int(line[tmp + o + 2 * i + 2]) - 1
                time = int(line[tmp + o + 2 * i + 3])
                machine_helper += [(time,machine)]
                task_processing_time[j][o][machine] = time
            jobs[j][o] = machine_helper
            tmp = tmp + 2 * nb_machines_operation
    L=0
    for j in range(nb_jobs):
        for o in range(nb_operations[j]):
            L += max(task_processing_time[j][o][m] for m in range(nb_machines) if task_processing_time[j][o][m] != INFINITE)
           
    num_jobs = len(jobs)
    all_jobs = range(num_jobs)

    num_machines = nb_machines
    all_machines = range(num_machines)
    model = cp_model.CpModel()

    horizon = L
    intervals_per_resources = collections.defaultdict(list)
    starts = {}
    presences = {}
    job_ends = []
    for job_id in all_jobs:
        job = jobs[job_id]
        num_tasks = len(job)
        previous_end = None
        for task_id in range(num_tasks):
            task = job[task_id]

            min_duration = task[0][0]
            max_duration = task[0][0]

            num_alternatives = len(task)
            all_alternatives = range(num_alternatives)

            for alt_id in range(1, num_alternatives):
                alt_duration = task[alt_id][0]
                min_duration = min(min_duration, alt_duration)
                max_duration = max(max_duration, alt_duration)

            suffix_name = "_j%i_t%i" % (job_id, task_id)
            start = model.new_int_var(0, horizon, "start" + suffix_name)
            duration = model.new_int_var(
                min_duration, max_duration, "duration" + suffix_name
            )
            end = model.new_int_var(0, horizon, "end" + suffix_name)
            interval = model.new_interval_var(
                start, duration, end, "interval" + suffix_name
            )

            starts[(job_id, task_id)] = start

            if previous_end is not None:
                model.add(start >= previous_end)
            previous_end = end

            if num_alternatives > 1:
                l_presences = []
                for alt_id in all_alternatives:
                    alt_suffix = "_j%i_t%i_a%i" % (job_id, task_id, alt_id)
                    l_presence = model.new_bool_var("presence" + alt_suffix)
                    l_start = model.new_int_var(0, horizon, "start" + alt_suffix)
                    l_duration = task[alt_id][0]
                    l_end = model.new_int_var(0, horizon, "end" + alt_suffix)
                    l_interval = model.new_optional_interval_var(
                        l_start, l_duration, l_end, l_presence, "interval" + alt_suffix
                    )
                    l_presences.append(l_presence)

                    model.add(start == l_start).only_enforce_if(l_presence)
                    model.add(duration == l_duration).only_enforce_if(l_presence)
                    model.add(end == l_end).only_enforce_if(l_presence)

                    intervals_per_resources[task[alt_id][1]].append(l_interval)

                    presences[(job_id, task_id, alt_id)] = l_presence

                model.add_exactly_one(l_presences)
            else:
                intervals_per_resources[task[0][1]].append(interval)
                presences[(job_id, task_id, 0)] = model.new_constant(1)

        job_ends.append(previous_end)

    for machine_id in all_machines:
        intervals = intervals_per_resources[machine_id]
        if len(intervals) > 1:
            model.add_no_overlap(intervals)

    makespan = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(makespan, job_ends)
    model.minimize(makespan)

    solver = cp_model.CpSolver()

    solver.parameters.max_time_in_seconds = TIME_LIMIT_IN_SECONDS
    
    #solution_printer = SolutionPrinter()

    #status = solver.solve(model, solution_printer)
    status = solver.solve(model)

    start_times = []
    assignments = []
    for job_id in all_jobs:
        for task_id in range(len(jobs[job_id])):
            start_times.append(solver.value(starts[(job_id, task_id)]))
            machine = -1
            for alt_id in range(len(jobs[job_id][task_id])):
                if solver.value(presences[(job_id, task_id, alt_id)]):
                    assignments.append(jobs[job_id][task_id][alt_id][1])

    lower_bound = solver.objective_value
    return solver.status_name(status), solver.objective_value, lower_bound, solver.wall_time, start_times, assignments, resources, history

def run_hexaly(path):
    history = []
    resources = [(0,0)]

    class SolutionListener:
        def __init__(self):
            history.append((0, float('inf'), -float('inf')))
        def my_callback(self, ls, cb_type):
            cpu, ram = get_cpu_ram_stats()
            resources.append((cpu, ram))
            time = ls.statistics.running_time
            obj = round(ls.model.objectives[0].value)
            bnd = round(ls.solution.get_objective_bound(0))
            if obj < history[-1][1] or bnd > history[-1][2]:
                # found better objective or better lower bound
                history.append((time, obj, bnd))

    status = -1
    fitness = -1
    lower_bound = -1
    runtime = -1
    f = open(path)

    lines = f.readlines()
    first_line = lines[0].split()
    nb_jobs = int(first_line[0])
    nb_machines = int(first_line[1])
    nb_operations = [int(lines[j + 1].split()[0]) for j in range(nb_jobs)]
    INFINITE = 1000000

    nb_tasks = sum(nb_operations[j] for j in range(nb_jobs))
    task_processing_time_data = [[INFINITE for m in range(nb_machines)] for i in range(nb_tasks)]
    job_operation_task = [[0 for o in range(nb_operations[j])] for j in range(nb_jobs)]
    
    id = 0
    for j in range(nb_jobs):
        line = lines[j + 1].split()
        tmp = 0
        for o in range(nb_operations[j]):
            nb_machines_operation = int(line[tmp + o + 1])
            for i in range(nb_machines_operation):
                machine = int(line[tmp + o + 2 * i + 2]) - 1
                time = int(line[tmp + o + 2 * i + 3])
                task_processing_time_data[id][machine] = time
            job_operation_task[j][o] = id
            id = id + 1
            tmp = tmp + 2 * nb_machines_operation

    L = sum(
        max(task_processing_time_data[i][m] for m in range(nb_machines) if task_processing_time_data[i][m] != INFINITE)
        for i in range(nb_tasks))

    with localsolver.LocalSolver() as ls:
        model = ls.model

        jobs_order = [model.list(nb_tasks) for _ in range(nb_machines)]
        machines = model.array(jobs_order)
        model.constraint(model.partition(machines))

        for i in range(nb_tasks):
            for m in range(nb_machines):
                if task_processing_time_data[i][m] == INFINITE:
                    model.constraint(model.not_(model.contains(jobs_order[m], i)))

        task_machine = [model.find(machines, i) for i in range(nb_tasks)]
        task_processing_time = model.array(task_processing_time_data)
        tasks = [model.interval(0, L) for _ in range(nb_tasks)]
        duration = [model.at(task_processing_time, i, task_machine[i]) for i in range(nb_tasks)]
        for i in range(nb_tasks):
            model.constraint(model.length(tasks[i]) == duration[i])
        task_array = model.array(tasks)

        for j in range(nb_jobs):
            for o in range(nb_operations[j] - 1):
                i1 = job_operation_task[j][o]
                i2 = job_operation_task[j][o + 1]
                model.constraint(tasks[i1] < tasks[i2])

        for m in range(nb_machines):
            sequence = jobs_order[m]
            sequence_lambda = model.lambda_function(
                lambda i: task_array[sequence[i]] < task_array[sequence[i + 1]])
            model.constraint(model.and_(model.range(0, model.count(sequence) - 1), sequence_lambda))

        makespan = model.max([model.end(tasks[i]) for i in range(nb_tasks)])
        model.minimize(makespan)
        
        model.close()

        ls.param.time_limit = TIME_LIMIT_IN_SECONDS
        ls.param.verbosity = 0
        
        #---------- ohne solution listener--------
        #ls.solve()

        #---------- mit solution listener--------
        ls.param.time_between_ticks = 1 # default 1sec INT!!
        cb = SolutionListener()
        ls.add_callback(localsolver.LSCallbackType.TIME_TICKED, cb.my_callback)
        ls.solve()
        #----------------------------------------

        start_times = []
        assignments = []
        for j in range(nb_jobs):
            for o in range(0, nb_operations[j]):
                taskIndex = job_operation_task[j][o]
                start_times.append(tasks[taskIndex].value.start())
                assignments.append(task_machine[taskIndex].value + 1)
        
        status = str(ls.solution.status)
        fitness = makespan.value
        lower_bound = ls.solution.get_objective_bound(0)
        runtime = ls.statistics.running_time

    lower_bound = solver.objective_value

    return status, fitness, lower_bound, runtime, start_times, assignments, resources, history

def write_output(message, path):
    with open(path, 'a') as f:
        f.write(f'{message}\n')

if __name__ == '__main__':
    shutdown_when_finished = True
    BENCHMARK_PATH = r'C:\Users\localadmin\Desktop\experiments\comparison\benchmarks_no_workers'
    OUTPUT_PATH = r'C:\Users\localadmin\Desktop\experiments\comparison\fjssp'
    # test fjssp first, then wfjssp
    #solvers = ['ortools','gurobi', 'cplex_lp', 'cplex_cp', 'hexaly']#'ortools',
    solvers = ['ortools', 'cplex_cp']
    #instances = [('0_BehnkeGeiger', 'Behnke60.fjs'), ('6_Fattahi', 'Fattahi20.fjs'), ('1_Brandimarte', 'BrandimarteMk11.fjs'), ('4_ChambersBarnes', 'ChambersBarnes10.fjs'), ('5_Kacem', 'Kacem3.fjs')]
    # NOTE: RAM and CPU stats are in percent
    """
     num = Value('d', 0.0)
    arr = Array('i', range(10))

    p = Process(target=f, args=(num, arr))
    p.start()
    p.join()

    print(num.value)
    print(arr[:])
    """
    instances = os.listdir(BENCHMARK_PATH)
    #for source in sources:
    #instances = os.listdir(BENCHMARK_PATH + '/' + source)
    for instance in instances:
        for solver in solvers:
            p = None
            status = None
            fitness = None
            lower_bound = None
            runtime = None
            start_times = None
            assignments = None
            resources = None
            history = None
            cpu = None
            ram = None
            run_monitor = None
            peak_ram = None
            peak_cpu = None
            message = None
            try:
                path = f'{BENCHMARK_PATH}/{instance}'
                print(f'Solving {instance} with {solver}...')
                #TODO: double check optimal/feasible status values for each solver
                message = ''
                if solver == 'gurobi':
                    cpu = Value('d', 0.0)
                    ram = Value('d', 0.0)
                    run_monitor = Value('i', 1)
                    p = Process(target=monitor_resources, args=(cpu, ram, 5, run_monitor))
                    p.start()
                    status, fitness, lower_bound, runtime, start_times, assignments, resources, history = run_gurobi(path)
                    run_monitor.value = 0
                    p.join()
                    peak_cpu = cpu.value
                    peak_ram = ram.value
                    message = f'{instance[:-4]};{1 if status == 2 else 0};{fitness};{lower_bound};{runtime};{start_times};{assignments};{peak_cpu};{peak_ram};{resources};{history}'
                elif solver == 'cplex_lp':
                    cpu = Value('d', 0.0)
                    ram = Value('d', 0.0)
                    run_monitor = Value('i', 1)
                    p = Process(target=monitor_resources, args=(cpu, ram, 5, run_monitor))
                    p.start()
                    status, fitness, lower_bound, runtime, start_times, assignments, resources, history = run_cplex_lp(path)
                    run_monitor.value = 0
                    p.join()
                    peak_cpu = cpu.value
                    peak_ram = ram.value
                    message = f'{instance[:-4]};{1 if status == "Optimal" else 0};{fitness};{lower_bound};{runtime};{start_times};{assignments};{peak_cpu};{peak_ram};{resources};{history}'
                elif solver == 'cplex_cp':
                    cpu = Value('d', 0.0)
                    ram = Value('d', 0.0)
                    run_monitor = Value('i', 1)
                    p = Process(target=monitor_resources, args=(cpu, ram, 5, run_monitor))
                    p.start()
                    status, fitness, lower_bound, runtime, start_times, assignments, resources, history = run_cplex_cp(path)
                    run_monitor.value = 0
                    p.join()
                    peak_cpu = cpu.value
                    peak_ram = ram.value
                    message = f'{instance[:-4]};{1 if status == "Optimal" else 0};{fitness};{lower_bound};{runtime};{start_times};{assignments};{peak_cpu};{peak_ram};{resources};{history}'
                elif solver == 'ortools':
                    cpu = Value('d', 0.0)
                    ram = Value('d', 0.0)
                    run_monitor = Value('i', 1)
                    p = Process(target=monitor_resources, args=(cpu, ram, 5, run_monitor))
                    p.start()
                    status, fitness, lower_bound, runtime, start_times, assignments, resources, history = run_ortools(path)
                    run_monitor.value = 0
                    p.join()
                    peak_cpu = cpu.value
                    peak_ram = ram.value
                    message = f'{instance[-4]};{1 if status == "OPTIMAL" else 0};{fitness};{lower_bound};{runtime};{start_times};{assignments};{peak_cpu};{peak_ram};{resources};{history}'
                else:
                    cpu = Value('d', 0.0)
                    ram = Value('d', 0.0)
                    run_monitor = Value('i', 1)
                    p = Process(target=monitor_resources, args=(cpu, ram, 5, run_monitor))
                    p.start()
                    status, fitness, lower_bound, runtime, start_times, assignments, resources, history = run_hexaly(path)
                    run_monitor.value = 0
                    p.join()
                    peak_cpu = cpu.value
                    peak_ram = ram.value
                    message = f'{instance[-4]};{1 if status == "LSSolutionStatus.OPTIMAL" else 0};{fitness};{lower_bound};{runtime};{start_times};{assignments};{peak_cpu};{peak_ram};{resources};{history}'
                write_output(message, f'{OUTPUT_PATH}/results_{solver}.txt')
            except:
                write_output(f'Error on instance {instance} using solver {solver}!', f'{OUTPUT_PATH}/results_{solver}.txt')
                p.kill()
            p.join()
            p.close()
            del p
            del status
            del fitness
            del lower_bound
            del runtime
            del start_times
            del assignments
            del resources
            del history
            del cpu
            del ram
            del run_monitor
            del peak_ram
            del peak_cpu
            del message
                
    if shutdown_when_finished:
        os.system("shutdown /s /t 1")
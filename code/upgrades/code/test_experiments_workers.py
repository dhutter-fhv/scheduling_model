import os
import psutil
from multiprocessing import Process, Value
from test_monitor import monitor_resources

# import gurobi stuff
import gurobipy as gp

# import cplex solver stuff
from docplex.cp.model import *
#import docplex.cp.utils_visu as visu
from docplex.cp.solver.solver_listener import *
from docplex.mp.model import Model
from docplex.mp.progress import ProgressListener, ProgressClock
import collections
from ortools.sat.python import cp_model

#import localsolver


TIME_LIMIT_IN_SECONDS = 300#1200
RANDOM_SEED = 1
CALLBACK = True

def get_cpu_ram_stats():
    return psutil.cpu_percent(), psutil.virtual_memory().percent

def write_output(message, path):
    with open(path, 'a') as f:
        f.write(f'{message}\n')

def run_gurobi(path):
    history = [(0, float('inf'), -float('inf'))]
    resources = [(0, 0)]

    def SolutionListener(model, where):
        cpu, ram = get_cpu_ram_stats()
        resources.append((cpu, ram))
        if where == gp.GRB.Callback.MIPSOL:
            time = model.cbGet(gp.GRB.Callback.RUNTIME)
            obj_best = model.cbGet(gp.GRB.Callback.MIPSOL_OBJBST)
            bnd = model.cbGet(gp.GRB.Callback.MIPSOL_OBJBND)
            #if obj_best < history[-1][1] or bnd > history[-1][2]:
            history.append((time, int(float(obj_best)+0.5), float(bnd)))

    f = open(path)
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

    task_processing_time = [[[[INFINITE for s in range(nb_workers)] 
                                        for m in range(nb_machines)] 
                                        for o in range(nb_operations[j])] 
                                        for j in range(nb_jobs)]

    job_op_dur_helper = {}
    job_op_machsuitable = {}
    job_op_mach_workersuitable = {}
    for j in range(nb_jobs):
        line = lines[j + 1].split()
        tmp_idx = 1
        for o in range(nb_operations[j]):
            nb_machines_operation = int(line[tmp_idx])
            tmp_idx += 1
            suitable_machine_helper = []
            for i in range(nb_machines_operation):
                machine = int(line[tmp_idx])
                suitable_machine_helper += [machine]
                nb_m_workers = int(line[tmp_idx + 1])
                tmp_idx += 2
                suitable_worker_helper = []
                for s in range(nb_m_workers):
                    worker = int(line[tmp_idx])
                    time = int(line[tmp_idx + 1])
                    tmp_idx += 2
                    task_processing_time[j][o][machine-1][worker-1] = time
                    suitable_worker_helper += [worker]
                    job_op_dur_helper[j+1,o+1,machine,worker] = time
                
                job_op_mach_workersuitable[j+1,o+1,machine] = suitable_worker_helper
            job_op_machsuitable[j+1,o+1] = suitable_machine_helper


    job_op_mach_worker, duration = gp.multidict(job_op_dur_helper)

    # Trivial upper bound for the completion times of the tasks
    L=0
    for j in range(nb_jobs):
        for o in range(nb_operations[j]):
            L += max(task_processing_time[j][o][m][s] for m in range(nb_machines) for s in range(nb_workers) if task_processing_time[j][o][m][s] != INFINITE )
            
        
    #initialize optimization    
    m = gp.Model('WFJSP MILP Gurobi')

    #list of jobs for creating Variables
    jobs = [j for j in range(1,nb_jobs+1)]

    #list of Job Operations for creating Variables
    job_ops = [(j+1,k+1) for j in range(nb_jobs) for k in range(nb_operations[j])] 

    #list of machines for creating Variables
    machines = [m for m in range(1,nb_machines+1)]

    #list of workers for creating Variables
    workers = [s for s in range(1,nb_workers+1)]

    #list for creating x Variables 
    list_X_var = []

    for j, k in job_ops :
        if j < nb_jobs :
            for jp, kp in job_ops:
                if jp > j:
                    list_X_var.append((j,k,jp,kp)) 
                    
    # Variables
    Y = m.addVars(job_op_mach_worker, obj = 0.0, vtype=gp.GRB.BINARY, name ="Y")

    X = m.addVars(list_X_var, obj = 0.0, vtype=gp.GRB.BINARY, name ="X")

    U = m.addVars(list_X_var, obj = 0.0, vtype=gp.GRB.BINARY, name ="U")

    C = m.addVars(job_ops,  obj = 0.0, lb = 0.0, vtype=gp.GRB.CONTINUOUS, name ="C")

    Cmax = m.addVar(obj = 1.0, name="Cmax")

    #Constraints
    m.addConstrs((Y.sum(j,k,'*','*') == 1 for j, k in job_ops), "Y_const")

    m.addConstrs((Y.prod(duration,j,k,'*','*') <= C[j,k] for j, k in job_ops if k == 1),"C_time")

    m.addConstrs((Y.prod(duration,j,k,'*','*') + C[j,k-1] <= C[j,k] for j, k in job_ops if k != 1), "C_time")

    m.addConstrs((C[j,k] >= C[jp,kp] + duration[j,k,i,s] - L*(3 - X[j,k,jp,kp] - Y[j,k,i,s] - Y[jp,kp,i,sp]) 
                for j, k in job_ops if j < nb_jobs
                for jp, kp in job_ops if jp > j 
                for i in machines if i in job_op_machsuitable[j,k] if i in job_op_machsuitable[jp,kp]
                for s in workers if s in job_op_mach_workersuitable[j,k,i]
                for sp in workers if sp in job_op_mach_workersuitable[jp,kp,i]) ,"l1_X")

    m.addConstrs((C[jp,kp] >= C[j,k] + duration[jp,kp,i,sp] - L*(X[j,k,jp,kp] + 2 - Y[j,k,i,s] - Y[jp,kp,i,sp]) 
                for j, k in job_ops if j < nb_jobs
                for jp, kp in job_ops if jp > j 
                for i in machines if i in job_op_machsuitable[j,k] if i in job_op_machsuitable[jp,kp]
                for s in job_op_mach_workersuitable[j,k,i]
                for sp in job_op_mach_workersuitable[jp,kp,i]), "l2_X")

    m.addConstrs((C[j,k] >= C[jp,kp] + duration[j,k,i,s] - L*(3 - U[j,k,jp,kp] - Y[j,k,i,s] - Y[jp,kp,ip,s]) 
                for j, k in job_ops if j < nb_jobs
                for jp, kp in job_ops if jp > j 
                for i in machines if i in job_op_machsuitable[j,k] 
                for ip in machines if ip in job_op_machsuitable[jp,kp]
                for s in workers if s in job_op_mach_workersuitable[j,k,i] if s in job_op_mach_workersuitable[jp,kp,ip]) ,"l1_U")

    m.addConstrs((C[jp,kp] >= C[j,k] + duration[jp,kp,ip,s] - L*(U[j,k,jp,kp] + 2 - Y[j,k,i,s] - Y[jp,kp,ip,s]) 
                for j, k in job_ops if j < nb_jobs
                for jp, kp in job_ops if jp > j 
                for i in machines if i in job_op_machsuitable[j,k] 
                for ip in machines if ip in job_op_machsuitable[jp,kp]
                for s in workers if s in job_op_mach_workersuitable[j,k,i] if s in job_op_mach_workersuitable[jp,kp,ip]), "l2_U")

    m.addConstrs((Cmax>=C[j,nb_operations[j-1]] for j in jobs),"Cmax")

    m.update()
    #m.display()
    m.Params.TimeLimit = TIME_LIMIT_IN_SECONDS
    m.Params.Seed = RANDOM_SEED
    m.Params.LogToConsole = 0
    # NOTE: FOR TESTING PURPOSES ONLY
    # TODO: REMOVE
    m.Params.Presolve = 0
    #---------- ohne solution listener--------
    #m.optimize()
    #---------- mit solution listener--------
    m._solution_count = 0
    # Bei Abbruch wenn known_best erreicht
    m._known_best = 0 # 884
    if CALLBACK:
        m.optimize(SolutionListener)
    else:
        m.optimize()
    #----------------------------------------

    start_times = []
    assignments = []
    workers = []
    if (m.status == 2 or m.status == 9) and m.SolCount > 0:
        #Output   
        xsol = m.getAttr('X', X)
        usol = m.getAttr('X', U)
        ysol = m.getAttr('X', Y)
        csol = m.getAttr('X', C)
        #counter = 0
        for j, k, i, s in job_op_mach_worker:
            if ysol[j,k,i,s] > 0:
                start_times.append(csol[j, k]-duration[j, k, i, s])
                assignments.append(i)
                workers.append(s)
    return m.status, m.objVal, m.objBound, m.Runtime, start_times, assignments, workers, resources, history

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
            objective = float(pdata.current_objective)
            bnd = float(pdata.best_bound)
            
            time = pdata.time
            #if objective < history[-1][1] or bnd > history[-1][2]:
            history.append((time, objective, bnd))
                

    f = open(path)
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

    task_processing_time = [[[[INFINITE for s in range(nb_workers)] 
                                        for m in range(nb_machines)] 
                                        for o in range(nb_operations[j])] 
                                        for j in range(nb_jobs)]

    duration = {}
    job_op_dur_helper = {}
    job_op_machsuitable = {}
    job_op_mach_workersuitable = {}
    for j in range(nb_jobs):
        line = lines[j + 1].split()
        tmp_idx = 1
        for o in range(nb_operations[j]):
            nb_machines_operation = int(line[tmp_idx])
            tmp_idx += 1
            suitable_machine_helper = []
            for i in range(nb_machines_operation):
                machine = int(line[tmp_idx])
                suitable_machine_helper += [machine]
                nb_m_workers = int(line[tmp_idx + 1])
                tmp_idx += 2
                suitable_worker_helper = []
                for s in range(nb_m_workers):
                    worker = int(line[tmp_idx])
                    time = int(line[tmp_idx + 1])
                    tmp_idx += 2
                    task_processing_time[j][o][machine-1][worker-1] = time
                    suitable_worker_helper += [worker]
                    duration[j+1,o+1,machine,worker] = time
                
                job_op_mach_workersuitable[j+1,o+1,machine] = suitable_worker_helper
            job_op_machsuitable[j+1,o+1] = suitable_machine_helper

    # Trivial upper bound for the completion times of the tasks
    L = 0
    for j in range(nb_jobs):
        for o in range(nb_operations[j]):
            L += max(task_processing_time[j][o][m][s] 
                        for m in range(nb_machines) 
                        for s in range(nb_workers) 
                        if task_processing_time[j][o][m][s] != INFINITE )

    #print("Horizon = %i" % L)

            
    #-----------------------------------------------------------------------------
    # Build the model
    #-----------------------------------------------------------------------------

    # Create model
    mdl = Model('WFJSP MILP Cplex')

    #list of jobs for creating Variables
    jobs = [j for j in range(1,nb_jobs+1)]

    #list of Job Operations for creating Variables
    job_ops = [(j+1,k+1) for j in range(nb_jobs) for k in range(nb_operations[j])] 

    #list of machines for creating Variables
    machines = [m for m in range(1,nb_machines+1)]

    #list of workers for creating Variables
    workers = [s for s in range(1,nb_workers+1)]

    #list for creating x Variables 
    list_X_var = []
    for j, k in job_ops :
        if j < nb_jobs :
            for jp, kp in job_ops:
                if jp > j:
                    list_X_var.append((j,k,jp,kp)) 
                    
    #list for creating Y Variables list_Y_var=[(0,0,0)]
    list_Y_var = []
    for j, o in job_ops :
        for m in job_op_machsuitable[j,o] :
            for w in job_op_mach_workersuitable[j,o,m]:
                list_Y_var.append((j,o,m,w))
    
    # Variables
    Y = mdl.binary_var_dict(list_Y_var, name=lambda y: 'Y_%s_%s_%s_%s' % y)
    mdl.Y = Y
    X = mdl.binary_var_dict(list_X_var, name=lambda x: 'X_%s_%s_%s_%s' % x)
    mdl.X = X
    U = mdl.binary_var_dict(list_X_var, name=lambda x: 'U_%s_%s_%s_%s' % x)
    mdl.U = U
    C = mdl.continuous_var_dict(job_ops, lb = 0, ub = L, name=lambda c: 'C_%s_%s' % c)
    mdl.C = C
    Cmax = mdl.continuous_var(lb = 0, ub = L, name = "Cmax")
    mdl.Cmax = Cmax
    
    #Constraints
    mdl.add_constraints((mdl.sum(mdl.Y[j,o,m,w] 
                                for m in job_op_machsuitable[j,o]
                                for w in job_op_mach_workersuitable[j,o,m]) == 1, 'Y_const__%s_%s' %(j,o))
                        for j, o in job_ops)

    mdl.add_constraints((mdl.sum(mdl.Y[j,o,m,w] * duration[j,o,m,w] 
                                for m in job_op_machsuitable[j,o]
                                for w in job_op_mach_workersuitable[j,o,m]) <= mdl.C[j,o], 'C_time_%s_%s' %(j,o))  
                        for j, o in job_ops 
                        if o == 1)

    mdl.add_constraints((mdl.sum(mdl.Y[j,o,m,w] * duration[j,o,m,w] 
                                for m in job_op_machsuitable[j,o]
                                for w in job_op_mach_workersuitable[j,o,m]) 
                        + mdl.C[j,o-1] <= mdl.C[j,o], 'C_time_%s_%s' %(j,o)) 
                        for j, o in job_ops 
                        if o != 1)

    mdl.add_constraints((mdl.C[j,o] >= mdl.C[jp,op] + duration[j,o,m,w] 
                        - L*(3 - mdl.X[j,o,jp,op] - mdl.Y[j,o,m,w] - mdl.Y[jp,op,m,wp]), 'NO_X_1_%s_%s_%s_%s_%s_%s_%s' %(j,o,jp,op,m,w,wp)) 
                    for j, o in job_ops if j < nb_jobs
                    for jp, op in job_ops if jp > j 
                    for m in machines if m in job_op_machsuitable[j,o] if m in job_op_machsuitable[jp,op]
                    for w in workers if w in job_op_mach_workersuitable[j,o,m]
                    for wp in workers if wp in job_op_mach_workersuitable[jp,op,m])

    mdl.add_constraints((mdl.C[jp,op] >= mdl.C[j,o] + duration[jp,op,m,wp] 
                        - L*(mdl.X[j,o,jp,op] + 2 - mdl.Y[j,o,m,w] - mdl.Y[jp,op,m,wp]), 'NO_X_2_%s_%s_%s_%s_%s_%s_%s' %(j,o,jp,op,m,w,wp)) 
                    for j, o in job_ops if j < nb_jobs
                    for jp, op in job_ops if jp > j 
                    for m in machines if m in job_op_machsuitable[j,o] if m in job_op_machsuitable[jp,op]
                    for w in workers if w in job_op_mach_workersuitable[j,o,m]
                    for wp in workers if wp in job_op_mach_workersuitable[jp,op,m])

    mdl.add_constraints((mdl.C[j,o] >= mdl.C[jp,op] + duration[j,o,m,w] 
                        - L*(3 - mdl.U[j,o,jp,op] - mdl.Y[j,o,m,w] - mdl.Y[jp,op,mp,w]), 'NO_U_1_%s_%s_%s_%s_%s_%s_%s' %(j,o,jp,op,m,mp,w)) 
                    for j, o in job_ops if j < nb_jobs
                    for jp, op in job_ops if jp > j 
                    for m in machines if m in job_op_machsuitable[j,o] 
                    for mp in machines if mp in job_op_machsuitable[jp,op]
                    for w in workers if w in job_op_mach_workersuitable[j,o,m] if w in job_op_mach_workersuitable[jp,op,mp])

    mdl.add_constraints((mdl.C[jp,op] >= mdl.C[j,o] + duration[jp,op,mp,w] 
                        - L*(mdl.U[j,o,jp,op] + 2 - mdl.Y[j,o,m,w] - mdl.Y[jp,op,mp,w]), 'NO_U_2_%s_%s_%s_%s_%s_%s_%s' %(j,o,jp,op,m,mp,w)) 
                    for j, o in job_ops if j < nb_jobs
                    for jp, op in job_ops if jp > j 
                    for m in machines if m in job_op_machsuitable[j,o] 
                    for mp in machines if mp in job_op_machsuitable[jp,op]
                    for w in workers if w in job_op_mach_workersuitable[j,o,m] if w in job_op_mach_workersuitable[jp,op,mp])


    mdl.add_constraints((mdl.Cmax >= mdl.C[j,nb_operations[j-1]] for j in jobs),"Cmax")

    mdl.minimize(mdl.Cmax)

    #Print model information
    #mdl.print_information()

    #-----------------------------------------------------------------------------
    # Solve the model and display the result
    #-----------------------------------------------------------------------------

    # Solve model
    
    mdl.parameters.timelimit = TIME_LIMIT_IN_SECONDS
    mdl.parameters.randomseed = RANDOM_SEED
    #mdl.parameters.mip.strategy.variableselect = 3 # TODO: double check
    if CALLBACK:
        mdl.add_progress_listener(SolutionPrinter())
    #mdl.set_log_stream(None)
    #mdl.set_error_stream(None)
    #mdl.set_warning_stream(None)
    #mdl.set_results_stream(None)
    #mdl.log_output = True
    #C:\Program Files\IBM\ILOG\CPLEX_Studio2211\cpoptimizer\bin\x64_win64\cpoptimizer.exe
    res = mdl.solve(execfile = r"C:\Program Files\IBM\ILOG\CPLEX_Studio2211\cplex\bin\x64_win64\cplex.exe")
    #res = mdl.solve()
    #res = mdl.solve()
    if res:
        xsol = res.get_value_dict(X)
        #ysol = res.get_value_dict(Y) #Bug in res.get_value_dict: wenn Y[i,j,m] negativ ist
        csol = res.get_value_dict(C)

        #Output
        ysol = {}
        start_times = []
        assignments = []
        workers = []
        for j, k, i, s in list_Y_var:
            ysol[j,k,i,s] = res.get_value(Y[j,k,i,s])
            if ysol[j,k,i,s] > 0:
                start_times.append(round(csol[j,k]-duration[j,k,i,s]))
                assignments.append(i)
                workers.append(s)
        #print(res)
        obj_value = res.get_objective_value()#solution.objective_values[0]
        bounds = res.solve_details.best_bound#objective_bounds[0]
        mdl.end()
        return res.solve_status, obj_value, bounds, res.solve_details.time, start_times, assignments, workers, resources, history
    else:
        sdetails = mdl.solve_details
        mdl.end()
        return "INFEASIBLE", float('inf'), sdetails.best_bound, sdetails.time, [], [], [], resources, history

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
                if obj < history[-1][1] or bnd > history[-1][2]:
                    history.append((time, obj, bnd))
    f = open(path)
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

    task_processing_time = [[[[INFINITE for s in range(nb_workers)] 
                                        for m in range(nb_machines)] 
                                        for o in range(nb_operations[j])] 
                                        for j in range(nb_jobs)]

    jobs =  [[[INFINITE] for o in range(nb_operations[j])] for j in range(nb_jobs)]


    for j in range(nb_jobs):
        line = lines[j + 1].split()
        tmp_idx = 1
        for o in range(nb_operations[j]):
            nb_machines_operation = int(line[tmp_idx])
            tmp_idx += 1
            m_w_helper=[]
            for i in range(nb_machines_operation):
                machine = int(line[tmp_idx])-1
                nb_m_workers = int(line[tmp_idx + 1])
                tmp_idx += 2
                for s in range(nb_m_workers):
                    worker = int(line[tmp_idx])-1
                    time = int(line[tmp_idx + 1])
                    tmp_idx += 2
                    task_processing_time[j][o][machine][worker] = time
                    m_w_helper += [(time,machine,worker)]
                            
            jobs[j][o] = m_w_helper

    # Trivial upper bound for the completion times of the tasks
    horizon = 0
    for j in range(nb_jobs):
        for o in range(nb_operations[j]):
            horizon += max(task_processing_time[j][o][m][s] 
                        for m in range(nb_machines) 
                        for s in range(nb_workers) 
                        if task_processing_time[j][o][m][s] != INFINITE )

    #print("Horizon = %i" % horizon)

            
    #-----------------------------------------------------------------------------
    # Build the model
    #-----------------------------------------------------------------------------

    # Create model
    mdl = CpoModel()

    # Following code creates:
    # - creates one interval variable 'ops' for each possible operation choice
    # - creates one interval variable mops' for each operation, as an alternative of all operation choices
    # - setup precedence constraints between operations of each job
    # - creates a no_overlap constraint an the operations of each machine

    ops  = { (j,o) : interval_var(name='J{}_O{}'.format(j,o))
            for j,J in enumerate(jobs) for o,O in enumerate(J)}
    #mops = { (j,o,k,m,s) : interval_var(name='J{}_O{}_C{}_M{}_W{}'.format(j,o,k,m,s), optional=True, size=d)
    #         for j,J in enumerate(jobs) for o,O in enumerate(J) for k, (d, m, s) in enumerate(O)}
    mops = { (j,o,m,s) : interval_var(name='J{}_O{}_M{}_W{}'.format(j,o,m,s), optional=True, size=d)
            for j,J in enumerate(jobs) for o,O in enumerate(J) for k, (d, m, s) in enumerate(O)}
    # Precedence constraints between operations of a job
    mdl.add(end_before_start(ops[j,o-1], ops[j,o]) for j,o in ops if 0<o)

    # Alternative constraints
    mdl.add(alternative(ops[j,o], [mops[a] for a in mops if a[0:2]==(j,o)]) for j,o in ops)

    # Add no_overlap constraint between operations executed on the same machine
    for m in range(nb_machines):
        no_overlap_list = []
        for a in mops:
            if a[2] == m:
                no_overlap_list.append(mops[a])
        if len(no_overlap_list) > 0:
            mdl.add(no_overlap(no_overlap_list))
    #mdl.add(no_overlap(mops[a] for a in mops if a[2]==m) for m in range(nb_machines))

    # Add no_overlap constraint between operations executed by the same worker
    for s in range(nb_workers):
        no_overlap_list = []
        for a in mops:
            if a[3] == s:
                no_overlap_list.append(mops[a])
        if len(no_overlap_list) > 0:
            mdl.add(no_overlap(no_overlap_list))
    #mdl.add(no_overlap(mops[a] for a in mops if a[3]==s) for s in range(nb_workers))

    # Minimize termination date
    mdl.add(minimize(max(end_of(ops[j,o]) for j,o in ops)))


    #-----------------------------------------------------------------------------
    # Solve the model and display the result
    #-----------------------------------------------------------------------------

    #---------- mit solution listener----------------
    context.solver.solve_with_search_next = True
    if CALLBACK:
        mdl.add_solver_listener(SolutionPrinter())
    #------------------------------------------------

    # Solve model
    #print('Solving model...')
    timelimit = TIME_LIMIT_IN_SECONDS

    #---------- ohne solution listener--------
    #res = mdl.solve(FailLimit=1000000,TimeLimit=10)
    res = mdl.solve(execfile=r"C:\Program Files\IBM\ILOG\CPLEX_Studio2211\cpoptimizer\bin\x64_win64\cpoptimizer.exe", TimeLimit = TIME_LIMIT_IN_SECONDS, RandomSeed=RANDOM_SEED, LogVerbosity = 'Quiet')
    #print('Solution:')
    #res.print_solution()
    start_times = []
    assignments = []
    workers = []
    for a in mops:
        itv = res.get_var_solution(mops[a])
        for m in range(nb_machines):
            if a[2]==m and itv.is_present():
                #print('Job %i Operation %i on Mashine %i by Worker %i starts at %i ends at %i (duration %i)' %(a[0],a[1],a[2],a[3],itv.start,itv.end,itv.size))
                start_times.append(itv.start)
                assignments.append(a[2])
                workers.append(a[3])
    #NOTE: status codes camel case
    return res.solve_status, res.solution.objective_values[0], res.solution.objective_bounds[0], res.get_solve_time(), start_times, assignments, workers, resources, history

def run_ortools(path):
    history = [(0, float('inf'), -float('inf'))]
    resources = [(0,0)]

    class SolutionPrinter(cp_model.CpSolverSolutionCallback):

        def __init__(self):
            cp_model.CpSolverSolutionCallback.__init__(self)

        def on_solution_callback(self):
            cpu, ram = get_cpu_ram_stats()
            resources.append((cpu, ram))
            #if round(self.objective_value) < history[-1][1] or round(self.best_objective_bound) > history[-1][2]:
            history.append((self.wall_time, self.objective_value, self.best_objective_bound))

    f = open(path)
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

    task_processing_time = [[[[INFINITE for s in range(nb_workers)] 
                                        for m in range(nb_machines)] 
                                        for o in range(nb_operations[j])] 
                                        for j in range(nb_jobs)]

    jobs =  [[[INFINITE] for o in range(nb_operations[j])] for j in range(nb_jobs)]


    for j in range(nb_jobs):
        line = lines[j + 1].split()
        tmp_idx = 1
        for o in range(nb_operations[j]):
            nb_machines_operation = int(line[tmp_idx])
            tmp_idx += 1
            m_w_helper=[]
            for i in range(nb_machines_operation):
                machine = int(line[tmp_idx])-1
                nb_m_workers = int(line[tmp_idx + 1])
                tmp_idx += 2
            
                for s in range(nb_m_workers):
                    worker = int(line[tmp_idx])-1
                    time = int(line[tmp_idx + 1])
                    tmp_idx += 2
                    task_processing_time[j][o][machine][worker] = time
                    m_w_helper += [(time,machine,worker)]
                            
            jobs[j][o] = m_w_helper

    # Trivial upper bound for the completion times of the tasks
    horizon = 0
    for j in range(nb_jobs):
        for o in range(nb_operations[j]):
            horizon += max(task_processing_time[j][o][m][s] for m in range(nb_machines) for s in range(nb_workers) if task_processing_time[j][o][m][s] != INFINITE )

    #print("Horizon = %i" % horizon)

    all_jobs = range(nb_jobs)
    all_machines = range(nb_machines)
    all_workers = range(nb_workers)

    #print("Creating Variables")
    # Global storage of variables.
    intervals_per_machine = collections.defaultdict(list)
    intervals_per_worker = collections.defaultdict(list)

    starts = {}  # indexed by (job_id, task_id).
    presences = {}  # indexed by (job_id, task_id, alt_id).
    job_ends = [] 

    # Model the flexible jobshop problem with worker constraint.
    model = cp_model.CpModel()

    # Scan the jobs and create the relevant variables and intervals.
    for job_id in all_jobs:
        job = jobs[job_id]
        num_tasks = len(job)
        previous_end = None
        for task_id in range(num_tasks):
            task = job[task_id]
            
            #temporerary
            min_duration = task[0][0]
            max_duration = task[0][0]

            num_alternatives = len(task)
            all_alternatives = range(num_alternatives)

            for alt_id in range(1, num_alternatives):
                alt_duration = task[alt_id][0]
                min_duration = min(min_duration, alt_duration)
                max_duration = max(max_duration, alt_duration)

            # Create main interval for the task.
            suffix_name = "_j%i_t%i" % (job_id, task_id)
            start = model.new_int_var(0, horizon, "start" + suffix_name)
            duration = model.new_int_var(
                min_duration, max_duration, "duration" + suffix_name
            )
            end = model.new_int_var(0, horizon, "end" + suffix_name)
            interval = model.new_interval_var(
                start, duration, end, "interval" + suffix_name
            )

            # Store the start for the solution.
            starts[(job_id, task_id)] = start

            # Add precedence with previous task in the same job.
            if previous_end is not None:
                model.add(start >= previous_end)
            previous_end = end

            # Create alternative intervals.
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

                    # Link the primary/global variables with the local ones.
                    model.add(start == l_start).only_enforce_if(l_presence)
                    model.add(duration == l_duration).only_enforce_if(l_presence)
                    model.add(end == l_end).only_enforce_if(l_presence)

                    # Add the local interval to the right machine.
                    intervals_per_machine[task[alt_id][1]].append(l_interval)
                    
                    # Add the local interval to the right machine.
                    intervals_per_worker[task[alt_id][2]].append(l_interval)

                    # Store the presences for the solution.
                    presences[(job_id, task_id, alt_id)] = l_presence

                # Select exactly one presence variable.
                model.add_exactly_one(l_presences)
            else:
                intervals_per_machine[task[0][1]].append(interval)
                intervals_per_worker[task[0][2]].append(interval)
                presences[(job_id, task_id, 0)] = model.new_constant(1)

        job_ends.append(previous_end)
    #print("Creating Constraints")
    # Create machines constraints.
    for machine_id in all_machines:
        intervals = intervals_per_machine[machine_id]
        if len(intervals) > 1:
            model.add_no_overlap(intervals)
            
    # Create worker constraints.
    for worker_id in all_workers:
        intervals = intervals_per_worker[worker_id]
        if len(intervals) > 1:
            model.add_no_overlap(intervals)
    #print("Setting Objective")
    # Makespan objective.
    makespan = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(makespan, job_ends)
    model.minimize(makespan)
    #print("Running the model")
    # Solve model.
    solver = cp_model.CpSolver()
    # Sets a time limit in seconds.
    solver.parameters.max_time_in_seconds = TIME_LIMIT_IN_SECONDS
    solver.parameters.random_seed = RANDOM_SEED
    #Meldung bei jeder neuen Lösung 
    solution_printer = SolutionPrinter()
    if CALLBACK:
        status = solver.solve(model, solution_printer)
    else:
        status = solver.solve(model)   
    #print("Finished Solving the problem")
    #Ohne Meldung bei jeder neuen Lösung
    #status = solver.solve(model)

    start_times = []
    assignments = []
    workers = []
    if solver.status_name(status) == 'OPTIMAL' or solver.status_name(status) == 'FEASIBLE':
        # Print final solution.
        #print(solver.status_name(status))
        for job_id in all_jobs:
            #print("Job %i:" % job_id)
            for task_id in range(len(jobs[job_id])):
                #print(len(starts))
                start_value = solver.value(starts[(job_id, task_id)])
                machine = -1
                worker = -1
                duration = -1
                selected = -1
                for alt_id in range(len(jobs[job_id][task_id])):
                    if solver.value(presences[(job_id, task_id, alt_id)]):
                        duration = jobs[job_id][task_id][alt_id][0]
                        machine = jobs[job_id][task_id][alt_id][1]
                        worker = jobs[job_id][task_id][alt_id][2]
                        selected = alt_id
                start_times.append(start_value)
                assignments.append(machine)
                workers.append(worker)
                """print(
                    "  task_%i_%i starts at %i ends at %i (alt %i, machine %i, worker %i, duration %i)"
                    % (job_id, task_id, start_value,start_value+duration, selected, machine, worker, duration)
                )"""
        lower_bound = solver.best_objective_bound

    return solver.status_name(status), solver.objective_value, lower_bound, solver.wall_time, start_times, assignments, workers, resources, history

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
            obj = ls.model.objectives[0].value
            bnd = ls.solution.get_objective_bound(0)
            #if obj != history[-1][1] or bnd != history[-1][2]:#.compare(history[-1][1]) < 0 or bnd.compare(history[-1][2]) < 0:# != history[-1][1] or bnd != history[-1][2]:
                # found better objective or better lower bound
            #obj_out = None
            #obj.pretty_print(out=obj_out)
            #bnd_out = None
            #bnd.pretty_print(out=bnd_out)
            history.append((time, obj, bnd))

    status = -1
    fitness = -1
    lower_bound = -1
    runtime = -1
    f = open(path)
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
        ls.param.time_limit = TIME_LIMIT_IN_SECONDS
        ls.param.verbosity = 0 #1 defaul 0 quiet 2 detailed
        ls.param.seed = RANDOM_SEED
        
        #---------- ohne solution listener--------
        #ls.solve()

        #---------- mit solution listener--------
        ls.param.time_between_ticks = 1 # default 1sec INT!!
        cb = SolutionListener()
        if CALLBACK:
            ls.add_callback(localsolver.LSCallbackType.TIME_TICKED, cb.my_callback)
        ls.solve()
        #----------------------------------------
        
        #stats = ls.get_statistics()
        
        # Print final solution.
        # - for each operation of each job, the selected machine, the start and end dates
        start_times = []
        assignments = []
        workers = []
        for j in range(nb_jobs):
            for o in range(0, nb_operations[j]):
                taskIndex = job_operation_task[j][o]
                """print('Job %i Operation %i on Maschine %i by Worker %i starts at %i ends at %i (duration %i)' 
                    %(j,
                        o,
                        task_machine[taskIndex].value + 1,
                        task_worker[taskIndex].value + 1,
                        tasks[taskIndex].value.start(),
                        tasks[taskIndex].value.end(),
                        tasks[taskIndex].value.end()-tasks[taskIndex].value.start()))"""
                start_times.append(tasks[taskIndex].value.start())
                assignments.append(task_machine[taskIndex].value + 1)
                workers.append(task_worker[taskIndex].value + 1)
        status = str(ls.solution.status)
        fitness = makespan.value
        lower_bound = ls.solution.get_objective_bound(0)
        runtime = ls.statistics.running_time

    #lower_bound = solver.objective_value
    history_result = []
    for entry in history:
        history_result.append((entry[0], entry[1], entry[2]))    
    return status, fitness, lower_bound, runtime, start_times, assignments, workers, resources, history_result


if __name__ == '__main__':
    shutdown_when_finished = True
    # TODO: include all paths, all instances
    BENCHMARK_PATH = r'C:\Users\localadmin\Downloads\benchmarks_with_workers\benchmarks_with_workers'
    #BENCHMARK_PATH = r'C:\Users\localadmin\Desktop\experiments\comparison\benchmarks'
    OUTPUT_PATH = r'C:\Users\localadmin\Desktop\experiments\comparison\other\repetitions'
    # test fjssp first, then wfjssp 
    #solvers = ['cplex_cp', 'ortools', 'hexaly', 'cplex_lp', 'gurobi']
    runs = [['cplex_cp', 'ortools', 'hexaly'], ['cplex_lp', 'gurobi']] # split to allow MILP to run on small instances only
    runs = [['cplex_lp', 'gurobi']]
    #solvers = ['hexaly']
    #solvers = ['cplex_cp','ortools', 'gurobi', 'hexaly']
    #solvers = ['gurobi', 'cplex_lp']#['hexaly', 'cplex_lp'] # 'hexaly', 
    #solvers = ['ortools']#, 'gurobi', 'cplex_cp','hexaly']
    #instances = [('0_BehnkeGeiger', 'Behnke60.fjs'), ('6_Fattahi', 'Fattahi20.fjs'), ('1_Brandimarte', 'BrandimarteMk11.fjs'), ('4_ChambersBarnes', 'ChambersBarnes10.fjs'), ('5_Kacem', 'Kacem3.fjs')]
    #missing_results = {
    #    'cplex_cp': ['1_Brandimarte_10_workers.fjs', '1_Brandimarte_8_workers.fjs'], 
    #    'cplex_lp': ['0_BehnkeGeiger_10_workers.fjs', '0_BehnkeGeiger_11_workers.fjs', '0_BehnkeGeiger_12_workers.fjs', '0_BehnkeGeiger_13_workers.fjs', '0_BehnkeGeiger_14_workers.fjs', '0_BehnkeGeiger_15_workers.fjs', '0_BehnkeGeiger_16_workers.fjs', '0_BehnkeGeiger_17_workers.fjs', '0_BehnkeGeiger_18_workers.fjs', '0_BehnkeGeiger_19_workers.fjs', '0_BehnkeGeiger_1_workers.fjs', '0_BehnkeGeiger_20_workers.fjs', '0_BehnkeGeiger_21_workers.fjs', '0_BehnkeGeiger_22_workers.fjs', '0_BehnkeGeiger_23_workers.fjs', '0_BehnkeGeiger_24_workers.fjs', '0_BehnkeGeiger_25_workers.fjs', '0_BehnkeGeiger_26_workers.fjs', '0_BehnkeGeiger_27_workers.fjs', '0_BehnkeGeiger_28_workers.fjs', '0_BehnkeGeiger_29_workers.fjs', '0_BehnkeGeiger_2_workers.fjs', '0_BehnkeGeiger_30_workers.fjs', '0_BehnkeGeiger_31_workers.fjs', '0_BehnkeGeiger_32_workers.fjs', '0_BehnkeGeiger_33_workers.fjs', '0_BehnkeGeiger_34_workers.fjs', '0_BehnkeGeiger_35_workers.fjs', '0_BehnkeGeiger_36_workers.fjs', '0_BehnkeGeiger_37_workers.fjs', '0_BehnkeGeiger_38_workers.fjs', '0_BehnkeGeiger_39_workers.fjs', '0_BehnkeGeiger_3_workers.fjs', '0_BehnkeGeiger_40_workers.fjs', '0_BehnkeGeiger_41_workers.fjs', '0_BehnkeGeiger_42_workers.fjs', '0_BehnkeGeiger_43_workers.fjs', '0_BehnkeGeiger_44_workers.fjs', '0_BehnkeGeiger_45_workers.fjs', '0_BehnkeGeiger_46_workers.fjs', '0_BehnkeGeiger_47_workers.fjs', '0_BehnkeGeiger_48_workers.fjs', '0_BehnkeGeiger_49_workers.fjs', '0_BehnkeGeiger_4_workers.fjs', '0_BehnkeGeiger_50_workers.fjs', '0_BehnkeGeiger_51_workers.fjs', '0_BehnkeGeiger_52_workers.fjs', '0_BehnkeGeiger_53_workers.fjs', '0_BehnkeGeiger_54_workers.fjs', '0_BehnkeGeiger_55_workers.fjs', '0_BehnkeGeiger_56_workers.fjs', '0_BehnkeGeiger_57_workers.fjs', '0_BehnkeGeiger_58_workers.fjs', '0_BehnkeGeiger_59_workers.fjs', '0_BehnkeGeiger_5_workers.fjs', '0_BehnkeGeiger_60_workers.fjs', '0_BehnkeGeiger_6_workers.fjs', '0_BehnkeGeiger_7_workers.fjs', '2d_Hurink_vdata_46_workers.fjs', '2d_Hurink_vdata_47_workers.fjs', '2d_Hurink_vdata_48_workers.fjs', '3_DPpaulli_15_workers.fjs', '3_DPpaulli_18_workers.fjs'], 
    #    'gurobi': ['0_BehnkeGeiger_11_workers.fjs', '0_BehnkeGeiger_12_workers.fjs', '0_BehnkeGeiger_13_workers.fjs', '0_BehnkeGeiger_14_workers.fjs', '0_BehnkeGeiger_15_workers.fjs', '0_BehnkeGeiger_16_workers.fjs', '0_BehnkeGeiger_17_workers.fjs', '0_BehnkeGeiger_18_workers.fjs', '0_BehnkeGeiger_19_workers.fjs', '0_BehnkeGeiger_20_workers.fjs', '0_BehnkeGeiger_21_workers.fjs', '0_BehnkeGeiger_22_workers.fjs', '0_BehnkeGeiger_23_workers.fjs', '0_BehnkeGeiger_24_workers.fjs', '0_BehnkeGeiger_25_workers.fjs', '0_BehnkeGeiger_26_workers.fjs', '0_BehnkeGeiger_27_workers.fjs', '0_BehnkeGeiger_28_workers.fjs', '0_BehnkeGeiger_29_workers.fjs', '0_BehnkeGeiger_30_workers.fjs', '0_BehnkeGeiger_31_workers.fjs', '0_BehnkeGeiger_32_workers.fjs', '0_BehnkeGeiger_33_workers.fjs', '0_BehnkeGeiger_34_workers.fjs', '0_BehnkeGeiger_35_workers.fjs', '0_BehnkeGeiger_36_workers.fjs', '0_BehnkeGeiger_37_workers.fjs', '0_BehnkeGeiger_38_workers.fjs', '0_BehnkeGeiger_39_workers.fjs', '0_BehnkeGeiger_40_workers.fjs', '0_BehnkeGeiger_41_workers.fjs', '0_BehnkeGeiger_42_workers.fjs', '0_BehnkeGeiger_43_workers.fjs', '0_BehnkeGeiger_44_workers.fjs', '0_BehnkeGeiger_45_workers.fjs', '0_BehnkeGeiger_46_workers.fjs', '0_BehnkeGeiger_47_workers.fjs', '0_BehnkeGeiger_48_workers.fjs', '0_BehnkeGeiger_49_workers.fjs', '0_BehnkeGeiger_50_workers.fjs', '0_BehnkeGeiger_51_workers.fjs', '0_BehnkeGeiger_52_workers.fjs', '0_BehnkeGeiger_53_workers.fjs', '0_BehnkeGeiger_54_workers.fjs', '0_BehnkeGeiger_55_workers.fjs', '0_BehnkeGeiger_56_workers.fjs', '0_BehnkeGeiger_57_workers.fjs', '0_BehnkeGeiger_58_workers.fjs', '0_BehnkeGeiger_59_workers.fjs', '0_BehnkeGeiger_60_workers.fjs', '0_BehnkeGeiger_6_workers.fjs', '0_BehnkeGeiger_7_workers.fjs', '0_BehnkeGeiger_8_workers.fjs', '0_BehnkeGeiger_9_workers.fjs', '1_Brandimarte_10_workers.fjs', '1_Brandimarte_13_workers.fjs', '1_Brandimarte_15_workers.fjs', '2d_Hurink_vdata_27_workers.fjs', '2d_Hurink_vdata_29_workers.fjs', '2d_Hurink_vdata_30_workers.fjs', '2d_Hurink_vdata_31_workers.fjs', '2d_Hurink_vdata_32_workers.fjs', '2d_Hurink_vdata_33_workers.fjs', '2d_Hurink_vdata_34_workers.fjs', '2d_Hurink_vdata_35_workers.fjs', '2d_Hurink_vdata_36_workers.fjs', '2d_Hurink_vdata_37_workers.fjs', '2d_Hurink_vdata_38_workers.fjs', '2d_Hurink_vdata_39_workers.fjs', '2d_Hurink_vdata_40_workers.fjs', '2d_Hurink_vdata_41_workers.fjs', '2d_Hurink_vdata_42_workers.fjs', '2d_Hurink_vdata_43_workers.fjs', '2d_Hurink_vdata_46_workers.fjs', '2d_Hurink_vdata_47_workers.fjs', '2d_Hurink_vdata_48_workers.fjs', '3_DPpaulli_12_workers.fjs', '3_DPpaulli_14_workers.fjs', '3_DPpaulli_15_workers.fjs', '3_DPpaulli_17_workers.fjs', '3_DPpaulli_18_workers.fjs', '3_DPpaulli_9_workers.fjs'], 
    #    'hexaly': [], 
    #    'ortools': ['0_BehnkeGeiger_56_workers.fjs', '0_BehnkeGeiger_57_workers.fjs', '0_BehnkeGeiger_58_workers.fjs', '0_BehnkeGeiger_59_workers.fjs', '0_BehnkeGeiger_60_workers.fjs']}

    skip = False
    instances = ['6_Fattahi_1_workers.fjs', '6_Fattahi_2_workers.fjs', '6_Fattahi_3_workers.fjs', '6_Fattahi_4_workers.fjs', '6_Fattahi_5_workers.fjs', '6_Fattahi_6_workers.fjs', '6_Fattahi_7_workers.fjs', '6_Fattahi_8_workers.fjs', '6_Fattahi_9_workers.fjs', '6_Fattahi_10_workers.fjs',  '6_Fattahi_11_workers.fjs',  '6_Fattahi_12_workers.fjs', '6_Fattahi_13_workers.fjs', '6_Fattahi_14_workers.fjs', '6_Fattahi_15_workers.fjs']
    for i in range(len(runs)):
        solvers = runs[i]
        if i == 0 and False:
            instances = os.listdir(BENCHMARK_PATH)
        else:
            instances = ['6_Fattahi_1_workers.fjs', '6_Fattahi_2_workers.fjs', '6_Fattahi_3_workers.fjs', '6_Fattahi_4_workers.fjs', '6_Fattahi_5_workers.fjs', '6_Fattahi_6_workers.fjs', '6_Fattahi_7_workers.fjs', '6_Fattahi_8_workers.fjs', '6_Fattahi_9_workers.fjs', '6_Fattahi_10_workers.fjs',  '6_Fattahi_11_workers.fjs',  '6_Fattahi_12_workers.fjs', '6_Fattahi_13_workers.fjs', '6_Fattahi_14_workers.fjs', '6_Fattahi_15_workers.fjs']
        n_experiments = 5
        #instances.reverse()
        for i in range(n_experiments):
            for solver in solvers:
                #instances = missing_results[solver]
                for instance in instances:
                    if skip and solver == 'cplex_lp' and instance.startswith('1'): # skip behnkeGeiger
                        skip = False
                    if not skip:
                        # free up memory for the new run
                        p = None
                        status = None
                        fitness = None
                        lower_bound = None
                        runtime = None
                        start_times = None
                        assignments = None
                        workers = None
                        resources = None
                        history = None
                        cpu = None
                        ram = None
                        run_monitor = None
                        peak_cpu = None
                        peak_ram = None
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
                                status, fitness, lower_bound, runtime, start_times, assignments, workers, resources, history = run_gurobi(path)
                                run_monitor.value = 0
                                p.join()
                                peak_cpu = cpu.value
                                peak_ram = ram.value
                                message = f'{instance};{1 if status == 2 else 0 if status == 9 and len(start_times) > 0 else -1};{fitness};{lower_bound};{runtime};{start_times};{assignments};{workers};{peak_cpu};{peak_ram};{resources};{history}'
                            elif solver == 'cplex_lp':
                                cpu = Value('d', 0.0)
                                ram = Value('d', 0.0)
                                run_monitor = Value('i', 1)
                                p = Process(target=monitor_resources, args=(cpu, ram, 5, run_monitor))
                                p.start()
                                status, fitness, lower_bound, runtime, start_times, assignments, workers, resources, history = run_cplex_lp(path)
                                run_monitor.value = 0
                                p.join()
                                peak_cpu = cpu.value
                                peak_ram = ram.value
                                message = f'{instance};{1 if status == "OPTIMAL" else -1 if status == "INFEASIBLE" else 0};{fitness};{lower_bound};{runtime};{start_times};{assignments};{workers};{peak_cpu};{peak_ram};{resources};{history}'
                            elif solver == 'cplex_cp':
                                cpu = Value('d', 0.0)
                                ram = Value('d', 0.0)
                                run_monitor = Value('i', 1)
                                p = Process(target=monitor_resources, args=(cpu, ram, 5, run_monitor))
                                p.start()
                                status, fitness, lower_bound, runtime, start_times, assignments, workers, resources, history = run_cplex_cp(path)
                                run_monitor.value = 0
                                p.join()
                                peak_cpu = cpu.value
                                peak_ram = ram.value
                                message = f'{instance};{1 if status == "Optimal" else 0 if status == "Feasible" else -1};{fitness};{lower_bound};{runtime};{start_times};{assignments};{workers};{peak_cpu};{peak_ram};{resources};{history}'
                            elif solver == 'ortools':
                                cpu = Value('d', 0.0)
                                ram = Value('d', 0.0)
                                run_monitor = Value('i', 1)
                                p = Process(target=monitor_resources, args=(cpu, ram, 5, run_monitor))
                                p.start()
                                status, fitness, lower_bound, runtime, start_times, assignments, workers, resources, history = run_ortools(path)
                                run_monitor.value = 0
                                p.join()
                                peak_cpu = cpu.value
                                peak_ram = ram.value
                                message = f'{instance};{1 if status == "OPTIMAL" else 0 if status == "FEASIBLE" else -1};{fitness};{lower_bound};{runtime};{start_times};{assignments};{workers};{peak_cpu};{peak_ram};{resources};{history}'
                            else:
                                cpu = Value('d', 0.0)
                                ram = Value('d', 0.0)
                                run_monitor = Value('i', 1)
                                p = Process(target=monitor_resources, args=(cpu, ram, 5, run_monitor))
                                p.start()
                                status, fitness, lower_bound, runtime, start_times, assignments, workers, resources, history = run_hexaly(path)
                                run_monitor.value = 0
                                p.join()
                                peak_cpu = cpu.value
                                peak_ram = ram.value
                                message = f'{instance};{1 if status == "OPTIMAL" else 0 if status == "FEASIBLE" else -1};{fitness};{lower_bound};{runtime};{start_times};{assignments};{workers};{peak_cpu};{peak_ram};{resources};{history}'
                            write_output(message, f'{OUTPUT_PATH}/results_{solver}.txt')
                        except Exception as exception:
                            print(exception)
                            write_output(f'Error on instance {instance} using solver {solver}: {exception}', f'{OUTPUT_PATH}/results_{solver}.txt')
                            if p and p.is_alive():
                                #p.join()
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
                        del workers
                        del resources
                        del history
                        del cpu
                        del ram
                        del run_monitor
                        del peak_ram
                        del peak_cpu
                        del message
                    
    #from subprocess import Popen
    #processes = []
    #sub_process_path = r'C:\Users\localadmin\Documents\GitHub\scheduling_model_jrc\code\upgrades\CS_Translation\Solver\bin\Release\net8.0\Solver.exe'
    #for i in range(5):
    #    processes.append(Popen(sub_process_path))
    #for i in range(len(processes)):
    #    processes[i].wait()
    if shutdown_when_finished:
        os.system("shutdown /s /t 0")
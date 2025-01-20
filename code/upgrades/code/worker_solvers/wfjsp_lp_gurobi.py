# -*- coding: utf-8 -*-
"""
Created on Tue Apr 23 14:36:40 2024

@author: tst
"""

#WFJSP with Gurobi MILP Solver

import gurobipy as gp # Import des Gurobi-Pythonpakets

# Define SolutionListener function
from gurobipy import GRB
def SolutionListener(model, where):
    if where == GRB.Callback.MIPSOL:
        # MIP solution callback
        m._solution_count += 1
        obj_best = round(model.cbGet(GRB.Callback.MIPSOL_OBJBST))
        time = model.cbGet(GRB.Callback.RUNTIME)
        bnd = round(model.cbGet(GRB.Callback.MIPSOL_OBJBND))
        print(
            "Solution %i, time = %f s, objective = %i, bound = %i"
            % (m._solution_count, time, obj_best, bnd)
        )
        if obj_best - m._known_best <= 0:
            print('Stop early - known_best achieved')
            model.terminate()

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
m.Params.TimeLimit = 30
m.Params.LogToConsole = 0

#---------- ohne solution listener--------
#m.optimize()
#---------- mit solution listener--------
m._solution_count = 0
# Bei Abbruch wenn known_best erreicht
m._known_best = 0 # 884
m.optimize(SolutionListener)
#----------------------------------------


#Output   
xsol = m.getAttr('X', X)
usol = m.getAttr('X', U)
ysol = m.getAttr('X', Y)
csol = m.getAttr('X', C)

for j, k, i, s in job_op_mach_worker:
    if ysol[j,k,i,s] > 0:
        print('\nStarting time for Job %s Operation %s on machine %s with worker %s is %s' % (j,k,i,s,csol[j,k]-duration[j,k,i,s]) )
        print('Completion time for Job %s Operation %s: %s' % (j,k,csol[j,k]))
        print('Duration of Job %s Operation %s: %s' % (j,k,duration[j,k,i,s]))
         
print("solve status = {}\n".format(m.status))
print("Best objective value: %f" % m.objVal)
print('Objektive lower bound: %f' % m.objBound)
print("Wall time : %f s" % m.Runtime)

# Draw solution
import docplex.cp.utils_visu as visu
if visu.is_visu_enabled():
# Draw solution
    visu.timeline('MIP-Gurobi Solution for flexible job-shop problem with worker constraints ' + filename)
    visu.panel('Machines')
    for m in machines:
        visu.sequence(name='M' + str(m))
        for j, k, i, s in job_op_mach_worker:
            if ysol[j,k,i,s] > 0 and i == m:
                start_value = round(csol[j,k]-duration[j,k,i,s])
                end_value = round(csol[j,k])
                visu.interval(start_value, end_value, j, 'J{}_O{} by W{}'.format(j,k,s))
    visu.show()

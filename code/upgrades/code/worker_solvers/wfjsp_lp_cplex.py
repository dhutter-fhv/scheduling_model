# -*- coding: utf-8 -*-
"""
Created on Tue Apr 23 15:00:52 2024

@author: tst
"""

#  WFJSP mit Cplex MILP solver
from docplex.mp.model import Model

#Beispiel für Progress Listener siehe: https://github.com/IBMDecisionOptimization/docplex-examples/blob/master/examples/mp/jupyter/progress.ipynb

from docplex.mp.progress import ProgressListener, ProgressClock

class SolutionPrinter(ProgressListener):
    
    def __init__(self):
        ProgressListener.__init__(self, ProgressClock.Objective)
        self.solution_count = 0 
        
    def notify_progress(self, pdata):
        #Called at each new solution (better objective).
        objective = round(pdata.current_objective)
        bnd = round(pdata.best_bound)
        time = pdata.time
        print(
            "Solution %i, time = %f s, objective = %i, bound = %i"
            % (self.solution_count, time, objective, bnd)
        )
        self.solution_count += 1

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

print("Horizon = %i" % L)

        
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
print('Solving model...')
mdl.parameters.timelimit = 30;
mdl.add_progress_listener(SolutionPrinter())
#mdl.log_output = True
res = mdl.solve(execfile = r"C:\Program Files\IBM\ILOG\CPLEX_Studio2211\cplex\bin\x64_win64\cplex.exe")
#res = mdl.solve()

#Print Solution
print('Solution:')
'''print('mdl.report:')
mdl.report()

print('res.display:')
res.display()
'''

xsol = res.get_value_dict(X)
#ysol = res.get_value_dict(Y) #Bug in res.get_value_dict: wenn Y[i,j,m] negativ ist
csol = res.get_value_dict(C)

#Output
ysol = {}
for j, k, i, s in list_Y_var:
    ysol[j,k,i,s] = res.get_value(Y[j,k,i,s])
    if ysol[j,k,i,s] > 0:
        #print('\nStarting time for Job %s Operation %s on machine %s is %s' % (j,k,i,csol[j,k]-duration[j,k,i]) )
        #print('Completion time for Job %s Operation %s: %s' % (j,k,csol[j,k]))
        print('Job %i Operation %i on Maschine %i with worker %i starts at %i ends at %i (duration %i)' 
              %(j,k,i,s,round(csol[j,k]-duration[j,k,i,s]),round(csol[j,k]),duration[j,k,i,s]))
print("solve status: %s" % res.solve_status)
print("solve status: %s" % res.solve_details.status) 
print("solve status code: %i" % res.solve_details.status_code) #101...integer optimal, 107...time limit exceed
print("Best objective value: %f" % res.objective_value)
print('Objektive lower bound: %f' % res.solve_details.best_bound)
print("Wall time : %f s" % res.solve_details.time)

mdl.end()

# Draw solution
import docplex.cp.utils_visu as visu
if res and visu.is_visu_enabled():
# Draw solution
    visu.timeline('MIP-Cplex Solution for flexible job-shop problem with worker constraints ' + filename)
    visu.panel('Machines')
    for m in machines:
        visu.sequence(name='M' + str(m))
        for j, k, i, s in list_Y_var:
            if ysol[j,k,i,s] > 0 and i == m:
                start_value = round(csol[j,k]-duration[j,k,i,s])
                end_value = round(csol[j,k])
                visu.interval(start_value, end_value, j, 'J{}_O{} by W{}'.format(j,k,s))
    visu.show()
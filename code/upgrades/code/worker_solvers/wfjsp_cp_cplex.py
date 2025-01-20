# -*- coding: utf-8 -*-
"""
Created on Fri Apr 19 08:28:46 2024

@author: tst
"""
#WFJSP mit constraint programming von ILOG Cplex

from docplex.cp.model import *

#Solution Listener siehe https://ibmdecisionoptimization.github.io/docplex-doc/cp/docplex.cp.solver.solver_listener.py.html#docplex.cp.solver.solver_listener.CpoSolverListener
from docplex.cp.solver.solver_listener import *
class SolutionPrinter(CpoSolverListener):
    
    def __init__(self):
        self.last_best_value = 1000000
        self.solution_count = 0
        self.known_best = 0#885
    
    def solver_created(self, solver):
        """ Notify the listener that the solver object has been created.

        Args:
            solver: Originator CPO solver (object of class :class:`~docplex.cp.solver.solver.CpoSolver`)
        """
        print("Solver created")
        
    def new_result(self, solver, msol):
            #Called at each new solution (better objective).
            if msol:
                # Update objective value
                time = msol.get_solve_time()
                obj = msol.get_objective_value()
                bnd = msol.get_objective_bound()
                if obj < self.last_best_value: 
                    self.solution_count += 1
                    self.last_best_value = obj
                    print(
                        "Solution %i, time = %f s, objective = %i, bound = %i"
                        % (self.solution_count, time, obj, bnd)
                        )
                    if self.last_best_value - self.known_best <= 0:
                        print('Stop early - known_best achieved')
                        solver.abort_search()

#read and arrange Data
#Small Size Data: SFJW-01.txt to SFJW-10.txt
#filename = r'C:\Users\tst\OneDrive - FH Vorarlberg\Forschung\JobShopScheduling\MO-FJSPW_BenchmarkDataInstances\SFJW\SFJW-10.txt'
#Medium size Data: MFJW-01.txt to MFJW-07.txt
#filename = r'C:\Users\tst\OneDrive - FH Vorarlberg\Forschung\JobShopScheduling\MO-FJSPW_BenchmarkDataInstances\MFJW\MFJW-03.txt'

#von David erzeugte Probleme
#filename = r'C:\Users\tst\OneDrive - FH Vorarlberg\Forschung\JobShopScheduling\changed_benchmarks\0_BehnkeGeiger_1_updated.fjs'
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

print("Horizon = %i" % horizon)

        
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
mdl.add(no_overlap(mops[a] for a in mops if a[2]==m) for m in range(nb_machines))

# Add no_overlap constraint between operations executed by the same worker
mdl.add(no_overlap(mops[a] for a in mops if a[3]==s) for s in range(nb_workers))

# Minimize termination date
mdl.add(minimize(max(end_of(ops[j,o]) for j,o in ops)))


#-----------------------------------------------------------------------------
# Solve the model and display the result
#-----------------------------------------------------------------------------

#---------- mit solution listener----------------
context.solver.solve_with_search_next = True
mdl.add_solver_listener(SolutionPrinter())
#------------------------------------------------

# Solve model
print('Solving model...')
timelimit = 30

#---------- ohne solution listener--------
#res = mdl.solve(FailLimit=1000000,TimeLimit=10)
res = mdl.solve(execfile=r"C:\Program Files\IBM\ILOG\CPLEX_Studio2211\cpoptimizer\bin\x64_win64\cpoptimizer.exe", TimeLimit = timelimit, LogVerbosity = 'Quiet')
print('Solution:')
#res.print_solution()

for a in mops:
    itv = res.get_var_solution(mops[a])
    for m in range(nb_machines):
        if a[2]==m and itv.is_present():
            print('Job %i Operation %i on Mashine %i by Worker %i starts at %i ends at %i (duration %i)' %(a[0],a[1],a[2],a[3],itv.start,itv.end,itv.size))

print("solve status: " + res.solve_status)  
print("Best objective value: %i" % res.solution.objective_values[0])
print('Objektive lower bound: %i' % res.solution.objective_bounds[0])
print("  - wall time : %f s" % res.get_solve_time())

# Draw solution
import docplex.cp.utils_visu as visu
if res and visu.is_visu_enabled():
# Draw solution
    visu.timeline('CP-Cplex Solution for flexible job-shop problem with worker constraints ' + filename)
    visu.panel('Machines')
    for m in range(nb_machines):
        visu.sequence(name='M' + str(m))
        for a in mops:
            if a[2]==m:
                itv = res.get_var_solution(mops[a])
                if itv.is_present():
                    visu.interval(itv, a[0], 'J{}_O{} by W{}'.format(a[0],a[1],a[3]))
    visu.show()
    
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 16 11:09:58 2024

@author: tst
"""

#WFJSSP mit constraint programming mit OR Tools

import collections

from ortools.sat.python import cp_model

class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__solution_count = 0

    def on_solution_callback(self):
        """Called at each new solution."""
        print(
            "Solution %i, time = %f s, objective = %i, bound = %i"
            % (self.__solution_count, self.wall_time, round(self.objective_value), round(self.best_objective_bound))
        )
        self.__solution_count += 1

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
        horizon += max(task_processing_time[j][o][m][s] for m in range(nb_machines) for s in range(nb_workers) if task_processing_time[j][o][m][s] != INFINITE )

print("Horizon = %i" % horizon)

all_jobs = range(nb_jobs)
all_machines = range(nb_machines)
all_workers = range(nb_workers)

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

# Makespan objective.
makespan = model.new_int_var(0, horizon, "makespan")
model.add_max_equality(makespan, job_ends)
model.minimize(makespan)

# Solve model.
solver = cp_model.CpSolver()
# Sets a time limit in seconds.
solver.parameters.max_time_in_seconds = 30.0

#Meldung bei jeder neuen Lösung 
solution_printer = SolutionPrinter()
status = solver.solve(model, solution_printer)

#Ohne Meldung bei jeder neuen Lösung
#status = solver.solve(model)


# Print final solution.
for job_id in all_jobs:
    print("Job %i:" % job_id)
    for task_id in range(len(jobs[job_id])):
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
        print(
            "  task_%i_%i starts at %i ends at %i (alt %i, machine %i, worker %i, duration %i)"
            % (job_id, task_id, start_value,start_value+duration, selected, machine, worker, duration)
        )

print("solve status: %s" % solver.status_name(status))
print("Best objective value: %i" % solver.objective_value)
print("Objective Lower Bound: %i" % solver.best_objective_bound)
#print("Statistics")
#print("  - conflicts : %i" % solver.num_conflicts)
#print("  - branches  : %i" % solver.num_branches)
print("  - wall time : %f s" % solver.wall_time)

# Draw solution
import docplex.cp.utils_visu as visu
if visu.is_visu_enabled():
# Draw solution
    visu.timeline('CP-OR Solution for flexible job-shop problem with worker constraints ' + filename)
    visu.panel('Machines')
    for m in range(nb_machines):
        visu.sequence(name='M' + str(m))
        for job_id in all_jobs:
            for task_id in range(len(jobs[job_id])):
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
                if m == machine:
                    visu.interval(start_value, start_value+duration, job_id, 'J{}_O{} by W{}'.format(job_id,task_id,worker))
       
    visu.show()
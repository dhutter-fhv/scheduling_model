# -*- coding: utf-8 -*-
"""
Created on Tue Apr 18 08:19:17 2023

@author: tst
"""

#%% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
#FJSSP with workers   
if 1==1:
    #import numpy as np
    #import matplotlib.pyplot as plt
    import gurobipy as gp # Import des Gurobi-Pythonpakets
    #from gurobipy import GRB
    # sequence based MILP for FJSSP
    
#read and arrange Data
    #Small Size Data: SFJW-01.txt to SFJW-10.txt
    #f = open(r'C:\Users\tst\OneDrive - FH Vorarlberg\Forschung\JobShopScheduling\MO-FJSPW_BenchmarkDataInstances\SFJW\SFJW-10.txt')
    #Medium size Data: MFJW-01.txt to MFJW-07.txt
    f = open(r'C:\Users\huda\Documents\GitHub\scheduling_model\code\external_test_data\1\MFJW\MFJW-01.txt')
    
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
    m = gp.Model('milp33')
    
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
    m.display()
    m.optimize()
    
#Output   

    if m.Status == gp.GRB.OPTIMAL:
        xsol = m.getAttr('X', X)
        usol = m.getAttr('X', U)
        ysol = m.getAttr('X', Y)
        csol = m.getAttr('X', C)
        
        for j, k, i, s in job_op_mach_worker:
            if ysol[j,k,i,s] > 0:
                print('\nStarting time for Job %s Operation %s on machine %s with worker %s is %s' % (j,k,i,s,csol[j,k]-duration[j,k,i,s]) )
                print('Completion time for Job %s Operation %s: %s' % (j,k,csol[j,k]))
                print('Duration of Job %s Operation %s: %s' % (j,k,duration[j,k,i,s]))
    else:
        print("status = {}\n".format(m.status)) 
#%% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
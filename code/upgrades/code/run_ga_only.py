from subprocess import Popen
import os
import time

#b_path = r"C:\Users\huda\Documents\GitHub\scheduling_model_jrc\code\upgrades\benchmarks_with_workers"
#files = os.listdir(b_path)
#for file in files:
#    if file.endswith('.json'):
#        print(b_path + "\\" + file)
#        os.remove(b_path + "\\" + file)
shutdown_when_finished = False
processes = []
sub_process_path = r'C:\Users\localadmin\Documents\GitHub\scheduling_model_jrc\code\upgrades\CS_Translation\Solver\bin\Release\net8.0\Solver.exe'
for i in range(6):
    processes.append(Popen(sub_process_path + f' {i+1}'))
    time.sleep(1)
for i in range(len(processes)):
    processes[i].wait()
if shutdown_when_finished:
    os.system("shutdown /s /t 1")

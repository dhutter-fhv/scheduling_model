from subprocess import Popen
processes = []
for i in range(5):
    args = r'C:\Users\huda\Documents\GitHub\scheduling_model_jrc\code\upgrades\CS_Translation\Solver\bin\Release\net8.0\Solver.exe'
    process = Popen(args)
    processes.append(process)
for process in processes:
    process.wait()
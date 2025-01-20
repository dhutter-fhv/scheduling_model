
from .encoding import Encoding, WorkerEncoding

import numpy as np

class BenchmarkParser: 
    def __init__(self):
        pass

    def parse_benchmark(self, path: str):
        file_content = []

        try:
            file = open(path, 'r')
            file_content = file.readlines()
        except Exception as exception: print(exception) 

        info = file_content[0].split(' ')
        n_machines = int(info[1])
        n_overall_operations = 0
        lines = [line.split() for line in file_content[1:]]
        for i in range(1, len(file_content)):
            line = file_content[i].split(' ')
            lines[i - 1] = line
            n_overall_operations += int(line[0])
        
        durations = np.zeros((n_overall_operations, n_machines), dtype=int)
        operation_index = 0
        job_sequence = [None] * n_overall_operations

        for i in range(1, len(lines)+1):

            line = lines[i-1]
            n_operations = int(line[0])
            index = 1
            for j in range(0, n_operations):
                job_sequence[operation_index] = i-1
                n_options = int(line[index])
                index +=1
                for k in range(0, n_options):
                    machine = int(line[index])
                    index += 1
                    duration = int(line[index])
                    index += 1
                    durations[operation_index, machine - 1] = duration
                operation_index += 1
                
        return Encoding(durations, job_sequence)

class WorkerBenchmarkParser: 
    def __init__(self):
        pass

    def parse_benchmark(self, path: str):
        file_content = []

        try:
            file = open(path, 'r')
            file_content = file.readlines()
        except Exception as exception: print(exception) 

        info = file_content[0].split(' ')
        n_machines = int(info[1])
        n_workers = int(round(float(info[2])))
        n_overall_operations = 0
        lines = [line.split() for line in file_content[1:]]

        for i in range(1, len(file_content)):
            line = file_content[i].split(' ')
            lines[i - 1] = line
            n_overall_operations += int(line[0])
        
        durations = np.zeros((n_overall_operations, n_machines, n_workers), dtype=int)
        operation_index = 0
        job_sequence = [None] * n_overall_operations

        for i in range(1, len(lines)+1):

            line = lines[i-1]
            n_operations = int(line[0])
            index = 1
            for j in range(0, n_operations):
                job_sequence[operation_index] = i-1
                n_machine_options = int(line[index])
                index +=1
                for k in range(0, n_machine_options):
                    machine = int(line[index])
                    index += 1
                    n_worker_options = int(line[index])
                    index += 1

                    for l in range(0, n_worker_options):
                        worker = int(line[index])
                        index += 1
                        duration = int(line[index])
                        index += 1
                        durations[operation_index, machine - 1, worker - 1] = duration
                
                operation_index += 1
                
        return WorkerEncoding(durations, job_sequence)

"""def main(): 
    #path = "C:\\Users\\Bianca\\OneDrive - FH Vorarlberg\\JRZ\\JRZ\\Scheduling\\scheduling_model\\code\\external_test_data\\FJSSPinstances\\6_Fattahi\\Fattahi20.fjs"
    #parser = WorkerBenchmarkParser()
    #result = parser.parse_benchmark(path)

    path = "C:\\Users\\Bianca\\OneDrive - FH Vorarlberg\\JRZ\\JRZ\\Scheduling\\scheduling_model\\code\\external_test_data\\FJSSPinstances\\6_Fattahi\\Fattahi20.fjs"
    parser = WorkerBenchmarkParser()
    result = parser.parse_benchmark(path)

    for i in range(0, result.durations().shape[0]):
        for j in range(0, result.durations().shape[1]):
            for k in range(0, result.durations().shape[2]):
                print(f"{result.durations()[i, j, k]},")

    print(f"n_jobs: {result.n_jobs()}")
    print(f"n_machines: {result.n_machines()}")
    print(f"n_operations: {result.n_operations()}")
    print(f"get_workers_for_operation: {result.get_workers_for_operation(1)}")
    print(f"get_all_machines_for_all_operations: {result.get_all_machines_for_all_operations()}")
    print(f"get_workers_for_operation_on_machine: {result.get_workers_for_operation_on_machine(1, 1)}")
    print(f"is_possible: {result.is_possible(1,1,1)}")

if __name__ == "__main__":
    main()"""


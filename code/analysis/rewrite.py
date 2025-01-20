# convert GA result file
import json
import copy
from os import listdir
base_path = '/home/dhu/Downloads/converted/'
ga_files = listdir(base_path)
out_path = '/home/dhu/Downloads/ga_results/converted/results_ga_best.txt'
#best = dict()
i = 0
for instance in ga_files:
    print(f'{i} - Rewriting: {instance}')
    i+= 1
    with open(f'{base_path}/{instance}', 'r') as file:
        data = json.load(file)
        name = data[0]['Name']
        best= copy.deepcopy(data[0])
        for run in data[1:]:
            if run['Result']['Fitness']['Makespan'] < best['Result']['Fitness']['Makespan']:
                best = copy.deepcopy(run)
        del data
        optimization_status = 0
        fitness_value = best['Result']['Fitness']['Makespan']
        lower_bound = 0
        runtime = best['Result']['TimeInSeconds']
        # TODO: not needed for analysis and comparison
        result_vector1 = []#best['Result']['Sequence']
        result_vector2 = []#best['Result']['Assignments']
        result_vector3 = []#best['Result']['Workers']
        peak_cpu = 0.0 # TODO
        peak_ram = 0.0 # TODO
        resource_history = [] 
        best_result_history = best['OverallBestFitness']

        with open(out_path, 'a') as out:
            out.write(f'{name};{optimization_status};{fitness_value};{lower_bound};{runtime};{result_vector1};{result_vector2};{result_vector3};{peak_cpu};{peak_ram};{resource_history};{best_result_history}\n')

from ga import GA
from history import History
from translation import SequenceGAEncoder, FJSSPInstancesTranslator
from model import Order, ProductionEnvironment
import time
import os
import inspect

def generate_one_order_per_recipe(production_environment : ProductionEnvironment) -> list[Order]:
    orders : list[Order] = []
    for i in range(len(production_environment.resources.values())): # should be the same amount as recipes for now
        orders.append(Order(delivery_time=1000, latest_acceptable_time=1000, resources=[(production_environment.get_resource(i), 1)], penalty=100.0, tardiness_fee=50.0, divisible=False, profit=500.0))
    return orders

def run_experiment(source, instance, parameters : dict):
    production_environment = FJSSPInstancesTranslator().translate(source, instance)
    orders = generate_one_order_per_recipe(production_environment)
    production_environment.orders = orders
    workstations_per_operation, base_durations, job_operations = SequenceGAEncoder().encode(production_environment, orders)
    ga = GA(job_operations, workstations_per_operation, base_durations)
    population_size = parameters['population_size'] if 'population_size' in parameters else 100
    offspring_amount = parameters['offspring_amount'] if 'offspring_amount' in parameters else population_size
    max_generations = parameters['max_generations'] if 'max_generations' in parameters else None
    run_for = parameters['time_limit'] if 'time_limit' in parameters else None
    stop_at = parameters['target_fitness'] if 'target_fitness' in parameters else None
    random_initialization = parameters['random_initialization'] if 'random_initialization' in parameters else False
    elitism = parameters['elitism'] if 'elitism' in parameters else 0
    allow_duplicate_parents = parameters['duplicate_parents'] if 'duplicate_parents' in parameters else False
    fill_gaps = parameters['fill_gaps'] if 'fill_gaps' in parameters else False
    adjust_individuals = parameters['adjust_individuals'] if 'adjust_individuals' in parameters else False
    adjust_parameters = parameters['adjust_mutation'] if 'adjust_mutation' in parameters else False
    restart_generations = parameters['restart_generations'] if adjust_parameters else 0
    max_p = parameters['max_mutation_rate'] if adjust_parameters else 0
    restart_at_max_p = parameters['restart_at_max_mutation_rate'] if adjust_parameters else False
    sequence_mutation = parameters['sequence_mutation'] if 'sequence_mutation' in parameters else 'mix'
    selection = parameters['selection'] if 'selection' in parameters else 'tournament'
    tournament_size = parameters['tournament_size'] if selection == 'tournament' else 0
    random_individual_per_generation_amount = parameters['random_individuals'] if 'random_individuals' in parameters else 0
    output_interval = parameters['output_interval'] if 'output_interval' in parameters else 1000
    start_time = time.time()
    history = ga.run(population_size, offspring_amount, max_generations, run_for, stop_at, None, tournament_size, adjust_parameters, restart_generations=restart_generations, max_p=max_p, restart_at_max_p=restart_at_max_p, elitism=elitism, sequence_mutation=sequence_mutation, fill_gaps=fill_gaps, adjust_optimized_individuals=adjust_individuals, random_individuals=random_individual_per_generation_amount, allow_duplicate_parents=allow_duplicate_parents, random_initialization=random_initialization, output_interval=output_interval)
    run_time = time.time() - start_time
    return history, run_time

def run(source, instance, target_fitness, time_limit):
    parameters = {
        'population_size': 5,
        'offspring_amount': 20,
        'max_generations': None,
        'time_limit': time_limit,
        'target_fitness': target_fitness,
        'elitism': 1,
        'random_initialization': False,
        'duplicate_parents': False,
        'pruning': False,
        'fill_gaps': True,
        'adjust_individuals': True,
        'adjust_mutation': True,
        'restart_generations': 50,
        'max_mutation_rate': 1.0,
        'restart_at_max_mutation_rate': True,
        'avoid_local_mins': True,
        'local_min_distance': 0.1,
        'sequence_mutation': 'swap',
        'selection': 'tournament',
        'tournament_size': 2,
        'random_individuals': 0,
        'output_interval': 1000
    }

    history, run_time = run_experiment(source, instance, parameters)
    return history, run_time

from datetime import datetime
if __name__ == '__main__':
    currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    #read_path = r'C:\Users\localadmin\Documents\GitHub\scheduling_model\code\upgrades\benchmarks\\'
    
    shutdown_when_finished = False

    import evaluation
    
    time_limit = 3600
    n_experiments = 10
    selection = [('5_Kacem', 1, 0),('5_Kacem', 2, 0),('5_Kacem', 3, 0),('5_Kacem', 4, 0), ('1_Brandimarte', 1, 0), ('1_Brandimarte', 2, 0), ('1_Brandimarte', 3, 0), ('1_Brandimarte', 4, 0), ('1_Brandimarte', 5, 0), ('1_Brandimarte', 6, 0), ('1_Brandimarte', 7, 0), ('1_Brandimarte', 8, 0), ('1_Brandimarte', 9, 0), ('1_Brandimarte', 10, 0), ('1_Brandimarte', 11, 0), ('1_Brandimarte', 12, 0), ('1_Brandimarte', 13, 0), ('1_Brandimarte', 14, 0), ('1_Brandimarte', 15, 0)]
    histories : list[History] = []

    #for memory conservation 
    result_path = r'C:\Users\localadmin\Documents\GitHub\scheduling_model\code\upgrades\code\results\\'
    for instance in selection:
        for j in range(n_experiments):
            history, real_runtime = run(instance[0], instance[1], instance[2], time_limit)
            history.instance = f'{instance[0]}_{instance[1]}'
            # for memory conservation
            history.to_file(f'{result_path}{datetime.now().day}-{datetime.now().month}-{datetime.now().year}-{j}-{history.instance}.json')
            #histories.append(history)
            print(f'{j} - {instance[0]}{instance[1]} - Done')

            # testing purposes
            """n_options = 5
            makespan_options, idle_time_options, queue_time_options = history.get_options(n_options) # get 5 options

            solutions = dict()
            for i in range(n_options):
                if str(makespan_options[i][0]) not in solutions:
                    solutions[str(makespan_options[i][0])] = [makespan_options[i][0], [0, 0, 0]]
                if str(idle_time_options[i][0]) not in solutions:
                    solutions[str(idle_time_options[i][0])] = [idle_time_options[i][0], [0, 0, 0]]
                if str(queue_time_options[i][0]) not in solutions:
                    solutions[str(queue_time_options[i][0])] = [queue_time_options[i][0], [0, 0, 0]]
            # sum ranks
            for i in range(n_options):
                solutions[str(makespan_options[i][0])][1][0] = i
                solutions[str(idle_time_options[i][0])][1][1] = i
                solutions[str(queue_time_options[i][0])][1][2] = i

            sorted_solutions = sorted(solutions.keys(), key=lambda x: sum(solutions[x][1])/len(solutions[x][1]))
            useable_solutions = [solutions[x][0] for x in sorted_solutions][:n_options]
            #solution = history.overall_best[-1][1][0]
            required_operations = history.required_operations
            durations = history.durations
            rank = 0
            colors = evaluation.predefine_colors(useable_solutions[0][0])
            for solution in useable_solutions:
                sequence = solution[0]
                assignments = solution[1]
                # actually not necessary, but whatever for now
                m = evaluation.makespan(sequence, assignments, durations, required_operations)
                i = evaluation.idle_time(sequence, assignments, durations, required_operations)
                q = evaluation.queue_time(sequence, assignments, durations, required_operations)
                print(f'Makepsan: {m}, Idle-Time: {i}, Queue-Time: {q}')
                evaluation.visualize(sequence, assignments, durations, required_operations, m, i, q, instance[0], instance[1], pre_colors=colors)#, title_prefix=f'Rank {rank}')
                rank += 1
            evaluation.show_plots()"""


if shutdown_when_finished:
    os.system("shutdown /s /t 1")
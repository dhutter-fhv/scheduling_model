from model import ProductionEnvironment, Job, Order, Recipe, Workstation, Task, Resource, Schedule
from copy import deepcopy
from translation import TimeWindowGAEncoder, Encoder, SimpleGAEncoder, GurobiEncoder
from evaluation import Evaluator, Objective
import random
import math

class Solver:
    
    def __init__(self, name : str, production_environment : ProductionEnvironment, encoder : Encoder = None) -> None:
        self.name = name
        self.production_environment = production_environment
        self.evaluator = Evaluator(self.production_environment)
        self.encoder = encoder

    def add_objective(self, objective : Objective) -> None:
        self.evaluator.add_objective(objective)

    def remove_objective(self, objective : Objective) -> None:
        self.evaluator.remove_objective(objective)

    def clear_objectives(self) -> None:
        self.evaluator.clear_objectives()

    def reset(self) -> None:
        self.clear_objectives()
    

class TimeWindowGASolver(Solver):

    def __init__(self, production_environment : ProductionEnvironment, orders : list[Order]) -> None:
        # TODO: after job change to objects, probably don't need list of orders anymore
        super().__init__('Time Window GA', production_environment, TimeWindowGAEncoder())
        self.production_environment = production_environment
        self.orders = orders

    def configure(self, encoding : list[int], population_size : int = 25, offspring_amount : int = 50, elitism : bool = False, mutation_probability : float = None, max_generations : int = 100, first_time_slot : int = 0, last_time_slot : int = 1000) -> None:
        self.max_generations = max_generations
        self.population_size = population_size
        self.offspring_amount = offspring_amount
        self.elitism = elitism
        self.first_time_slot = first_time_slot
        self.last_time_slot = last_time_slot
        if not mutation_probability:
            mutation_probability = 1 / len(encoding)
        self.mutation_probability = mutation_probability

    def initialize_population(self) -> list[list[int]]: # TODO
        population : list[list[int]] = []
        for i in range(self.population_size): 
            individual : list[int] = []
            for j in range(len(self.jobs)):
                #<workstation, worker, start_time, end_time>
                tasks : list[Task] = self.jobs[j].recipe.get_alternatives(self.jobs[j].task)
                task : Task = random.choice(tasks) # choose random starting task (chooses worker)
                self.jobs[j].task = task
                workstations : list[Workstation] = self.production_environment.get_available_workstations_for_task(task)
                workstation : Workstation = random.choice(workstations)
                worker : Resource = task.required_resources[0][0]
                duration = workstation.get_duration(task)
                start_time = random.randint(self.first_time_slot, self.last_time_slot - duration)
                end_time = random.randint(start_time, self.last_time_slot)
                individual.append(int(workstation.id))
                individual.append(int(worker.id))
                individual.append(start_time)
                individual.append(end_time)
            population.append(individual)
        return population

    def _evaluate(self, individual : list[int]) -> list[float]:
        #encoder = TimeWindowGAEncoder()
        schedule : Schedule = self.encoder.decode(individual, self.jobs, self.production_environment, [], self)
        if not schedule.is_feasible(self.jobs):
            return 2 * self.last_time_slot
        # use evaluation module
        objective_values = self.evaluator.evaluate(schedule, self.jobs, self.orders)
        schedule.objective_values = objective_values
        # maybe keep schedule ? 
        return objective_values

    def _evaluate_population(self, population : list[list[int]]) -> list[list[float]]:
        population_fitness : list[list[float]] = []
        for individual in population:
            objective_values = self._evaluate(individual)
            population_fitness.append(objective_values)
        return population_fitness

    def _get_weighted_probabilities(self, population : list[list[int]], population_fitness : list[list[float]]) -> list[float]:
        #TODO: invert probabilities, currently higher values get higher weights NOTE: (needs testing)
        probabilities : list[float] = []
        sum = 0
        max_fitness = 0
        for fitness in population_fitness:
            if fitness[0] > max_fitness:
                max_fitness = fitness[0]
            sum += fitness[0] #NOTE/TODO: only one objective value for now
        population = []
        previous_probability = 0.0
        while len(population) < self.population_size:
            for i in range(len(population)):
                #probability = previous_probability + (fitness[i] / sum)
                probability = previous_probability + ((max_fitness - fitness[i]) / sum)
                probabilities.append(probability)
                previous_probability = probability
        return probabilities

    def _roulette_wheel_selection(self, population : list[list[int]], population_fitness : list[list[float]]):
        r = random.random()
        probabilities = self._get_weighted_probabilities(population, population_fitness)
        for i in range(len(probabilities)):
            if r < probabilities[i]:
                return population[i]
        return population[-1]

    def _select_parents(self, population : list[list[int]], population_fitness : list[list[float]]) -> tuple[list[int], list[int]]:
        parent_a = self._roulette_wheel_selection(population, population_fitness)
        parent_b = []
        while parent_a == parent_b: # force 2 different parents
            parent_b = self._roulette_wheel_selection(population, population_fitness)
        return parent_a, parent_b

    def _mutate(self, individual : list[int]) -> list[int]:
        job_index = 0
        for i in range(len(individual)):
            if i != 0 and i % 4 == 0:
                job_index += 1
            if random.random() < self.mutation_probability:
                job = self.jobs[job_index]
                if i % 4 == 0:
                    # mutate workstation
                    workstations : list[Workstation] = self.production_environment.get_available_workstations_for_task(job.task)
                    individual[i] = int(random.choice(workstations).id)
                elif i % 4 == 1:
                    # mutate worker
                    recipe : Recipe = job.recipe #self.production_environment.get_recipe(job.recipe_id)
                    alternatives : list[Task] = None
                    for alternative_list in recipe.tasks:
                        for task in alternative_list:
                            if task == job.task: #str(task.id) == str(job.task.id):#job.task_id:
                                alternatives = alternative_list # NOTE: probably needs to be changed
                                break
                    alternative : Task = random.choice(alternatives)
                    worker : Resource = alternative.required_resources[0][0] # <resource, quantity> # NOTE: only works for examples with exactly one resource
                    individual[i] = int(worker.id)
                    job.task = alternative # adapt job to make sure the selected alternative is known to the solver
                elif i % 4 == 2:
                    # mutate start time
                    workstation = self.production_environment.get_workstation(individual[i-2])
                    duration = workstation.get_duration(job.task)
                    if duration:
                        individual[i] = random.randint(self.first_time_slot, self.last_time_slot - duration) # NOTE: upper bound should probably be limited
                    else:
                        # should probably throw an exception here
                        pass
                elif i % 4 == 3:
                    # mutate end time
                    workstation = self.production_environment.get_workstation(individual[i-3])
                    duration = workstation.get_duration(job.task)
                    if duration:
                        individual[i] = random.randint(self.first_time_slot + duration, self.last_time_slot)
                    else:
                        # should probably throw an exception here
                        pass
        

    def _recombine(self, parent_a : list[int], parent_b : list[int]) -> tuple[list[int], list[int]]:
        crossover_point_a = random.randint(0, len(parent_a) - 2)
        crossover_point_b = random.randint(crossover_point_a + 1, len(parent_a) - 1)
        offspring_a = []
        offspring_b = []
        for i in range(crossover_point_a):
            offspring_a.append(parent_a[i])
            offspring_b.append(parent_b[i])
        for i in range(crossover_point_a + 1, crossover_point_b):
            offspring_a.append(parent_b[i])
            offspring_b.append(parent_a[i])
        for i in range(crossover_point_b + 1, len(parent_a)):
            offspring_a.append(parent_a[i])
            offspring_b.append(parent_b[i])
        return deepcopy(offspring_a), deepcopy(offspring_b)
    
    def get_best(self, population : list[list[int]], population_fitness : list[list[float]]):
        best : tuple[list[list[int]], list[list[float]]] = population[0]
        for i in range(1, len(population_fitness)):
            if population_fitness[i][0] < best[1][0]:
                best = (population[i], population_fitness[i])
        return deepcopy(best)


    def _select_next_generation(self, pool : list[list[int]], pool_fitness : list[list[float]]) -> tuple[list[list[int]], list[list[float]]]:
        population : list[list[int]] = []
        population_fitness : list[list[float]] = []
        while len(population) < self.population_size:
            individual : list[int] = self._roulette_wheel_selection(pool, pool_fitness)
            idx = pool.index(individual)
            population.append(individual)
            population_fitness.append(pool_fitness[idx])
            pool.pop(idx)
            pool_fitness.pop(idx)
        return population, population_fitness

    def solve(self, jobs : list[Job]):
        self.jobs = jobs
        population : list[list[int]] = self.initialize_population()
        population_fitness : list[list[float]] = self._evaluate_population(population)
        offsprings : list[list[int]] = []
        offspring_fitness : list[list[float]] = []
        best : tuple[list[int], list[float]] = self.get_best(population, population_fitness)
        
        for generation in range(self.max_generations):
            offsprings.clear()
            offspring_fitness.clear()

            # recombine
            while len(offsprings < self.offspring_amount):
                parent_a, parent_b = self._select_parents(population, population_fitness)
                offspring_a, offspring_b = self._recombine(parent_a, parent_b)
                # mutate
                self._mutate(offspring_a)
                offsprings.append(offspring_a)
                if len(offsprings) + 1 <= self.offspring_amount:
                    self._mutate(offspring_b)
                    offsprings.append(offspring_b)

            # evaluate offsprings
            offspring_fitness = self._evaluate_population(offsprings)
            
            best_offspring = self.get_best(offsprings, offspring_fitness)
            if best_offspring[1][0] < best[1][0]:
                best = best_offspring

            # select next generation
            if self.elitism:
                offsprings.extend(population)
                offspring_fitness.extend(population_fitness)
            
            population.clear()
            population_fitness.clear()

            population, population_fitness = self._select_next_generation(offsprings, offspring_fitness)

        return best

class HarmonySearch(Solver):

#NOTE: this is just the base algorithm, several improvements to the HS-Algorithm have been suggested
    def __init__(self, production_environment : ProductionEnvironment):
        super().__init__('Harmony Search Solver', production_environment)

    def evaluate(self, harmony):
        pass

    def solve(self):
        #step 1: parameters
        harmony_search_memory_size = 10
        harmony_memory : list[list[int]] = []
        lower_bounds : list[int] = []
        upper_bounds : list[int] = []
        harmony_considering_rate = 0.1
        pitch_adjusting_rate = 0.1 # mutation probability
        individual_size = 20
        bandwith = 2
        max_improvisations = 1000
        # for improved harmony search
        #max_pitch_adjusting_rate = 0.5
        #min_pitch_adjusting_rate = 0.1
        #max_bandwith = 4 NOTE: bandwidths should be a list for combinatorial problems
        #min_bandwith = 2
        #step 2: initialize the harmony memory
        for i in range(harmony_search_memory_size):
            harmony = []
            for j in range(individual_size):
                harmony.append(lower_bounds[j] + random.random() * (upper_bounds[j] - lower_bounds[j]))
            fitness = self.evaluate(harmony)
            harmony_memory.append((harmony, fitness))
        for i in range(max_improvisations):
            #step 3: improvise a new harmony
            harmony = []
            for j in range(individual_size):
                if random.random() <= harmony_considering_rate:
                    harmony.append(random.choice(harmony_memory)[0][j])
                    # for improved harmony search
                    # NI number of solution vector generations (=individual_size?)
                    # pitch_adjusting_rate = min_pitch_adjusting_rate + ((max_pitch_adjusting_rate - min_pitch_adjusting_rate) / individual_size) * j
                    if random.random() <= pitch_adjusting_rate:
                        # for improved harmony search
                        # c = math.log(max_bandwith / min_bandwith) / individual_size
                        # bandwidth = max_bandwith * math.exp(c * j)
                        harmony[-1] += random.random() * bandwith
                else:
                    harmony.append(lower_bounds[j] + random.random() * (upper_bounds[j] - lower_bounds[j]))
            #step 4: update harmony memory: replace worst harmony in memory with the new harmony, if the new harmony is better
            fitness = self.evaluate(harmony)
            worst = None # NOTE: worst individual could just be tracked
            for harmony in harmony_memory:
                if worst is None or harmony[1] > worst[1]:
                    worst = (harmony)
            if fitness < worst[1]:
                harmony.remove(worst)
                harmony.append((harmony, fitness))

import pygad

class GASolver(Solver):

    instance = None

    def __init__(self, encoding : list[int], durations : dict[int, list[int]], job_list : list[Job], production_environment : ProductionEnvironment, orders : list[Order]):
        super().__init__('GASolver', production_environment, SimpleGAEncoder())
        self.encoding = encoding
        self.durations = durations
        self.jobs : list[Job] = job_list
        self.orders = orders
        self.best_history = []
        self.average_history = []
        self.memory : dict[list[int], float] = dict()
        self.memory_duplicate = 0
        GASolver.instance = self

    def reset(self) -> None:
        super().reset()
        self.best_solution = None
        self.best_history = []
        self.average_history = []
        self.memory : dict[list[int], float] = dict()
        self.memory_duplicate = 0
        GASolver.instance = self

    def initialize(self, earliest_slot : int = 0, last_slot : int = 1000, population_size : int = 100, offspring_amount : int = 50, max_generations : int = 5000, crossover : str = 'two_points', selection : str = 'rws', mutation : str = 'workstation_only', k_tournament : int = 10, keep_parents : int = 10, keep_elitism : int = 0, parallel_processing=["process", 10], verbose : bool = True, repair : bool = False, repair_on_crossover : bool = False, random_until_feasible : bool = False) -> None:
        self.earliest_slot = earliest_slot
        self.last_slot = last_slot
        self.population_size = population_size
        self.offspring_amount = offspring_amount
        self.max_generations = max_generations
        self.crossover_type = crossover
        self.parent_selection_type = selection
        self.verbose = verbose
        self.random_until_feasible = random_until_feasible
        self.repair = repair
        #self.mutation_type = GASolver.alternative_mutation_function # set as default if no feasible option is provided
        if mutation == 'workstation_only':
            self.mutation_type = GASolver.alternative_mutation_function
        elif mutation == 'full_random':
            self.mutation_type = GASolver.mutation_function
        elif mutation == 'random_only_feasible':
            self.mutation_type = GASolver.only_feasible_mutation
        elif mutation == 'force_feasible':
            self.mutation_type = GASolver.force_feasible_mutation
        else:
            self.mutation_type = mutation
        self.mutation_percentage_genes = 10 # not used, but necessary parameter
        self.gene_type = int
        self.keep_parents = keep_parents
        gene_space_workstations = {'low': 0, 'high': len(self.production_environment.workstations)}
        gene_space_starttime = {'low': self.earliest_slot, 'high': self.last_slot}
        self.gene_space = []
        self.objective_function = GASolver.fitness_function
        for i in range(0, len(self.encoding), 2):
            #self.gene_space.append(gene_space_workstations)
            #NOTE: experimental
            #NOTE: maybe do custom initialization, use inital_population parameter
            possible_workstations = [int(x.id) for x in self.production_environment.get_available_workstations_for_task(self.jobs[int(i/2)].task)]
            self.gene_space.append(possible_workstations)
            if mutation == 'force_feasible':
                lower_bound, upper_bound = self.determine_gene_space(i)
                self.gene_space.append({'low': lower_bound, 'high': upper_bound})
            else:
                self.gene_space.append(gene_space_starttime)
        on_crossover = None
        on_mutation = None
        if repair:
            if repair_on_crossover:
                on_crossover = GASolver.repair_offspring
            else:
                on_mutation = GASolver.repair_offspring
        self.k_tournament = k_tournament
        self.ga_instance = pygad.GA(num_generations=max_generations, num_parents_mating=int(self.population_size/2), fitness_func=self.objective_function, on_fitness=GASolver.on_fitness_assignemts, sol_per_pop=population_size, num_genes=len(self.encoding), init_range_low=self.earliest_slot, init_range_high=self.last_slot, parent_selection_type=self.parent_selection_type, keep_parents=self.keep_parents, crossover_type=self.crossover_type, mutation_type=self.mutation_type, mutation_percent_genes=self.mutation_percentage_genes, gene_type=self.gene_type, gene_space=self.gene_space, K_tournament=self.k_tournament, on_generation=GASolver.on_generation, on_crossover=on_crossover, on_mutation=on_mutation)#, parallel_processing=parallel_processing)
        self.best_solution = None

    # maybe do on crossover?
    def repair_offspring(ga_instance, offsprings): # NOTE: weird explanation in pygad docs
        instance = GASolver.instance
        if instance.repair:
            for offspring in offsprings:
                # repair the offspring (overlaps)
                w_sortings : list[list[int]] = []
                #TODO: test
                for workstation in instance.production_environment.workstations.keys():
                    w_sortings.append([])
                    for i in range(0, len(offspring), 2):
                        if offspring[i] == int(workstation):
                            w_sortings[-1].append(i)
                    w_sortings[-1].sort(key= lambda x: offspring[x+1])
                """for i in range(len(instance.production_environment.workstations.keys())):
                    w_sortings.append([])
                for i in range(0, len(offspring), 2):
                    if len(w_sortings[offspring[i]]) == 0:
                        w_sortings[offspring[i]].append(i)
                    else:
                        for j in range(len(w_sortings[offspring[i]])):
                            index = w_sortings[offspring[i]][j]
                            if offspring[i+1] < offspring[index+1]:
                                w_sortings[offspring[i]].insert(w_sortings[offspring[i]].index(index), i)
                                break
                            elif offspring[i+1] == offspring[index+1]:
                                # NOTE: maybe it should be inserted after, maybe even randomized
                                w_sortings[offspring[i]].insert(w_sortings[offspring[i]].index(index), i)
                                break # something"""
                for w in w_sortings:
                    # fix if overlap found
                    # in theory overlaps should only be able to occur on the workstations, not for the sequences
                    for i in range(1, len(w)):
                        index = w[i]
                        lb_sequence = 0
                        if not instance.is_first(int(index/2)): # NOTE: inefficient
                            # gather ending time of previous in sequence
                            lb_sequence = offspring[index-1]
                        lb_workstation = 0
                        #prev_start = offspring[index-1]
                        lb_workstation = offspring[w[i-1]+1] + instance.production_environment.get_workstation(offspring[w[i-1]]).get_duration(instance.jobs[int(w[i-1]/2)].task)
                        offspring[index+1] = max(offspring[index+1], max(lb_sequence, lb_workstation)) #NOTE: could use min to force tighter schedules, probably bad for robustness optimization

    def on_generation(ga_instance):
        if GASolver.instance.verbose and ga_instance.generations_completed % 100 == 0:
            print(f'Generation {ga_instance.generations_completed}, Current Best: {GASolver.instance.best_history[-1]}')

    def determine_gene_space(self, index : int) -> tuple[int,int]:
        lower_bound = self.earliest_slot
        upper_bound = self.last_slot
        if not self.is_first(int(index/2)):
        #if not index == 0 and (self.jobs[int((index-2)/2)].order == self.jobs[int((index)/2)].order):
            previous_job = self.jobs[int((index-2)/2)]
            previous_duration = max(self.durations[int(previous_job.task.id)])
            lower_bound = lower_bound + previous_duration
        min_buffer = 0#self.get_longest_duration(int(index/2))
        j = index#+2
        while int(j/2) < len(self.jobs) and self.jobs[int(j/2)].order == self.jobs[int(index/2)].order:
            min_buffer += self.get_longest_duration(int(j/2))
            j+=2
        upper_bound = upper_bound - min_buffer
        return lower_bound, upper_bound

    def run(self) -> None:
        self.ga_instance.run()
        solution, solution_fitness, solution_idx = self.ga_instance.best_solution()
        self.solution_index = solution_idx
        self.best_solution = (solution, solution_fitness)
        print("Done")

    def get_best(self) -> list[int]:
        return self.best_solution[0]

    def get_best_fitness(self) -> int:
        return self.best_solution[1]

    def get_result_jobs(self) -> list[int]:
        return self.jobs

    def mutation_function(offsprings : list[list[int]], ga_instance) -> list[list[int]]:
        instance : GASolver = GASolver.instance
        index = 0
        for offspring in offsprings:
            p = 1 / (len(offspring)/2) # amount of jobs
            for i in range(0, len(offspring), 2):
                if random.random() < p:
                    # mutate workstation assignment
                    workstations = instance.production_environment.get_available_workstations_for_task(instance.jobs[int(i/2)].task)
                    offspring[i] = random.choice(workstations).id
                    # mutate start time
                    offspring[i+1] = random.randint(instance.earliest_slot, instance.last_slot)
            index += 1
        return offsprings
    
    def has_overlaps(self, offspring : list[int], i : int, start_time : int, end_time : int) -> bool:
        instance : GASolver = GASolver.instance
        for j in range(0, len(offspring), 2):
                if not i == j:
                    if offspring[i] == offspring[j]: # tasks run on the same workstation
                        other_job = instance.jobs[int(j/2)]
                        own_start = start_time
                        other_start = offspring[j+1]
                        other_duration = instance.durations[int(other_job.task.id)][offspring[j]]
                        own_end = end_time
                        other_end = other_start + other_duration
                        if own_start >= other_start and own_start < other_end:
                            return True
                        if own_end > other_start and own_end <= other_end:
                            return True
                        if other_start >= own_start and other_start < own_end:
                            return True
                        if other_end > own_start and other_end <= own_end:
                            return True
        return False

    def only_feasible_mutation(offsprings : list[list[int]], ga_instance) -> list[list[int]]:
        instance : GASolver = GASolver.instance
        for offspring in offsprings:
            p = 1 / (len(offspring)/2)
            for i in range(0, len(offspring), 2):
                if random.random() < p:
                    workstations = instance.production_environment.get_available_workstations_for_task(instance.jobs[int(i/2)].task)
                    offspring[i] = random.choice(workstations).id
                    # choose random start time until fitting spot is found, or amount of tries is up
                    tries = 10000
                    start_time = random.randint(instance.earliest_slot, instance.last_slot)
                    duration = instance.durations[int(instance.jobs[int(i / 2)].task.id)][offspring[i]]
                    end_time = start_time + duration
                    current_try = 0
                    while current_try < tries and instance.has_overlaps(offspring, i, start_time, end_time):
                        start_time = random.randint(instance.earliest_slot, instance.last_slot)
                        end_time = start_time + duration
                        current_try += 1
                    offspring[i+1] = start_time
        return offsprings

    def get_order_index(self, index : int) -> int: # NOTE: should probably be replaces
        return int(self.jobs[int(index/2)].order.id)

    def is_first(self, index : int) -> bool:
        return index == 0 or self.jobs[index].order != self.jobs[index-1].order
    
    def get_longest_duration(self, job_index : int) -> int:
        return max(self.durations[int(self.jobs[job_index].task.id)])
            
    def force_feasible_mutation(offsprings : list[list[int]], ga_instance) -> list[list[int]]: #NOTE: does not guarantee no overlaps, just valid workstations + valid sequence
        instance = GASolver.instance
        for offspring in offsprings:
            if instance.random_until_feasible and instance.best_history[-1] == float('inf'):
                p = 1
            else:
                p = (1 / (len(offspring)))# + (ga_instance.generations_completed / ga_instance.num_generations)
            for i in range(0, len(offspring), 2):
                if random.random() < p:
                    # mutate workstation
                    workstations = instance.production_environment.get_available_workstations_for_task(instance.jobs[int(i/2)].task)
                    offspring[i] = int(random.choice(workstations).id)
                    # mutate start time
                    lower_bound = instance.earliest_slot
                    upper_bound = instance.last_slot
                    previous_duration = 0
                    if not instance.is_first(int(i/2)):
                    #if not i == 0 and (instance.jobs[int((i-2)/2)].order == instance.jobs[int(i/2)].order):
                        previous_job = instance.jobs[int((i-2)/2)]
                        previous_duration = instance.durations[int(previous_job.task.id)][offspring[i-2]]
                        lower_bound = offspring[i-1] + previous_duration # end of the previous job in the sequence
                    min_buffer = 0#instance.durations[int(instance.jobs[int(i/2)].id)][offspring[i]] # leave at least enough space for the duration of the task
                    j = i#+2
                    while int(j/2) < len(instance.jobs) and instance.jobs[int(j/2)].order == instance.jobs[int(i/2)].order:
                        min_buffer += instance.get_longest_duration(int(j/2))
                        j+=2
                    upper_bound -= min_buffer
                    #TODO: temporary to avoid multiple restarts
                    offspring[i+1] = random.randint(min(lower_bound, upper_bound), max(lower_bound, upper_bound))
                    #offspring[i+1] = random.randint(lower_bound, upper_bound)
        return offsprings

    def alternative_mutation_function(offsprings : list[list[int]], ga_instance) -> list[list[int]]:
        instance = GASolver.instance
        for offspring in offsprings:
            prev_order = -1
            current_order = 0
            p = 1 / (len(offspring)/2)
            for i in range(0, len(offspring), 2):
                current_order = instance.get_order_index(i)
                if random.random() < p:
                    # adjust workstation
                    workstations = instance.production_environment.get_available_workstations_for_task(instance.jobs[int(i/2)].task)
                    offspring[i] = random.choice(workstations).id
                # adjust start time for all, independent of workstation assignment mutation
                min_time_previous_job = 0
                if prev_order == current_order:
                    min_time_previous_job = offspring[i-1] + instance.durations[int(instance.jobs[int((i-2)/2)].task.id)][offspring[i-2]] # end of previous task in the same order
                min_time_workstation = -1
                current_duration = instance.durations[int(instance.jobs[int((i-1)/2)].task.id)][offspring[i]]
                # gather all jobs currently assigned to the same workstation
                assignments = []
                for j in range(0, i, 2): # NOTE: maybe needs to consider ALL jobs <start time, end time>
                    if offspring[j] == offspring[i]:
                        assignments.append([offspring[j+1], offspring[j+1] + instance.durations[int(instance.jobs[int(j/2)].task.id)][offspring[j]]])
                # find first slot big enough to fit the job
                if len(assignments) > 1: # if more than one job is on the same workstation, find first fitting slot
                    for j in range(1, len(assignments)):
                        if assignments[j][0] - assignments[j-1][1] >= current_duration and assignments[j-1][1] >= min_time_previous_job:
                            min_time_workstation = assignments[j-1][1]
                            break
                    if min_time_workstation == -1: # this should only be the case if there is no free slot in between, so put it at the end
                        min_time_workstation = assignments[len(assignments)-1][1] # set to end of the last assigned job
                elif len(assignments) == 1: # if only only one other job is on the same workstation, set to end of that job
                    min_time_workstation = assignments[0][1]
                else:
                    min_time_workstation = 0 # no other jobs on the same workstation, can start at 0
                offspring[i+1] = max(min_time_previous_job, min_time_workstation) # max between the two is the first feasible slot for the job
                prev_order = current_order
        return offsprings

    def on_fitness_assignemts(ga_instance, population_fitness) -> None:
        instance = GASolver.instance
        current_best = abs(sorted(population_fitness, reverse=True)[0]) - 1
        if len(instance.best_history) == 0:
            instance.best_history.append(current_best)
        elif current_best < instance.best_history[len(instance.best_history)-1]:
            instance.best_history.append(current_best)
        else:
            instance.best_history.append(instance.best_history[len(instance.best_history)-1])
        sum = 0
        for individual_fitness in population_fitness:
            sum += abs(individual_fitness)-1
        instance.average_history.append(sum/len(population_fitness))

    def fitness_function(solution : list[int], solution_idx) -> int:#def fitness_function(ga_instance, solution : list[int], solution_idx) -> int:
        if GASolver.instance.memory.get(solution.tostring()):
            GASolver.instance.memory_duplicate += 1
            return GASolver.instance.memory[solution.tostring()]
        if not GASolver.is_feasible(solution):
            #return - (2 * GASolver.instance.last_slot)
            GASolver.instance.memory[solution.tostring()] = -float('inf')
            return -float('inf')
        # for testing purposes
        #fitness = (max(solution[1::2]) - min(solution[1::2]))
        instance = GASolver.instance
        schedule : Schedule = instance.encoder.decode(solution, instance.jobs, instance.production_environment, [], instance)
        fitness = instance.evaluator.evaluate(schedule, instance.jobs)[0] # only do single objective for now
        instance.memory[solution.tostring()] = -fitness
        return -fitness

    def get_order(self, index : int) -> Order:
        return self.jobs[int(index/2)].order

    def is_feasible(solution : list[int]) -> bool:
        order = None
        instance : GASolver = GASolver.instance
        for i in range(0, len(solution), 2): # go through all workstation assignments
            job = instance.jobs[int(i/2)]
            # check for last time slot
            if solution[i+1] + instance.durations[int(job.task.id)][solution[i]] > instance.last_slot:
                return False
            # check for earliest time slot
            if solution[i+1] < instance.earliest_slot:
                return False
            # check for overlaps
            for j in range(i, len(solution), 2):
                if not i == j:
                    if solution[i] == solution[j]: # tasks run on the same workstation
                        other_job = instance.jobs[int(j/2)]
                        own_start = solution[i+1]
                        other_start = solution[j+1]
                        own_duration = instance.durations[int(job.task.id)][solution[i]]
                        other_duration = instance.durations[int(other_job.task.id)][solution[j]]
                        own_end = own_start + own_duration
                        other_end = other_start + other_duration
                        if own_start >= other_start and own_start < other_end:
                            return False
                        if own_end > other_start and own_end <= other_end:
                            return False
                        if other_start >= own_start and other_start < own_end:
                            return False
                        if other_end > own_start and other_end <= own_end:
                            return False
            # check for correct sequence
            prev_order = order
            order = instance.get_order(i) # find order corresponding to task
            if order:
                if not prev_order is None and order == prev_order: # if current task is not the first job of this order, check if the previous job ends before the current one starts
                    prev_start = solution[i-1]
                    prev_end = prev_start + instance.durations[int(instance.jobs[int((i-2)/2)].task.id)][solution[i-2]]
                    if solution[i+1] < prev_end:
                        return False
            else:
                print("Something went completely wrong!") # TODO: should probably throw exception
        return True

class GreedyAgentSolver(Solver):

    instance = None

    def __init__(self, encoding, durations, job_list, environment, orders):
        super().__init__('Greedy Agent', environment, SimpleGAEncoder())
        self.name = "GreedyAgentSolver"
        self.encoding = encoding
        self.durations = durations
        self.jobs = job_list
        self.orders = orders

        self.assignments_best = []
        self.average_assignments = []
        GreedyAgentSolver.instance = self

    def initialize(self):
        pass

    def get_order_index(self, index : int) -> int:
        job_index = int(index/2)
        sum = 0
        index = 0
        for order in self.orders:
            recipe : Recipe = order.resources[0][0].recipes[0]
            if job_index < sum + len(recipe.tasks):
                return index
            sum += len(recipe.tasks)
            index += 1
        return len(self.orders) -1

    def run(self, output : bool = True):
        result = len(self.encoding) * [-1]
        prev_order = -1
        for i in range(0, len(result), 2):
            current_order = self.get_order_index(i)
            workstation_options = []
            for j in range(len(self.durations[int(self.jobs[int(i/2)].task.id)])):
                if self.durations[int(self.jobs[int(i/2)].task.id)][j] != 0:
                    duration = self.durations[int(self.jobs[int(i/2)].task.id)][j] # save workstation with duration
                    tasks_on_workstation = []
                    for k in range(0, i, 2):
                        if j == result[k]:
                            tasks_on_workstation.append([k, result[k+1], result[k+1] + self.durations[int(self.jobs[int(k/2)].task.id)][result[k]]]) # save index, start time and end time, probably don't need index
                    tasks_on_workstation.sort(key=lambda x:x[1]) # sort by start time
                    # find gaps
                    for k in range(1, len(tasks_on_workstation)):
                        if tasks_on_workstation[k][1] - tasks_on_workstation[k-1][2] >= duration:
                            workstation_options.append((j, tasks_on_workstation[k-1][2])) # save workstation + end of previous task
                    if len(tasks_on_workstation) > 0:
                        workstation_options.append((j, tasks_on_workstation[-1][2])) # add the workstation + end of the current last task on the workstation as option
                    else:
                        workstation_options.append((j, 0)) # first task on this workstation
            # workstation_options should contain all viable slots for the current task
            # remove all slots that would invalidate the sequence of an order
            if prev_order == current_order:
                prev_start = result[i-1]
                prev_end = prev_start + self.durations[int(self.jobs[int((i-2)/2)].task.id)][result[i-2]]
                workstation_options = [(option[0], prev_end) if option[1] < prev_end else option for option in workstation_options ] # should remove every starting slot before prev_end
            # at this point, workstation_option should only contain valid possible starting slots for the current task
            # evaluate all options to find options with the smallest impact on makespan
            # create solutions:
            """solutions = []
            for option in workstation_options:
                solution = deepcopy(result)
                solution[i] = option[0]
                solution[i+1] = option[1]
                solutions.append(solution)"""
            
            best_makespan = []
            for option in workstation_options:
                test_solution = deepcopy(result) # slow
                test_solution[i] = option[0] # workstation
                test_solution[i+1] = option[1] # start time slot
                test_fitness = self.makespan(test_solution)
                if len(best_makespan) == 0 or test_fitness <= best_makespan[0][1]:
                    if len(best_makespan) > 0 and test_fitness < best_makespan[0][1]:
                        best_makespan = []
                    best_makespan.append((test_solution, test_fitness))
            # TODO: if more than one best solution, evaluate secondary objective, or choose randomly
            best_idle = [] # copy.deepcopy(best_makespan)
            for option in best_makespan:
                test_solution = deepcopy(option[0]) # slow
                test_fitness = self.idle_time(test_solution)
                if len(best_idle) == 0 or test_fitness <= best_idle[0][1]:
                    if len(best_idle) > 0 and test_fitness < best_idle[0][1]:
                        best_idle = []
                    best_idle.append((test_solution, test_fitness))
            # choose randomly from all best_idle solutions
            result = deepcopy(random.choice(best_idle))[0] # choose randomly for now
            prev_order = current_order
        self.best_solution = (result, self.makespan(result))
        if output:
            print("Done")
    
    def find_best(self, solutions) -> tuple[list[int], list[float]]:
        results : list[list[float]] = []
        best : list[float] = None
        best_solution : list[int] = []
        alternatives = []
        for solution in solutions:
            schedule : Schedule = self.encoder.decode(solution, self.jobs, self.production_environment, [], self)
            result = self.evaluator.evaluate(schedule)
            results.append(result)
            if not best:
                best = result
                best_solution = deepcopy(solution)
            else:
                success = False
                for i in range(len(result)):
                    if result[i] < best[i]:
                        best = result
                        best_solution = solution
                        success = True
                        break
                    elif result[i] > best[i]:
                        success = True
                        break
                if not success: # equal solution
                    alternatives.append((solution, result))
        if len(alternatives) > 0:
            alternatives.append((best_solution, best))
            solution = random.choice(alternatives)
            best_solution = solution[0]
            best = solution[1]
        return best_solution, best

    def makespan(self, solution):
        min = float('inf')
        max = 0
        for i in range(0, len(solution), 2):
            if solution[i] != -1:
                if solution[i+1] < min:
                    min = solution[i+1]
                if solution[i+1] + self.durations[int(self.jobs[int(i/2)].task.id)][solution[i]] > max:
                    max = solution[i+1] + self.durations[int(self.jobs[int(i/2)].task.id)][solution[i]]
        return max - min
    
    def idle_time(self, solution):
        result = 0
        for workstation in self.production_environment.workstations.values():
            id = workstation.id
            on_workstation = []
            # get all start and end times on workstation:
            for i in range(0, len(solution), 2):
                if solution[i] == id:
                    start = solution[i+1]
                    end = start + self.durations[int(self.jobs[int(i/2)].task.id)][id]
                    on_workstation.append((start, end))
            on_workstation.sort(key= lambda x:x[0]) # sort by start times
            for i in range(1, len(on_workstation)):
                result += on_workstation[i][0] - on_workstation[i-1][1]
        return result

    def get_best(self):
        return self.best_solution[0]

    def get_best_fitness(self):
        return self.best_solution[1]

class Particle:

    def __init__(self):
        self.best_positions : list[int] = []
        self.best_fitness : float = float('inf')
        self.velocities : list[float] = []
        self.current_positions : list[int] = []
        self.current_fitness : float = float('inf')

    def update(self) -> None:
        if self.current_fitness < self.best_fitness or math.isinf(self.best_fitness):
            self.best_positions = deepcopy(self.current_positions)
            self.best_fitness = self.current_fitness

class PSOSolver(Solver):

    def __init__(self, production_environment : ProductionEnvironment, encoder : Encoder = None, jobs : list[Job] = [], durations = dict(), start_time = 0, end_time = 1000, orders : list[Order] = []):
        super().__init__('PSO Solver', production_environment, encoder)
        self.jobs = jobs
        self.durations = durations
        self.end_time = end_time
        self.start_time = start_time
        self.orders = orders

    def initialize(self, dimensions : int = 10, lower_bounds : list[int] = None, upper_bounds : list[int] = None, particle_amount : int = 50, max_iterations : int = 25000, personal_weight : float = 2, global_weight : float = 2, inertia : float = 0.8, max_velocity : float = None, min_velocity : float = None, min_workstation_mutation_probability : float = 1.0, update_weights :bool = True, use_alternative : bool = False):
        self.dimensions = dimensions
        self.lower_bounds = lower_bounds
        self.upper_bounds = upper_bounds
        self.best = None
        self.particle_amount = particle_amount
        self.max_iterations = max_iterations
        self.personal_weight = personal_weight
        self.global_weight = global_weight
        self.inertia = inertia
        self.max_velocity = max_velocity
        self.min_velocity = min_velocity
        self.min_workstation_mutation_probability = min_workstation_mutation_probability
        self.swarm : list[Particle] = []
        self.update_weights = update_weights
        self.alternative = use_alternative


    def get_best_particle(self) -> Particle:
        best = self.swarm[0]
        for particle in self.swarm:
            if particle.best_fitness < best.best_fitness:
                best = particle
        return best

    def create_particle(self, jobs : list[Job]) -> Particle:
        particle : Particle = Particle()
        for i in range(self.dimensions):
            if i % 2 == 0:
                # workstation NOTE: currently ensures starting population uses only allowed workstations
                workstations = self.production_environment.get_available_workstations_for_task(jobs[int(i/2)].task)
                particle.current_positions.append(int(random.choice(workstations).id))
            else:
                # start time
                particle.current_positions.append(random.randint(self.lower_bounds[i], self.upper_bounds[i]))
            particle.velocities.append(0.0)
        return particle
    
    def create_particle_alternative(self, jobs : list[Job]) -> Particle:
        # NOTE: requires lower and upper bounds to contain amounts of workstations for each job
        particle : Particle = Particle()
        for i in range(self.dimensions):
            particle.current_positions.append(random.randint(self.lower_bounds[i], self.upper_bounds[i]))
            particle.velocities.append(0.0) # NOTE: velocities should be randomized initially
        return particle

    def get_order(self, index : int) -> Order: # NOTE: should probably be replaces
        return self.jobs[int(index/2)].order

    def is_feasible(self, particle : Particle) -> bool: # TODO
        solution = particle.current_positions
        order = None
        for i in range(0, len(solution), 2): # go through all workstation assignments
            job = self.jobs[int(i/2)]
            # check for last time slot
            if solution[i+1] + self.durations[int(job.task.id)][solution[i]] > self.end_time: #TODO: durations, end time
                return False
            # check for earliest time slot
            if solution[i+1] < self.start_time: #TDOO: start time
                return False
            # check for overlaps
            for j in range(0, len(solution), 2):
                if not i == j:
                    if solution[i] == solution[j]: # tasks run on the same workstation
                        other_job = self.jobs[int(j/2)]
                        own_start = solution[i+1]
                        other_start = solution[j+1]
                        own_duration = self.durations[int(job.task.id)][solution[i]]
                        other_duration = self.durations[int(other_job.task.id)][solution[j]]
                        own_end = own_start + own_duration
                        other_end = other_start + other_duration
                        if own_start >= other_start and own_start < other_end:
                            return False
                        if own_end > other_start and own_end <= other_end:
                            return False
                        if other_start >= own_start and other_start < own_end:
                            return False
                        if other_end > own_start and other_end <= own_end:
                            return False
            # check for correct sequence
            prev_order = order
            order = self.get_order(i) # find order corresponding to task # TODO: get_order
            if order:
                if not prev_order is None and order == prev_order: # if current task is not the first job of this order, check if the previous job ends before the current one starts
                    prev_start = solution[i-1]
                    prev_end = prev_start + self.durations[int(self.jobs[int((i-2)/2)].task.id)][solution[i-2]]
                    if solution[i+1] < prev_end:
                        return False
            else:
                print("Something went completely wrong!") # TODO: should probably throw exception
        return True

    def evaluate(self, particle : Particle) -> None:
        if not self.is_feasible(particle):
            particle.current_fitness = float('inf')
        else:
            values = particle.current_positions
            if self.alternative:
                values = []
                for i in range(len(particle.current_positions)):
                    if i % 2 == 0:
                        values.append(self.translate_to_workstation_id(particle, i))
                    else:
                        values.append(particle.current_positions[i])
            schedule : Schedule = self.encoder.decode(values, self.jobs, self.production_environment)
            fitness = self.evaluator.evaluate(schedule, self.jobs)[0] # single objective for now
            particle.current_fitness = fitness
        particle.update()

    def evaluate_swarm(self) -> None:
        for particle in self.swarm:
            self.evaluate(particle)

    def translate_to_workstation_id(self, particle, index):
        return int(self.production_environment.get_available_workstations_for_task(self.jobs[int(index/2)].task)[particle.current_positions[index]].id)

    def move_swarm_alternative(self) -> None:
        for particle in self.swarm:
            for i in range(self.dimensions):
                r_personal = random.uniform(0, 1)
                r_global = random.uniform(0, 1)
                velocity = self.inertia * particle.velocities[i] + self.personal_weight * r_personal * (particle.best_positions[i] - particle.current_positions[i]) + self.global_weight * r_global * (self.current_best.best_positions[i] - particle.current_positions[i])
                if self.max_velocity and velocity > self.max_velocity:
                    velocity = self.max_velocity
                if self.min_velocity and velocity < self.min_velocity:
                    velocity = self.min_velocity
                particle.current_positions[i] += velocity
                particle.velocities[i] = velocity
                if particle.current_positions[i] > self.upper_bounds[i]:
                    particle.current_positions[i] = self.upper_bounds[i]
                if particle.current_positions[i] < self.lower_bounds[i]:
                    particle.current_positions[i] = self.lower_bounds[i]
                particle.current_positions[i] = int(particle.current_positions[i])

    def move_swarm(self) -> None:
        for particle in self.swarm:
            for i in range(self.dimensions):
                if i % 2 == 0:
                    # mutate workstations
                    """
                    workstations = self.production_environment.get_available_workstations_for_task(self.jobs[int(i/2)].task)
                    probabilities = [1.0/len(workstations)] * len(workstations)
                    p_sum = 0
                    for j in len(workstations):
                        workstation = workstations[j]
                        if particle.best_positions[j] == int(workstation.id):
                            probabilities[j] += probabilities[j] * personal_weight # maybe use separate parameters
                        if current_best.best_positions[j] == int(workstation.id):
                            probabilities[j] += probabilities[j] * global_weight
                        p_sum += probabilities[j]
                    r = random.uniform(0.0, p_sum)
                    p_sum = 0
                    for j in len(probabilities):
                        p_sum += probabilities[j]
                        if p_sum >= r:
                            particle.current_positions[i] = workstations[j]
                            break
                    """
                    if random.random() < self.min_workstation_mutation_probability:
                        workstations = self.production_environment.get_available_workstations_for_task(self.jobs[int(i/2)].task)
                        particle.current_positions[i] = int(random.choice(workstations).id)
                else:
                    # mutate start time
                    r_personal = random.uniform(0, 1)
                    r_global = random.uniform(0, 1)
                    velocity = self.inertia * particle.velocities[i] + self.personal_weight * r_personal * (particle.best_positions[i] - particle.current_positions[i]) + self.global_weight * r_global * (self.current_best.best_positions[i] - particle.current_positions[i])
                    if self.max_velocity and velocity > self.max_velocity:
                        velocity = self.max_velocity
                    if self.min_velocity and velocity < self.min_velocity:
                        velocity = self.min_velocity
                    particle.current_positions[i] += velocity
                    particle.velocities[i] = velocity
                    if particle.current_positions[i] > self.upper_bounds[i]:
                        particle.current_positions[i] = self.upper_bounds[i]
                    if particle.current_positions[i] < self.lower_bounds[i]:
                        particle.current_positions[i] = self.lower_bounds[i]
                    particle.current_positions[i] = int(particle.current_positions[i]) # clip to integers

    def adjust_weights(self, iteration):
        t = iteration
        n = self.max_iterations
        # TODO: remove magic numbers
        self.inertia = (0.4/n**2) * (t - n) ** 2 + 0.4
        self.personal_weight = - 3 * t / n + 3.5
        self.global_weight = 3 * t / n + 0.5

    def update_history(self):
        self.best_history.append(self.current_best.best_fitness)
        average_fitness = 0
        average_best_fitness = 0
        for particle in self.swarm:
            average_fitness += particle.current_fitness
            average_best_fitness += particle.best_fitness
        self.average_swarm_history.append(average_fitness / len(self.swarm))
        self.average_best_history.append(average_best_fitness / len(self.swarm))

    def run(self) -> Particle:
        self.best_history = []
        self.average_best_history = []
        self.average_swarm_history = []
        for _ in range(self.particle_amount):
            if self.alternative:
                particle : Particle = self.create_particle_alternative(self.jobs)
            else:
                particle : Particle = self.create_particle(self.jobs)
            #self.evaluate(particle)
            self.swarm.append(particle)
        self.evaluate_swarm()
        for iteration in range(self.max_iterations):
            self.current_best = self.get_best_particle()
            self.update_history()
            if self.alternative:
                self.move_swarm_alternative()
            else:
                self.move_swarm()
            self.evaluate_swarm()
            #TODO: maybe adjust parameters over time
            if self.update_weights:
                self.adjust_weights(iteration)
        self.current_best = self.get_best_particle()
        self.best = self.current_best
        return self.current_best

    def get_best(self):
        values = self.best.best_positions
        if self.alternative:
            values = []
            for i in range(len(self.best.best_positions)):
                if i % 2 == 0:
                    w_id = int(self.production_environment.get_available_workstations_for_task(self.jobs[int(i/2)].task)[self.best.best_positions[i]].id)
                    values.append(w_id)
                else:
                    values.append(self.best.best_positions[i])
        return self.best.best_positions
    
    def get_best_fitness(self):
        return self.best.best_fitness

class NestedGA(Solver):

    def __init__(self):
        # outer solver > workstation assignment
        # inner solver > start times
        NestedGA.instance = self
        pass

    def initialize(self, inner_solver : str = 'pso', inner_parameters : dict[str,] = dict()):
        if inner_solver == 'pso':
            pass
        elif inner_solver == 'ga':
            pass
        elif inner_solver == 'hs':
            pass
        else:
            pass
        self.outer_solver = pygad.GA()
        self.inner_solver = pygad.GA()

    def evaluate(solution):
        instance = NestedGA.instance
        result, result_fitness = instance.inner_solver.run(solution)
        instance.inner_solver.run(solution)
        inner_solution, inner_solution_fitness, inner_solution_idx = instance.inner_solver.best_solution()
        return result_fitness

    def run(self):
        # run outer solver
        pass

class StagedGA(Solver):
    
    def __init__(self, production_environment : ProductionEnvironment):
        # first solver > workstation assignment (balance load)
        # second solver > start times
        super().__init__('StagedGA', production_environment, SimpleGAEncoder())
        self.best_history = []
        self.average_history = []
        StagedGA.instance = self

    def initialize(self, encoding : list[int], jobs : list[Job], durations, start_time : int = 0, end_time : int = 1000):
        # TODO: obviously add all parameters 
        max_generations = 1000
        population_size = 50
        offspring_amount = 100
        self.jobs = jobs
        self.encoding = encoding
        first_encoding = encoding[::2]
        second_encoding = encoding[1::2]
        self.earliest_slot = start_time
        self.last_slot = end_time
        self.durations = durations
        self.gene_space = []
        for job in self.jobs:
            possibilities = self.production_environment.get_available_workstations_for_task(job.task)
            possible_ids = [int(x.id) for x in possibilities]
            self.gene_space.append(possible_ids)
        self.stage_one = pygad.GA(num_generations=max_generations, num_parents_mating=int(population_size/2), fitness_func=StagedGA.evaluate_load, on_fitness=StagedGA.on_fitness_assignemts, sol_per_pop=population_size, num_genes=len(first_encoding), parent_selection_type='tournament', keep_parents=0, crossover_type='two_points', mutation_type='random', mutation_percent_genes=10, gene_type=int, gene_space=self.gene_space, K_tournament=int(population_size/4))
        self.gene_space = []
        max_generations = 2000
        for i in range(len(second_encoding)):
            self.gene_space.append({'low': self.earliest_slot, 'high': self.last_slot})
        self.stage_two = pygad.GA(num_generations=max_generations, num_parents_mating=int(population_size/2), fitness_func=StagedGA.evaluate_start_times, on_fitness=StagedGA.on_fitness_assignemts, sol_per_pop=population_size, num_genes=len(second_encoding), parent_selection_type='tournament', keep_parents=0, crossover_type='two_points', mutation_type='random', mutation_percent_genes=10, gene_type=int, gene_space=self.gene_space, K_tournament=int(population_size/4))

    def evaluate_load(solution : list[int], solution_idx) -> int:
        instance = StagedGA.instance
        loads = [0] * len(instance.production_environment.workstations.keys())
        for i in range(len(solution)):
            loads[solution[i]] += instance.durations[int(instance.jobs[i].task.id)][solution[i]]
        mean = sum(loads) / len(loads)
        var = sum((load - mean) ** 2 for load in loads) / len(loads)
        return -var

    def is_feasible(solution : list[int]) -> bool:
        order = None
        instance : StagedGA = StagedGA.instance
        for i in range(0, len(solution), 2): # go through all workstation assignments
            job = instance.jobs[int(i/2)]
            # check for last time slot
            if solution[i+1] + instance.durations[int(job.task.id)][solution[i]] > instance.last_slot:
                return False
            # check for earliest time slot
            if solution[i+1] < instance.earliest_slot:
                return False
            # check for overlaps
            for j in range(0, len(solution), 2):
                if not i == j:
                    if solution[i] == solution[j]: # tasks run on the same workstation
                        other_job = instance.jobs[int(j/2)]
                        own_start = solution[i+1]
                        other_start = solution[j+1]
                        own_duration = instance.durations[int(job.task.id)][solution[i]]
                        other_duration = instance.durations[int(other_job.task.id)][solution[j]]
                        own_end = own_start + own_duration
                        other_end = other_start + other_duration
                        if own_start >= other_start and own_start < other_end:
                            return False
                        if own_end > other_start and own_end <= other_end:
                            return False
                        if other_start >= own_start and other_start < own_end:
                            return False
                        if other_end > own_start and other_end <= own_end:
                            return False
            # check for correct sequence
            prev_order = order
            order = instance.get_order(i) # find order corresponding to task
            if order:
                if not prev_order is None and order == prev_order: # if current task is not the first job of this order, check if the previous job ends before the current one starts
                    prev_start = solution[i-1]
                    prev_end = prev_start + instance.durations[int(instance.jobs[int((i-2)/2)].task.id)][solution[i-2]]
                    if solution[i+1] < prev_end:
                        return False
            else:
                print("Something went completely wrong!") # TODO: should probably throw exception
        return True

    def get_order(self, index : int) -> Order:
        return self.jobs[int(index/2)].order

    def evaluate_start_times(solution : list[int], solution_idx) -> int:
        instance = StagedGA.instance
        values = []
        for i in range(len(solution)):
            values.append(instance.first_solution[i])
            values.append(solution[i])
        if not StagedGA.is_feasible(values): #TODO: replace
            return -float('inf')
        schedule : Schedule = instance.encoder.decode(values, instance.jobs, instance.production_environment, [], instance)
        results = instance.evaluator.evaluate(schedule, instance.jobs)
        return -results[0] # just use first for now

    def run(self):
        # run workstation assignment solver
        self.stage_one.run()
        self.first_solution, self.first_solution_fitness, self.first_solution_idx = self.stage_one.best_solution()
        # run start time solver
        self.stage_two.run()
        self.second_solution, self.second_solution_fitness, self.second_solution_idx = self.stage_two.best_solution()
        # create endresult
        result = []
        for i in range(len(self.first_solution)):
            result.append(self.first_solution[i])
            result.append(self.second_solution[i])
        self.best_solution = (result, self.second_solution_fitness)

    def get_best(self) -> list[int]:
        return self.best_solution[0]

    def get_best_fitness(self) -> int:
        return self.best_solution[1]
    
    def on_fitness_assignemts(ga_instance, population_fitness) -> None:
        instance = StagedGA.instance
        current_best = abs(sorted(population_fitness, reverse=True)[0]) - 1
        if len(instance.best_history) == 0:
            instance.best_history.append(current_best)
        elif current_best < instance.best_history[len(instance.best_history)-1]:
            instance.best_history.append(current_best)
        else:
            instance.best_history.append(instance.best_history[len(instance.best_history)-1])
        sum = 0
        for individual_fitness in population_fitness:
            sum += abs(individual_fitness)-1
        instance.average_history.append(sum/len(population_fitness))

class SequenceOrderGA(Solver):

    def __init__(self):
        # optimize job order, use greedy algorithm to determine start times and workstations

        SequenceOrderGA.instance = self
        pass

    def initialize(self):
        pass

    def run(self):
        pass

    def recombine(self):
        p1 = []
        p2 = []
        c = [p1[i] if random.random() < 0.5 else p2[i] for i in range(len(p1))]
        # repair sequence in created child

    def mutate(self):
        solution = []
        p = 1 / len(solution)
        production_environment = ProductionEnvironment()
        jobs = []
        #if mutate workstation, choose from available
        solution = [solution[i] if p < random.random() else random.choice(production_environment.get_available_workstations_for_task(jobs[int(i/2)])) for i in range(0, len(solution), 2)]
        #if mutate sequence on workstation, swap with random other on same workstation
        for i in range(1, len(solution), 1):
            if random.random() < p:
                indices = []
                for j in range(0, len(solution), 2):
                    if solution[i] == solution[j]:
                        indices.append(j+1)
                index = random.choice(indices)
                tmp = solution[i]
                solution[i] = solution[index]
                solution[index] = tmp
        # repair sequence in mutated individual

    def determine_start_times(self, solution : list[int]) -> list[int]:
        instance : SequenceOrderGA = SequenceOrderGA.instance
        result = solution.copy()
        on_workstations = []
        for workstation in len(instance.production_environment.get_workstation_list()):
            on_workstations.append([])
            for i in range(0,len(result), 2):
                if result[i] == workstation:
                    on_workstations[workstation].append(i)
        for workstation in on_workstations:
            workstation.sort(key=lambda x: solution[x+1])
            for i in range(len(workstation)):
                if i == 0:
                    result[workstation[i]+1] = 0
                else:
                    result[workstation[i]+1] = result[workstation[i-1]+1] + instance.production_environment.get_workstation(workstation[i]).get_duration(instance.jobs[int(i/2)].task)#TODO: duration result[workstation[i-1]+2]
        for i in range(0,len(result),2):
            if i > 0 and instance.jobs[int(i/2)].order == instance.jobs[int(i/2)-1].order:
                for w in on_workstations:
                    if i in w:
                        on_workstation = w
                        break
                for j in range(on_workstation.index(i), len(on_workstation)):
                    prev_end = result[i-1] + instance.production_environment.get_workstation(result[i-2]).get_duration(instance.jobs[int(i/2)-1].task)# TODO: duration result[i-1]
                    result[on_workstation[j]+1] = max(result[on_workstation[j]+1], prev_end)
        return result


import gurobipy as gp
class GurobiSolver(Solver):

    def __init__(self, production_environment : ProductionEnvironment):
        super().__init__('GurobiSolver', production_environment, GurobiEncoder())

    def initialize(self, nb_jobs, nb_operations, nb_machines, job_ops_machs, duration, job_op_suitable, L):
        self.job_ops_machs = job_ops_machs
        self.m = gp.Model('milp32')
        jobs = [j for j in range(1,nb_jobs+1)]
        job_ops = [(j+1,k+1) for j in range(nb_jobs) for k in range(nb_operations[j])] 
        machines = [m for m in range(1,nb_machines+1)]
        list_X_var = []
        for j, k in job_ops :
            if j < nb_jobs :
                for jp, kp in job_ops:
                    if jp > j:
                        list_X_var.append((j,k,jp,kp))
        Y = self.m.addVars(job_ops_machs, obj = 0.0, vtype=gp.GRB.BINARY, name ="Y")
        X = self.m.addVars(list_X_var, obj = 0.0, vtype=gp.GRB.BINARY, name ="X")
        C = self.m.addVars(job_ops,  obj = 0.0, lb = 0.0, vtype=gp.GRB.CONTINUOUS, name ="C")
        Cmax = self.m.addVar(obj = 1.0, name="Cmax")
        self.m.addConstrs((Y.sum(j,k,'*') == 1 for j, k in job_ops), "Y_const")

        self.m.addConstrs((Y.prod(duration,j,k,'*') <= C[j,k] for j, k in job_ops if k == 1),"C_time")

        self.m.addConstrs((Y.prod(duration,j,k,'*') + C[j,k-1] <= C[j,k] for j, k in job_ops if k != 1), "C_time")

        self.m.addConstrs((C[j,k] >= C[jp,kp] + duration[j,k,i] - L*(3 - X[j,k,jp,kp] - Y[j,k,i] - Y[jp,kp,i]) 
                        for j, k in job_ops if j < nb_jobs
                        for jp, kp in job_ops if jp > j 
                        for i in machines if i in job_op_suitable[j,k] if i in job_op_suitable[jp,kp]), "l1")
        self.m.addConstrs((C[jp,kp] >= C[j,k] + duration[jp,kp,i] - L*(X[j,k,jp,kp] + 2 - Y[j,k,i] - Y[jp,kp,i]) 
                    for j, k in job_ops if j < nb_jobs
                    for jp, kp in job_ops if jp > j 
                    for i in machines if i in job_op_suitable[j,k] if i in job_op_suitable[jp,kp]), "l2")
        
        self.m.addConstrs((Cmax>=C[j,nb_operations[j-1]] for j in jobs),"Cmax")
        self.X = X
        self.Y = Y
        self.C = C
        self.Cmax = Cmax

    def run(self):
        self.m.update()
        #self.m.display()
        self.m.optimize()

    def get_best(self):
        xsol = self.m.getAttr('X', self.X)
        ysol = self.m.getAttr('X', self.Y)
        csol = self.m.getAttr('X', self.C)
        return xsol, ysol, csol
        
    def get_best_fitness(self):
        return self.m.getAttr('X', self.C)
    
    def get_lower_bound(self):
        return self.m.LB
    

class GurobiNoMachineFlexibilitySolver(Solver):

    def __init__(self, production_environment : ProductionEnvironment):
        super().__init__('GurobiNoMachineFlexibilitySolver', production_environment, GurobiEncoder())

    def initialize(self, f):
        #self.job_ops_machs = job_ops_machs

        lines = f.readlines()
        first_line = lines[0].split()
        # Number of jobs
        nb_jobs = int(first_line[0])
        
        # Number of machines
        nb_machines = int(first_line[1])
        
        # Number of operations for each job
        nb_operations = [int(lines[j + 1].split()[0]) for j in range(nb_jobs)] 
        
        # Number of tasks
        nb_tasks = sum(nb_operations[j] for j in range(nb_jobs))

        self.m = gp.Model('milp_opt')
        """jobs = [j for j in range(1,nb_jobs+1)]
        job_ops = [(j+1,k+1) for j in range(nb_jobs) for k in range(nb_operations[j])] 
        machines = [m for m in range(1,nb_machines+1)]
        list_X_var = []
        for j, k in job_ops :
            if j < nb_jobs :
                for jp, kp in job_ops:
                    if jp > j:
                        list_X_var.append((j,k,jp,kp))"""
        #Duration
        job_op_mach__duration = {}
        #Suitable machines
        job_op__suitablemachines = {}
        #nb of Machines
        job_op__nb_machines = {}
        #Indexdarstellung der Job_Ops
        job_op__idx ={}
        
        # Constant for incompatible machines
        INFINITE = 1000000
        # Processing time for each task, for each machine
        task_processing_time = [[[INFINITE for m in range(nb_machines)] for o in range(nb_operations[j])] for j in range(nb_jobs)]
        idx = 0
        
        for j in range(nb_jobs):
            line = lines[j + 1].split()
            tmp = 0
            for o in range(nb_operations[j]):
                nb_machines_operation = int(line[tmp + o + 1])
                suitable_helper =[]
                for i in range(nb_machines_operation):
                    machine = int(line[tmp + o + 2 * i + 2])
                    time = int(line[tmp + o + 2 * i + 3])
                    task_processing_time[j][o][machine-1] = time
                    suitable_helper += [machine]
                    job_op_mach__duration[j+1,o+1,machine] = time
                    
                job_op__suitablemachines[j+1,o+1] = suitable_helper
                job_op__nb_machines[j+1,o+1] = nb_machines_operation
                job_op__tuple = tuple(job_op__nb_machines.keys())
                tmp = tmp + 2 * nb_machines_operation
        #list of jobs for creating Variables
        jobs = [j for j in range(1,nb_jobs+1)]
        
        #list of Job Operations for creating Variables
        job_ops = [(j+1,k+1) for j in range(nb_jobs) for k in range(nb_operations[j])] 
        
        #dict of selected machines
        job_op__mach = {}
        job_op__duration = {}
        for j, k in job_ops :
            #h = job_op__tuple.index((j,k)) 
            machine = job_op__suitablemachines[j,k][0]  # !!!! HIER: no machine flexibility
            job_op__mach[j,k] = machine
            job_op__duration[j,k] = job_op_mach__duration[j,k,machine]

        L = sum(job_op__duration[j,k] for j, k in job_ops)

        list_X_var = []
        for j, k in job_ops :
            if j < nb_jobs :
                for jp, kp in job_ops:
                    if jp > j:
                        if job_op__mach[j,k] == job_op__mach[jp,kp] :
                            list_X_var.append((j,k,jp,kp))
        
        X = self.m.addVars(list_X_var, obj = 0.0, vtype=gp.GRB.BINARY, name ="X")
        S = self.m.addVars(job_ops,  obj = 0.0, lb = 0.0, vtype=gp.GRB.CONTINUOUS, name ="S")
        Cmax = self.m.addVar(obj = 1.0, name="Cmax")
        self.m.addConstrs((S[j,k] >= S[j,k-1] + job_op__duration[j,k-1] 
                  for j, k in job_ops if k >= 2)
                 ,"Order")

        self.m.addConstrs((S[jp,kp] + job_op__duration[jp,kp] <= S[j,k] + L*(1 - X[j,k,jp,kp]) 
                  for j, k in job_ops if j < nb_jobs
                  for jp, kp in job_ops if jp > j 
                  if job_op__mach[j,k] == job_op__mach[jp,kp])
                 , "Mach1")

        self.m.addConstrs((S[j,k] + job_op__duration[j,k] <= S[jp,kp] + L*X[j,k,jp,kp]
                  for j, k in job_ops if j < nb_jobs
                  for jp, kp in job_ops if jp > j 
                  if job_op__mach[j,k] == job_op__mach[jp,kp])
                 , "Mach2")

        self.m.addConstrs((Cmax >= S[j,nb_operations[j-1]] + job_op__duration[j,nb_operations[j-1]] 
                  for j in jobs)
                 ,"Cmax")        
        #self.m.addConstrs((Cmax>=C[j,nb_operations[j-1]] for j in jobs),"Cmax")
        timelimit = 3600
        self.m.Params.TimeLimit = timelimit
        self.X = X
        self.S = S
        #self.C = C
        self.Cmax = Cmax

    def run(self):
        self.m.update()
        #self.m.display()
        self.m.optimize()

    def get_best(self):
        xsol = self.m.getAttr('X', self.X)
        ysol = self.m.getAttr('X', self.S)
        #csol = self.m.getAttr('X', self.C)
        return xsol, ysol, self.Cmax.X
        
    def get_best_fitness(self):
        return self.m.getAttr('X', self.C)
    
    def get_lower_bound(self):
        return self.m.LB # ObjBound?

class GurobiWithWorkerSolver(Solver):
    
    def __init__(self, production_environment : ProductionEnvironment = None):
        super().__init__('GurobiSolver (incl. Worker)', production_environment, GurobiEncoder())

    def initialize(self, nb_jobs, nb_operations, nb_machines, nb_workers, job_op_machsuitable, job_op_mach_worker, duration, job_op_mach_workersuitable, L):
        self.m = gp.Model('milp33')
        jobs = [j for j in range(1,nb_jobs+1)]
        job_ops = [(j+1,k+1) for j in range(nb_jobs) for k in range(nb_operations[j])] 
        machines = [m for m in range(1,nb_machines+1)]
        workers = [s for s in range(1,nb_workers+1)]
        list_X_var = []
        
        for j, k in job_ops :
            if j < nb_jobs :
                for jp, kp in job_ops:
                    if jp > j:
                        list_X_var.append((j,k,jp,kp)) 

        self.Y = self.m.addVars(job_op_mach_worker, obj = 0.0, vtype=gp.GRB.BINARY, name ="Y")
        self.X = self.m.addVars(list_X_var, obj = 0.0, vtype=gp.GRB.BINARY, name ="X")
        self.U = self.m.addVars(list_X_var, obj = 0.0, vtype=gp.GRB.BINARY, name ="U")
        self.C = self.m.addVars(job_ops,  obj = 0.0, lb = 0.0, vtype=gp.GRB.CONTINUOUS, name ="C")
        self.Cmax = self.m.addVar(obj = 1.0, name="Cmax")

        self.m.addConstrs((self.Y.sum(j,k,'*','*') == 1 for j, k in job_ops), "Y_const")
        self.m.addConstrs((self.Y.prod(duration,j,k,'*','*') <= self.C[j,k] for j, k in job_ops if k == 1),"C_time")
        self.m.addConstrs((self.Y.prod(duration,j,k,'*','*') + self.C[j,k-1] <= self.C[j,k] for j, k in job_ops if k != 1), "C_time")
        self.m.addConstrs((self.C[j,k] >= self.C[jp,kp] + duration[j,k,i,s] - L*(3 - self.X[j,k,jp,kp] - self.Y[j,k,i,s] - self.Y[jp,kp,i,sp]) 
                    for j, k in job_ops if j < nb_jobs
                    for jp, kp in job_ops if jp > j 
                    for i in machines if i in job_op_machsuitable[j,k] if i in job_op_machsuitable[jp,kp]
                    for s in workers if s in job_op_mach_workersuitable[j,k,i]
                    for sp in workers if sp in job_op_mach_workersuitable[jp,kp,i]) ,"l1_X")
        self.m.addConstrs((self.C[jp,kp] >= self.C[j,k] + duration[jp,kp,i,sp] - L*(self.X[j,k,jp,kp] + 2 - self.Y[j,k,i,s] - self.Y[jp,kp,i,sp]) 
                    for j, k in job_ops if j < nb_jobs
                    for jp, kp in job_ops if jp > j 
                    for i in machines if i in job_op_machsuitable[j,k] if i in job_op_machsuitable[jp,kp]
                    for s in job_op_mach_workersuitable[j,k,i]
                    for sp in job_op_mach_workersuitable[jp,kp,i]), "l2_X")
        self.m.addConstrs((self.C[j,k] >= self.C[jp,kp] + duration[j,k,i,s] - L*(3 - self.U[j,k,jp,kp] - self.Y[j,k,i,s] - self.Y[jp,kp,ip,s]) 
                    for j, k in job_ops if j < nb_jobs
                    for jp, kp in job_ops if jp > j
                    for i in machines if i in job_op_machsuitable[j,k]
                    for ip in machines if ip in job_op_machsuitable[jp,kp]
                    for s in workers if s in job_op_mach_workersuitable[j,k,i] if s in job_op_mach_workersuitable[jp,kp,ip]) ,"l1_U")
        self.m.addConstrs((self.C[jp,kp] >= self.C[j,k] + duration[jp,kp,ip,s] - L*(self.U[j,k,jp,kp] + 2 - self.Y[j,k,i,s] - self.Y[jp,kp,ip,s]) 
                    for j, k in job_ops if j < nb_jobs
                    for jp, kp in job_ops if jp > j
                    for i in machines if i in job_op_machsuitable[j,k]
                    for ip in machines if ip in job_op_machsuitable[jp,kp]
                    for s in workers if s in job_op_mach_workersuitable[j,k,i] if s in job_op_mach_workersuitable[jp,kp,ip]), "l2_U")
        self.m.addConstrs((self.Cmax>=self.C[j,nb_operations[j-1]] for j in jobs),"Cmax")

    def run(self):
        self.m.update()
        self.m.display()
        self.m.optimize()

    def get_best(self):
        xsol = self.m.getAttr('X', self.X)
        usol = self.m.getAttr('X', self.U)
        ysol = self.m.getAttr('X', self.Y)
        csol = self.m.getAttr('X', self.C)
        return xsol, usol, ysol, csol

# workstation, sequence, time window, second objective to minimize time window size

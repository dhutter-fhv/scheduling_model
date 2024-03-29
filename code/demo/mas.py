from solver import Solver
from models import SimulationEnvironment
from data_translator import GAToScheduleTranslator, DataTranslator
from objective_function import calculate_comparison_values

import multiprocessing as mp

class SolverWrapper:

    def __init__(self, solver : Solver = None):
        self.solver = solver

        
#def solve_parallel(solver : Solver, translator, jobs, env, orders, queue):
def solve_parallel(solver : Solver, translator : DataTranslator, jobs : list, env : SimulationEnvironment, orders : list, pipe):
    solver.run()
    result = solver.get_best()
    schedule = translator.translators[solver].translate(result, jobs, env, orders)
    schedule.created_by = solver
    schedule.created_in = env
    schedule.created_for = orders
    #queue.put([result, schedule])
    pipe.send([result, schedule])

class MAS:

    def __init__(self):
        self.solvers = []
        self.translators = dict()
        self.all_results = []

    def add_solver(self, solver : Solver, translator : DataTranslator = GAToScheduleTranslator()) -> None:
        #NOTE: solvers should be initialized and configured at this point
        self.solvers.append(solver)
        self.translators[solver] = translator

    def run(self, env : SimulationEnvironment = None, jobs : list = None, orders : list = None, parallel : bool = False) -> tuple:
        # setup
        results = []
        self.env = env
        self.jobs = jobs
        self.orders = orders
        # choose run method
        if parallel:
            results = self._run_parallel()
        else:
            results = self._run_sequential()
        schedules = []
        for result in results:
            # convert to schedules or already receive results as schedule from run methods
            # NOTE: currently run methods already convert results to schedules -> [0] -> actual result, [1] -> result as schedule
            # evaluate with multiple objective functions
            fitness_values = calculate_comparison_values(result[1], orders, env) # NOTE: should probably return array to make adding objectives easier
            schedules.append((result[1], fitness_values))
        # compare
        self.all_results = schedules
        fronts = []
        for _ in range(len(schedules[0][1])):
            fronts.append([])
        for i in range(len(schedules)):
            fronts[self.get_dominance(schedules, i)].append(schedules[i])
        best = None
        for i in range(len(fronts)):
            if len(fronts[i]) > 0:
                best = fronts[i]
        return best[0] # resulting schedule should contain information about orders, used solver and used environment, as well as all fitness values in [1]

    def get_dominance(self, solutions : list, index : int) -> int:
        # NOTE: assumes all objective functions try to minimize (not true for e.g. profit, but not really used currently so doesn't matter yet)
        solution = solutions[index]
        dominance = [True for _ in range(len(solution[1]))]
        for i in range(len(solutions)):
            if i != index:
                for j in range(len(solution[1])):
                    if solutions[i][1][j] < solution[1][j]:
                        dominance[j] = False
        count = 0
        for i in range(len(dominance)):
            if dominance[i]:
                count += 1
        return count

    def get_all_results(self) -> list[tuple]:
        return self.all_results

    def _run_sequential(self) -> list[tuple]:
        results = []
        for solver in self.solvers:
            solver.run()
            result = solver.get_best()
            schedule = self.translators[solver].translate(result=result, jobs=self.jobs, env=self.env, orders=self.orders)
            schedule.created_by = solver
            schedule.created_in = self.env
            schedule.created_for = self.orders
            results.append((result, schedule))
        return results # returns a list of tuples <result, schedule>

    def _run_parallel(self) -> list[tuple]:
        context = mp.get_context('spawn') # 'spawn'
        results = []
        queue = context.Queue()
        parent_pipe, child_pipe = context.Pipe() # try pipe instead of queue
        processes = []
        for solver in self.solvers:
            #p = context.Process(target=solve_parallel, args=(solver, self.translators[solver], self.jobs, self.env, self.orders, queue))
            p = context.Process(target=solve_parallel, args=(solver, self.translators[solver], self.jobs, self.env, self.orders, child_pipe,))
            processes.append(p)
            print('added process to list')
            p.start()
        for process in processes: # one result per process
            print('waiting for queue...')
            #results.append(queue.get())
            results.append(parent_pipe.recv())
            print('received result from queue!')
        print('joining processes')
        for process in processes: # second loop in case results are not added to the queue in order
            process.join() 
            print('process joined!')
        return results



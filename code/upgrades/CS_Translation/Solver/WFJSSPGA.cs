using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;

namespace Solver
{
    public class WFJSSPGA //: GA
    {
        protected List<WFJSSPIndividual> _population;
        //private GAConfiguration _configuration;
        protected Random _random;

        protected bool _generationStop = false;
        protected bool _fitnessStop = false;
        protected bool _timeStop = false;
        protected bool _fevalStop = false;

        protected bool _useGenerationStop = true;
        protected bool _useFitnessStop = true;
        protected bool _useTimeStop = true;
        protected bool _useFevalStop = true;

        DateTime _startTime;
        protected int _functionEvaluations = 0;

        public int FunctionEvaluations { get => _functionEvaluations; set => _functionEvaluations = value; }

        protected bool _output = false;
        private int[,,] _workerDurations;
        private WorkerGAConfiguration _configuration;

        public void Reset()
        {
            _random = new Random();
            _population = new List<WFJSSPIndividual>();
            _functionEvaluations = 0;
        }

        public WFJSSPGA(WorkerGAConfiguration configuration, bool output, int[,,] workerDurations)// : base(configuration, output)
        {
            _configuration = configuration;
            _output = output;
            Reset();
            _workerDurations = workerDurations;
            //List<List<List<int>>> availableWorkers = new List<List<List<int>>>();
            //for(int operation = 0; operation < _workerDurations.GetLength(0); ++operation)
            //{
            //    List<List<int>> operationWorkers = new List<List<int>>();
            //    for(int machine = 0; machine < _workerDurations.GetLength(1); ++machine)
            //    {
            //        List<int> machineWorkers = new List<int>();
            //        for(int worker = 0; worker < _workerDurations.GetLength(2); ++worker)
            //        {
            //            if (_workerDurations[operation,machine,worker] > 0)
            //            {
            //                machineWorkers.Add(worker);
            //            }
            //        }
            //        operationWorkers.Add(machineWorkers);
            //    }
            //    availableWorkers.Add(operationWorkers);
            //}
            //WFJSSPIndividual.AvailableWorkers = availableWorkers;
            // TODO: update mutation probability
            configuration.MutationProbability = 1.0f / (configuration.NOperations * 3.0f);
        }

        private void Adjust(WFJSSPIndividual nIndividual)
        {
            return;
            WFJSSPIndividual individual = (WFJSSPIndividual)nIndividual;
            // TODO
            List<List<Dictionary<string, int>>> gaps = new List<List<Dictionary<string, int>>>();
            for (int i = 0; i < _configuration.NMachines; ++i)
            {
                gaps.Add(new List<Dictionary<string, int>>());
            }
            int[] endTimesOnMachines = new int[_configuration.NMachines];
            int[] endTimesOfOperations = new int[_configuration.NOperations];

            int[] endTimesOfWorkers = new int[_workerDurations.GetLength(2)]; // should be N workers

            int[] nextOperation = new int[_configuration.NJobs];

            for (int i = 0; i < individual.Sequence.Length; ++i)
            {
                int job = 0;
                int operation = nextOperation[job]++;
                int operationIndex = _configuration.JobStartIndices[job] + operation;
                int machine = individual.Assignments[operationIndex];

                int worker = individual.Workers[operationIndex];

                int duration = _workerDurations[operation, machine, worker];

                bool inserted = false;
                for (int j = 0; j < gaps[machine].Count; ++j)
                {
                    Dictionary<string, int> gap = gaps[machine][j];
                    if (gap["end"] - gap["start"] >= duration)
                    {
                        if (operationIndex == 0 || _configuration.JobSequence[operationIndex - 1] == _configuration.JobSequence[operationIndex] && endTimesOfOperations[operationIndex - 1] <= gap["end"] - duration)
                        {
                            // gap can be used
                            inserted = true;
                            int start = 0;
                            if (operationIndex != 0)
                            {
                                start = Math.Min(gap["start"], endTimesOfOperations[operationIndex - 1]);
                            }
                            int end = start + duration;
                            if (gap["end"] - end > 0)
                            {
                                Dictionary<string, int> newGap = new Dictionary<string, int>();
                                newGap["start"] = end;
                                newGap["end"] = gap["end"];
                                newGap["preceedsOperation"] = operationIndex;
                                gaps[machine].Add(newGap);
                            }
                            endTimesOfOperations[operationIndex] = end;
                            int jobSwap = _configuration.JobSequence[gap["preceedsOperation"]];
                            int swapOperationIndex = 0;
                            int swapStartIndex = 0;
                            bool found = false;
                            for (int k = 0; k < _configuration.JobSequence.Length && !found; ++k)
                            {
                                if (_configuration.JobSequence[k] == jobSwap)
                                {
                                    swapStartIndex = k;
                                    found = true;
                                }
                            }
                            swapOperationIndex = gap["preceedsOperation"] - swapStartIndex;
                            int count = 0;
                            int swapIndividualIndex = 0;
                            found = false;
                            for (int k = 0; k < individual.Sequence.Length && !found; ++k)
                            {
                                if (individual.Sequence[k] == jobSwap)
                                {
                                    if (count == swapOperationIndex)
                                    {
                                        swapIndividualIndex = k;
                                        found = true;
                                    }
                                    ++count;
                                }
                            }
                            int tmp = individual.Sequence[swapIndividualIndex];
                            individual.Sequence[swapIndividualIndex] = individual.Sequence[i];
                            individual.Sequence[i] = tmp;
                            gaps[machine].Remove(gap);
                            break; // TODO: double check
                        }
                    }
                }
                if (!inserted)
                {
                    int jobMinStart = 0;
                    if (operationIndex != 0 && _configuration.JobSequence[operationIndex - 1] == _configuration.JobSequence[operationIndex])
                    {
                        jobMinStart = endTimesOfOperations[operationIndex - 1];
                    }
                    if (jobMinStart > endTimesOnMachines[machine])
                    {
                        gaps[machine].Add(new Dictionary<string, int>() { ["start"] = jobMinStart, ["end"] = jobMinStart + duration, ["preceedsOperation"] = operationIndex });
                        endTimesOnMachines[machine] = jobMinStart + duration;
                    }
                    else
                    {
                        endTimesOnMachines[machine] += duration;
                    }
                }
                endTimesOfOperations[operationIndex] = endTimesOnMachines[machine];
            }
        }

        class TimeSlot
        {
            public int Start = 0;
            public int End = 0;

            public TimeSlot(int start, int end)
            {
                Start = start;
                End = end;
            }
            public bool Overlaps(TimeSlot other)
            {
                return Contains(other.Start) || Contains(other.End) || other.Contains(Start) || other.Contains(End);
            }

            public bool Contains(int time)
            {
                return time >= Start && time <= End;
            }
        }

        private TimeSlot EarliestFit(List<TimeSlot> slots, TimeSlot slot)
        {
            for(int i = 1; i < slots.Count; ++i) 
            {
                if (slots[i-1].End <= slot.Start && slots[i].Start >= slot.End)
                {
                    return slots[i - 1];
                }
            }
            return slots.Last();
        }

        private void EvaluateSlots(WFJSSPIndividual nIndividual)
        {
            
            WFJSSPIndividual individual = (WFJSSPIndividual)nIndividual;
            // TODO: test
            if (!individual.Feasible)
            {
                individual.Fitness[Criteria.Makespan] = float.MaxValue;
                return;
            }
            int[] nextOperation = new int[_configuration.NJobs];
            List<TimeSlot>[] endOnMachines = new List<TimeSlot>[_configuration.NMachines];
            for(int i = 0; i < endOnMachines.Length; ++i)
            {
                endOnMachines[i] = new List<TimeSlot>();
                endOnMachines[i].Add(new TimeSlot(0, 0));
            }
            List<TimeSlot>[] endOfWorkers = new List<TimeSlot>[_workerDurations.GetLength(2)];
            for (int i = 0; i < endOfWorkers.Length; ++i)
            {
                endOfWorkers[i] = new List<TimeSlot>();
                endOfWorkers[i].Add(new TimeSlot(0, 0));
            }
            //int[] endOnMachines = new int[_configuration.NMachines];
            // TODO: need to keep record of worker times in a different format
            //int[] endOfWorkers = new int[_workerDurations.GetLength(2)];
            int[] endTimes = new int[_configuration.JobSequence.Length];
            for (int i = 0; i < individual.Sequence.Length; ++i)
            {
                int job = individual.Sequence[i];
                int operation = nextOperation[job];
                ++nextOperation[job];
                int startIndex = _configuration.JobStartIndices[job] + operation;
                int machine = individual.Assignments[startIndex];

                int worker = individual.Workers[startIndex];

                int duration = _workerDurations[startIndex, machine, worker];
                if(duration == 0)
                {
                    Console.WriteLine("0 DURATION, INVALID ASSIGNMENT!");
                }
                int offset = 0;
                int minStartJob = 0;
                if (operation > 0)
                {
                    if (endTimes[startIndex - 1] > offset)
                    {
                        // need to wait for previous operation to finish
                        offset = endTimes[startIndex - 1];
                    }
                }
                if (endOnMachines[machine].Count > 0 && endOnMachines[machine].Last().End >= offset)
                {
                    // need to wait for machine to be available
                    // TODO: could check for earlier timeslot here, but complicated with worker 
                    offset = endOnMachines[machine].Last().End;
                }
                // TODO: don't check if the worker is finished, check if the worker is free in the timespan instead
                // (could be on other machine at a later time already)
                if (endOfWorkers[worker].Count > 0)
                {
                    TimeSlot workerEarliest = EarliestFit(endOfWorkers[worker], new TimeSlot(offset, offset + duration));
                    if (workerEarliest.End >= offset)
                    //if (endOfWorkers[worker].Last().End >= offset)
                    {
                        // need to wait for worker to be ready
                        //offset = endOfWorkers[worker].Last().End;
                        offset = workerEarliest.End;
                    }
                }

                //offset = Math.Max(Math.Max(0, endTimes[startIndex - 1] - endOnMachines[machine]), endTimes[startIndex - 1] - endOfWorkers[worker]);
                //minStartJob = endTimes[startIndex - 1];
                //}
                endTimes[startIndex] = offset + duration;
                //endTimes[startIndex] = Math.Max(endOnMachines[machine], endOfWorkers[worker]) + duration + offset;
                endOnMachines[machine].Add(new TimeSlot(offset, offset + duration));
                endOfWorkers[worker].Add(new TimeSlot(offset, offset + duration));
                //endOnMachines[machine] = endTimes[startIndex];
                //endOfWorkers[worker] = endTimes[startIndex];
            }
            individual.Fitness[Criteria.Makespan] = endTimes.Max();
            _functionEvaluations++;
        }

        private void Evaluate(WFJSSPIndividual nIndividual)
        {
            // just redirect for now
            EvaluateSlots(nIndividual);
            /*
            WFJSSPIndividual individual = (WFJSSPIndividual)nIndividual;
            // TODO: test
            if (!individual.Feasible)
            {
                individual.Fitness[Criteria.Makespan] = float.MaxValue;
                return;
            }
            int[] nextOperation = new int[_configuration.NJobs];
            int[] endOnMachines = new int[_configuration.NMachines];
            // TODO: need to keep record of worker times in a different format
            int[] endOfWorkers = new int[_workerDurations.GetLength(2)];
            int[] endTimes = new int[_configuration.JobSequence.Length];
            for (int i = 0; i < individual.Sequence.Length; ++i)
            {
                int job = individual.Sequence[i];
                int operation = nextOperation[job];
                ++nextOperation[job];
                int startIndex = _configuration.JobStartIndices[job] + operation;
                int machine = individual.Assignments[startIndex];

                int worker = individual.Workers[startIndex];

                int duration = _workerDurations[startIndex, machine, worker];
                int offset = 0;
                int minStartJob = 0;
                if (operation > 0)
                {
                    if (endTimes[startIndex - 1] > offset)
                    {
                        // need to wait for previous operation to finish
                        offset = endTimes[startIndex - 1];
                    }
                }
                if (endOnMachines[machine] > offset)
                {
                    // need to wait for machine to be available
                    offset = endOnMachines[machine];
                }
                // TODO: don't check if the worker is finished, check if the worker is free in the timespan instead
                // (could be on other machine at a later time already)
                if (endOfWorkers[worker] > offset)
                {
                    // need to wait for worker to be ready
                    offset = endOfWorkers[worker];
                }
                    
                    //offset = Math.Max(Math.Max(0, endTimes[startIndex - 1] - endOnMachines[machine]), endTimes[startIndex - 1] - endOfWorkers[worker]);
                    //minStartJob = endTimes[startIndex - 1];
                //}
                endTimes[startIndex] = offset + duration;
                //endTimes[startIndex] = Math.Max(endOnMachines[machine], endOfWorkers[worker]) + duration + offset;
                endOnMachines[machine] = endTimes[startIndex];
                endOfWorkers[worker] = endTimes[startIndex];
            }
            individual.Fitness[Criteria.Makespan] = endTimes.Max();
            _functionEvaluations++;*/
        }


        protected WFJSSPIndividual TournamentSelection(int tournamentSize)
        {
            if (tournamentSize == 0)
            {
                tournamentSize = Math.Max(1, _population.Count / 10);
            }
            List<int> participants = new List<int>();
            while (participants.Count < tournamentSize)
            {
                int index;
                do
                {
                    index = _random.Next(_population.Count);
                } while (participants.Contains(index));
                participants.Add(index);
            }
            WFJSSPIndividual winner = _population[participants[0]];
            for (int i = 1; i < participants.Count; ++i)
            {
                if (_population[participants[i]].Fitness[Criteria.Makespan] < winner.Fitness[Criteria.Makespan])
                {
                    winner = _population[participants[i]];
                }
            }
            return winner;
        }

        protected WFJSSPIndividual Recombine(int tournamentSize)
        {
            WFJSSPIndividual parentA = TournamentSelection(tournamentSize);
            WFJSSPIndividual parentB;
            int maxAttempts = 100;
            int attempts = 0;
            do
            {
                parentB = TournamentSelection(tournamentSize);
                ++attempts;
            } while (parentA.Equals(parentB) && attempts < maxAttempts);
            return new WFJSSPIndividual(parentA, parentB);
        }

        protected bool HasInvalidAssignment(WFJSSPIndividual individual)
        {
            for (int i = 0; i < individual.Assignments.Length; ++i)
            {
                if (_configuration.Durations[i, individual.Assignments[i], individual.Workers[i]] == 0)
                {
                    return true;
                }
            }
            return false;
        }

        protected void CheckIndividual(WFJSSPIndividual individual)
        {
            if (HasInvalidAssignment(individual))
            {
                Console.WriteLine("Something went wrong!");
            }
        }

        protected void CreatePopulation(int populationSize)
        {
            _population = new List<WFJSSPIndividual>();
            for (int i = 0; i < populationSize; ++i)
            {
                WFJSSPIndividual individual = new WFJSSPIndividual(_population);
                // Adjustment step
                Adjust(individual);
                Evaluate(individual);
                //CheckIndividual(individual);
                _population.Add(individual);
            }
            _population.Sort((a, b) => a.Fitness[Criteria.Makespan].CompareTo(b.Fitness[Criteria.Makespan]));
        }

        protected void CreateOffspring(List<WFJSSPIndividual> offspring, int offspringAmount, int tournamentSize, float mutationProbability)
        {
            offspring.Clear();
            //offspring = new List<Individual>();
            for (int i = 0; i < offspringAmount; ++i)
            {
                WFJSSPIndividual o = Recombine(tournamentSize);
                // Adjustment step
                //CheckIndividual(o);
                Adjust(o);
                o.Mutate(mutationProbability);
                Evaluate(o);
                offspring.Add(o);
            }
        }

        public void SetStoppingCriteriaStatus(bool generation, bool time, bool functionEvaluations, bool targetFitness)
        {
            _useGenerationStop = generation;
            _useTimeStop = time;
            _useFevalStop = functionEvaluations;
            _useFitnessStop = targetFitness;
        }

        protected void UpdateStoppingCriteria(int generation, float bestFitness, int maxGeneration, int functionEvaluations, int maxFunctionEvaluations, int timeLimit, float targetFitness)
        {
            _generationStop = _useGenerationStop && generation >= maxGeneration;
            _timeStop = _useTimeStop && DateTime.Now.Subtract(_startTime).TotalSeconds >= timeLimit;
            _fevalStop = _useFevalStop && functionEvaluations >= maxFunctionEvaluations;
            _fitnessStop = _useFitnessStop && bestFitness <= targetFitness;
        }

        protected List<WFJSSPIndividual> GetAllEqual(WFJSSPIndividual original, List<WFJSSPIndividual> individuals)
        {
            List<WFJSSPIndividual> result = new List<WFJSSPIndividual>();
            for (int i = 0; i < individuals.Count; ++i)
            {
                if (original.Fitness[Criteria.Makespan] == individuals[i].Fitness[Criteria.Makespan])
                {
                    result.Add(individuals[i]);
                }
            }
            return result;
        }

        protected float UpdateMutationProbability(float p, int generation, int lastProgress, int maxWait, float maxP)
        {
            return (float)(p + (Math.Pow((generation - lastProgress) * (1.0f / maxWait), 4) * maxP));
        }

        protected void MutateMachineVector(WFJSSPIndividual individual)
        {
            float p = 1.0f / individual.Assignments.Length;
            for (int i = 0; i < individual.Assignments.Length; ++i)
            {
                if (_random.NextDouble() < p)
                {
                    if (WFJSSPIndividual.AvailableMachines[i].Count > 1)
                    {
                        int swap;
                        do
                        {
                            swap = WFJSSPIndividual.AvailableMachines[i][_random.Next(WFJSSPIndividual.AvailableMachines[i].Count)];
                        } while (swap != individual.Assignments[i]);
                        individual.Assignments[i] = swap;
                    }
                }
            }
        }

        protected void MutateSequenceVector(WFJSSPIndividual individual)
        {
            float p = 1.0f / individual.Sequence.Length;
            for (int i = 0; i < individual.Sequence.Length; ++i)
            {
                if (_random.NextDouble() < p)
                {
                    int swap;
                    do
                    {
                        swap = _random.Next(individual.Sequence.Length);
                    } while (swap == i || individual.Sequence[i] == individual.Sequence[swap]);
                    int tmp = individual.Sequence[i];
                    individual.Sequence[i] = individual.Sequence[swap];
                    individual.Sequence[swap] = tmp;
                }
            }
        }

        protected WFJSSPIndividual SimulatedAnnealing(WFJSSPIndividual individual)
        {
            int nMachineMutations = 5;
            int nSequenceMutations = 20;
            float initialT = 20.0f;
            float alpha = 0.8f;
            int nT = 7;
            float T = initialT;
            WFJSSPIndividual best = new WFJSSPIndividual(individual);
            for (int i = 0; i < nMachineMutations; ++i)
            {
                WFJSSPIndividual y = new WFJSSPIndividual(individual);
                if (i > 0)
                {
                    MutateMachineVector(y);
                }
                for (int j = 0; j < nT; ++j)
                {
                    WFJSSPIndividual yTmp = new WFJSSPIndividual(y);
                    Evaluate(yTmp);
                    for (int k = 0; k < nSequenceMutations; ++k)
                    {
                        WFJSSPIndividual z = new WFJSSPIndividual(y);
                        MutateSequenceVector(z);
                        Evaluate(z);
                        if (z.Fitness[Criteria.Makespan] < yTmp.Fitness[Criteria.Makespan])
                        {
                            yTmp = z;
                        }
                    }
                    if (yTmp.Fitness[Criteria.Makespan] < y.Fitness[Criteria.Makespan])
                    {
                        y = yTmp;
                    }
                    if (y.Fitness[Criteria.Makespan] < best.Fitness[Criteria.Makespan])
                    {
                        best = y;
                    }
                    T *= alpha;
                }
                T = initialT;
            }
            return best;
        }

        protected WFJSSPIndividual LocalSearch(List<WFJSSPIndividual> currentBest)
        {
            //NOTE: since currentBest is now a list, somehow one of the individuals would need to be chosen for simulated annealing?
            return SimulatedAnnealing(currentBest[0]);
        }

        public void Debug_Report(int generation, List<WFJSSPIndividual> best, List<WFJSSPIndividual> currentBest, int restarts, bool improvement, bool match)
        {
            if (improvement)
            {
                Console.ForegroundColor = ConsoleColor.Green;
            }
            else if (match)
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
            }
            Console.WriteLine("Generation " + generation + " Overall Best: " + best[0].Fitness[Criteria.Makespan] + " (" + best.Count + " equal solutions), Current Run Best " + currentBest[0].Fitness[Criteria.Makespan] + " (" + currentBest.Count + " equal solutions) - " + restarts + " restarts" + ")");
            Console.ResetColor();
        }

        public WorkerHistory Run(int maxGeneration, int timeLimit, float targetFitness, int maxFunctionEvaluations, bool keepMultiple, bool doLocalSearch)
        {
            CreatePopulation(_configuration.PopulationSize);
            List<WFJSSPIndividual> offspring = new List<WFJSSPIndividual>();
            // Setup all required parameters using the decision variables
            int populationSize = _configuration.PopulationSize;
            int offspringAmount = _configuration.OffspringAmount;
            int tournamentSize = _configuration.TournamentSize; //TODO: adjust
            float mutationProbability = _configuration.MutationProbability;
            float maxMutationProbability = _configuration.MaxMutationProbability;
            float elitism = _configuration.ElitismRate * populationSize;
            int maxWait = _configuration.RestartGenerations;
            int restarts = 0;
            List<WFJSSPIndividual> overallBest = GetAllEqual(_population[0], _population);
            List<WFJSSPIndividual> currentBest = GetAllEqual(_population[0], _population);
            int lastProgress = 0;
            int generation = 0;
            _functionEvaluations = 0;
            _startTime = DateTime.Now;

            _output = false;

            WorkerHistory history = new WorkerHistory();
            bool improvement = false;
            bool match = false;
            UpdateStoppingCriteria(generation, overallBest[0].Fitness[Criteria.Makespan], maxGeneration, _functionEvaluations, maxFunctionEvaluations, timeLimit, targetFitness);
            while (!_generationStop && !_fevalStop && !_fitnessStop && !_timeStop)
            {
                history.Update(overallBest, currentBest, mutationProbability, _population);
                if (generation > 0 && lastProgress < generation - 1)
                {
                    mutationProbability = UpdateMutationProbability(mutationProbability, generation, lastProgress, maxWait, maxMutationProbability);
                }
                if (mutationProbability > maxMutationProbability)
                {
                    WFJSSPIndividual localMinimum = currentBest[0];
                    if (doLocalSearch)
                    {
                        //Note: local minimum
                        //Console.WriteLine("Local Search");
                        localMinimum = LocalSearch(currentBest);
                        //Console.WriteLine("Local Search Done");
                    }
                    // only necessary if local search is conducted
                    if (localMinimum.Fitness[Criteria.Makespan] < overallBest[0].Fitness[Criteria.Makespan])
                    {
                        overallBest.Clear(); // just never happened without local search
                        improvement = true;
                        if (keepMultiple)
                        {
                            foreach (WFJSSPIndividual individual in currentBest)
                            {
                                if (individual.Fitness[Criteria.Makespan] == localMinimum.Fitness[Criteria.Makespan] && !overallBest.Contains(individual))
                                {
                                    overallBest.Add(individual);
                                }
                            }
                        }
                        else
                        {
                            overallBest.Add(localMinimum);
                        }
                        //overallBest = currentBest;
                    }
                    else if (keepMultiple && localMinimum.Fitness[Criteria.Makespan] == overallBest[0].Fitness[Criteria.Makespan] && !overallBest.Contains(localMinimum))
                    {
                        overallBest.Add(localMinimum);
                        match = true;
                    }
                    if (_output)
                    {
                        Debug_Report(generation - 1, overallBest, currentBest, restarts, improvement, match);
                    }
                    int maxPopulationSize = 400; // TODO: parameter
                    int maxOffspringAmount = maxPopulationSize * 4; // TODO: parameter
                    populationSize = (int)Math.Min(maxPopulationSize, _configuration.PopulationSizeGrowthRate * populationSize);
                    offspringAmount = (int)Math.Min(maxOffspringAmount, _configuration.PopulationSizeGrowthRate * offspringAmount);

                    elitism = Math.Max(0, populationSize * _configuration.MaxElitismRate * _configuration.DurationVariety);
                    tournamentSize = (int)Math.Max(1, (int)populationSize * _configuration.MaxTournamentRate * _configuration.DurationVariety);

                    currentBest.Clear();
                    // NOTE: for visual purposes only
                    improvement = false;
                    match = false;
                    // NOTE: also sorts the population
                    CreatePopulation(populationSize);
                    mutationProbability = _configuration.MutationProbability;
                    lastProgress = generation;
                    restarts++;
                }

                CreateOffspring(offspring, offspringAmount, tournamentSize, mutationProbability);
                //offspring.Sort((a, b) => a.Fitness[Criteria.Makespan].CompareTo(b.Fitness[Criteria.Makespan])); // pool gets sorted anyway
                List<WFJSSPIndividual> pool = offspring; // NOTE: since no copy is made, could just use offspring as list
                for (int i = 0; i < elitism; ++i)
                {
                    // NOTE: population should always be sorted at this point
                    pool.Add(_population[i]);
                }
                pool.Sort((a, b) => a.Fitness[Criteria.Makespan].CompareTo(b.Fitness[Criteria.Makespan]));
                _population = new List<WFJSSPIndividual>();
                for (int i = 0; i < populationSize; ++i)
                {
                    _population.Add(pool[i]);
                }

                if (currentBest.Count == 0 || _population[0].Fitness[Criteria.Makespan] < currentBest[0].Fitness[Criteria.Makespan])
                {
                    if (keepMultiple)
                    {
                        currentBest = GetAllEqual(_population[0], _population);
                    } else
                    {
                        currentBest.Clear();
                        currentBest.Add(_population[0]);
                    }
                    if (currentBest[0].Fitness[Criteria.Makespan] < overallBest[0].Fitness[Criteria.Makespan])
                    {
                        overallBest.Clear();
                        improvement = true;
                        if (keepMultiple)
                        {
                            overallBest = GetAllEqual(_population[0], _population); // just to not copy currentBest
                        } else
                        {
                            overallBest.Add(currentBest[0]);
                        }
                    }
                    else if (keepMultiple && currentBest[0].Fitness[Criteria.Makespan] == overallBest[0].Fitness[Criteria.Makespan])
                    {
                        match = true;
                        for (int i = 0; i < currentBest.Count; ++i)
                        {
                            if (!overallBest.Contains(currentBest[i]))
                            {
                                overallBest.Add(currentBest[i]);
                            }
                        }
                    }
                    lastProgress = generation;
                }
                else if (keepMultiple && _population[0].Fitness[Criteria.Makespan] == currentBest[0].Fitness[Criteria.Makespan])
                {
                    List<WFJSSPIndividual> equals = GetAllEqual(_population[0], _population);
                    for (int i = 0; i < equals.Count; ++i)
                    {
                        if (!currentBest.Contains(equals[i]))
                        {
                            currentBest.Add(equals[i]);
                        }
                    }
                    if (currentBest[0].Fitness[Criteria.Makespan] == overallBest[0].Fitness[Criteria.Makespan])
                    {
                        for (int i = 0; i < currentBest.Count; ++i)
                        {
                            if (!overallBest.Contains(currentBest[i]))
                            {
                                match = true;
                                overallBest.Add(currentBest[i]);
                            }
                        }
                    }
                }
                UpdateStoppingCriteria(generation, overallBest[0].Fitness[Criteria.Makespan], maxGeneration, _functionEvaluations, maxFunctionEvaluations, timeLimit, targetFitness);
                ++generation;
            }
            if (_output)
            {
                Debug_Report(generation, overallBest, currentBest, restarts, improvement, match);
            }
            history.Result = new WorkerResult(overallBest, _configuration, generation - 1, _functionEvaluations, DateTime.Now.Subtract(_startTime).TotalSeconds, [_generationStop, _fevalStop, _fitnessStop, _timeStop], restarts);
            return history;
        }
    }
}

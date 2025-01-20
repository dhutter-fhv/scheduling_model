using BenchmarkParsing;
using System.IO;
using System.Runtime.InteropServices;
using static BenchmarkParsing.BenchmarkParser;
using static System.Net.Mime.MediaTypeNames;


namespace Solver
{
    internal class Program
    {
        static int index = 0;
        static ConsoleColor[] _colors = { ConsoleColor.Red, ConsoleColor.Green, ConsoleColor.Blue, ConsoleColor.Yellow, ConsoleColor.White, ConsoleColor.Magenta};
        static void RunExperiment(string basepath, bool[] criteriaStatus, int maxGenerations, int timeLimit, float targetFitness, int maxFunctionEvaluations)
        {
            // TODO
            bool skip = false;
            bool skipSource = false;
            string[] sources = Directory.GetDirectories(basepath);
            foreach (string source in sources)
            {
                History gaResult = null;
                //Console.WriteLine(source);
                if (source.EndsWith("6_Fattahi"))
                {
                    skipSource = false;
                }
                if (!skipSource)
                {

                    string[] instances = Directory.GetFiles(source);
                    foreach (string instance in instances)
                    {
                        if (instance.EndsWith("Fattahi4.fjs"))
                        {
                            skip = false;
                        }
                        if (!skip)
                        {
                            Console.WriteLine("Processing: " + instance);
                            BenchmarkParser parser = new BenchmarkParser();
                            //Console.WriteLine("Parsing Complete");
                            Encoding result = parser.ParseBenchmark(instance);
                            //Console.WriteLine("Encoding Complete");
                            DecisionVariables variables = new DecisionVariables(result);
                            //Console.WriteLine("Decision Variables Complete");
                            GAConfiguration configuration = new GAConfiguration(result, variables);
                            //Console.WriteLine("Configuration Complete");
                            GA ga = new GA(configuration, true);
                            //Console.WriteLine("GA Creation Complete");
                            ga.SetStoppingCriteriaStatus(criteriaStatus[0], criteriaStatus[1], criteriaStatus[3], criteriaStatus[2]); // TODO: change signature parameter order
                            Console.WriteLine("Starting Run");
                            gaResult = ga.Run(maxGenerations, timeLimit, targetFitness, maxFunctionEvaluations);
                            string[] fullPath = instance.Split("\\");
                            gaResult.Name = fullPath.Last();
                            gaResult.ToFile("C:\\Users\\huda\\Desktop\\experiments\\results_1_second.json");
                        }
                    }
                }
                //Console.ReadLine();
            }


            /*
            BenchmarkParser parser = new BenchmarkParser();
            Encoding result = parser.ParseBenchmark(path);
            DecisionVariables variables = new DecisionVariables(result);
            GAConfiguration configuration = new GAConfiguration(result, variables);
            GA ga = new GA(configuration, true);
            ga.SetStoppingCriteriaStatus(criteriaStatus[0], criteriaStatus[1], criteriaStatus[3], criteriaStatus[2]); // TODO: change signature parameter order
            History gaResult = ga.Run(maxGenerations, timeLimit, targetFitness, maxFunctionEvaluations);
            // TODO
            gaResult.ToFile("test.json");
            Console.WriteLine(gaResult.Result.ToString());*/
        }

        static void PrepareFile(string filename)
        {
            File.AppendAllText(filename, "{results:[");
        }

        static void DelimitRun(string filename)
        {
            File.AppendAllText(filename, ",");
        }

        static void EndFile(string filename)
        {
            File.AppendAllText(filename, "];");
        }
        static void RunExperimentWorkers(string basepath, bool[] criteriaStatus, int maxGenerations, int timeLimit, float targetFitness, int maxFunctionEvaluations, bool keepMultiple, bool localSearch, int iteration)
        {
            // TODO
            //basepath = "C:\\Users\\localadmin\\Documents\\GitHub\\scheduling_model\\code\\reworked_data_model\\benchmarks_with_workers\\";
            //basepath = "C:\\Users\\huda\\Documents\\GitHub\\scheduling_model_jrc\\code\\upgrades\\benchmarks_with_workers\\";
            bool skip = false;
            string outPath = "C:\\Users\\localadmin\\Desktop\\experiments\\comparison\\ga\\";
            //if (localSearch)
            //{
            if(iteration == 0)
            {
                outPath += "dissimilarity\\";
                WFJSSPIndividual.UseDissimilarity = true;
            } else
            {
                outPath += "no_dissimilarity\\";
                WFJSSPIndividual.UseDissimilarity = false;
            }
            //outPath += ((iteration+1)*50).ToString()+"_populationSize\\";
            //} else
            //{
            //    outPath += "nolocal\\";
            //}
            //bool skipSource = true;
            //string[] sources = Directory.GetDirectories(basepath);
            //foreach (string source in sources)
            //{
            //Console.WriteLine(source);
            //    if (source.EndsWith("6_Fattahi"))
            //    {
            //        skipSource = false;
            //    }
            //    if (!skipSource)
            //    {

            var dict = File.ReadLines("C:\\Users\\localadmin\\Documents\\GitHub\\scheduling_model_jrc\\code\\analysis\\best_known.txt").Select(line => line.Split(';')).ToDictionary(line => line[0], line => line[1]);
            string[] instances = Directory.GetFiles(basepath);
            foreach (string instance in instances)
            {
                Console.ForegroundColor = _colors[index - 1];
                string instanceName = instance.Split("\\").Last();
                
                if (dict.ContainsKey(instanceName))
                {
                    bool success = float.TryParse(dict[instanceName], out targetFitness);
                    if (success)
                    {
                        criteriaStatus[2] = true;
                    } else
                    {
                        targetFitness = 0.0f;
                    }
                }
                //string path = "C:\\Users\\localadmin\\Desktop\\experiments\\worker_results\\ga_results\\with_localsearch\\" + gaResult.Name + ".json";
                if (!File.Exists(outPath+ instanceName + ".json"))
                {
                    PrepareFile(outPath + instanceName + ".json");
                }
                WorkerHistory gaResult = null; // free up memory
                if (instance.EndsWith("6_Fattahi_14_workers.fjs"))
                {
                    skip = false;
                }
                if (!skip)
                {
                    Console.WriteLine(index + ": Processing: " + instanceName + " - Run #" + (iteration+1));
                    WorkerBenchmarkParser parser = new WorkerBenchmarkParser();
                    //Console.WriteLine("Parsing Complete");
                    WorkerEncoding encoding = parser.ParseBenchmark(instance);
                    //Console.WriteLine("Encoding Complete");
                    WorkerDecisionVariables variables = new WorkerDecisionVariables(encoding);
                    //Console.WriteLine("Decision Variables Complete");
                    WorkerGAConfiguration config = new WorkerGAConfiguration(encoding, variables);
                    

                    //Console.WriteLine("Configuration Complete");
                    WFJSSPGA ga = new WFJSSPGA(config, true, encoding.Durations);
                    //Console.WriteLine("GA Creation Complete");
                    ga.SetStoppingCriteriaStatus(criteriaStatus[0], criteriaStatus[1], criteriaStatus[3], criteriaStatus[2]); // TODO: change signature parameter order
                    //Console.WriteLine("Starting Run");
                    gaResult = ga.Run(maxGenerations, timeLimit, targetFitness, maxFunctionEvaluations, keepMultiple, localSearch);
                    string[] fullPath = instance.Split("\\");
                    gaResult.Name = fullPath.Last();
                    gaResult.ToFile(outPath + gaResult.Name + ".json");
                    DelimitRun(outPath + instanceName + ".json");
                }
            }
        }
    


        static void Main(string[] args)
        {
            string path = "C:\\Users\\localadmin\\Desktop\\experiments\\comparison\\benchmarks\\"; // DEBUG
            //string path = "C:\\Users\\huda\\Documents\\GitHub\\scheduling_model_jrc\\code\\upgrades\\benchmarks"; // DEBUG
            int maxGenerations = 0;
            int timeLimit = 300;//1200;//300; // in seconds
            //float targetFitness = 1196.0f;
            float targetFitness = 0.0f;
            int maxFunctionEvaluations = 0;
            if(args.Length > 0)
            {
                //path = args[0];
                int.TryParse(args[0], out index);
                Console.ForegroundColor = _colors[index-1];
                if(args.Length > 1)
                {
                    int.TryParse(args[1], out maxGenerations);
                    int.TryParse(args[2], out timeLimit);
                    float.TryParse(args[3], out targetFitness);
                    int.TryParse(args[4], out maxFunctionEvaluations);
                }
            }
            bool[] criteriaStatus = { maxGenerations > 0, timeLimit > 0, targetFitness > 0.0f, maxFunctionEvaluations > 0};
            if (!(criteriaStatus[0] || criteriaStatus[1] || criteriaStatus[2] || criteriaStatus[3]))
            {
                Console.WriteLine("No valid stopping criteria was set!");
                return;
            }
            int nExperiments = 2;
            bool keepMultiple = false;
            int restartGenerations = 25;

            //RunExperiment(path, criteriaStatus, maxGenerations, timeLimit, targetFitness, maxFunctionEvaluations);
            for(int i = 0; i < nExperiments; ++i) // assuming 5 instances
            {
                RunExperimentWorkers(path, criteriaStatus, maxGenerations, timeLimit, targetFitness, maxFunctionEvaluations, keepMultiple, false, i);
            }
        }
    }
}

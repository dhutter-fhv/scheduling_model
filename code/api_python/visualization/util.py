import matplotlib.pyplot as plt

def ecdf_inf(vectors, title : str = None, max : bool = False, n_instances : int = 402, labels : list[str] = [], xlabel : str = None, xlim : tuple[float, float] = None):
    plot_vectors = []
    for vector in vectors:
        plot_vectors.append([[0.0],[0.0]])
        i = 1
        while i < len(vector):
            if vector[i] == float('inf'):
                break
            if vector[i] == -float('inf'):
                break
            while i < len(vector) and vector[i] == vector[i-1]:
                i += 1
            plot_vectors[-1][0].append(vector[i-1])
            plot_vectors[-1][1].append((i-1)/n_instances)
            i += 1
    for i in range(len(vectors)):
        plt.plot(plot_vectors[i][0], plot_vectors[i][1], label=[labels[i]])
    if xlim:
        plt.xlim(xlim[0], xlim[1])
        
    plt.legend()
    if title:
        plt.title(title)
    if xlabel:
        plt.xlabel(xlabel)
    plt.ylabel('Portion of Instances')
    plt.show()

def calculate_gap(fitness, best, max : bool = False):
    gap = ((fitness - best) / best)
    if max:
        gap = 1.0 - gap
    return gap

def get_overall_bests(data, max : bool = False):
    n_instances = len(data[0])
    bests = []
    for i in range(n_instances):
        if max:
            bests.append(max([solver[i][0] for solver in data]))
        else:
            bests.append(min([solver[i][0] for solver in data]))
    return bests

def overall_gaps(data, max : bool = False):
    n_instances = len(data[0])
    overall_bests = get_overall_bests(data)
    overall_gaps = [[calculate_gap(solver[i][0], overall_bests[i]) for i in range(n_instances)] for solver in data]
    for gaps in overall_gaps:
        if not max:
            gaps.sort()
        else:
            gaps.sort(reverse=True)
    return overall_gaps

def get_all_timestamps(data, max : bool = False, max_diff : float = 0.1):
    results_fitness_overall = [get_timestamps(get_overall_bests(data), solver, max_diff=max_diff) for solver in data]
    results_fitness_self = [get_timestamps([solver[i][0] for i in range(len(solver))], solver, max_diff=max_diff) for solver in data]
    for fitness_overall in results_fitness_overall:
        fitness_overall.sort()
    for fitness_self in results_fitness_self:
        fitness_self.sort()
    return results_fitness_overall, results_fitness_self

def get_timestamps(targets, data, max : bool = False, max_diff : float = 0.1):
    result = []
    for i in range(len(targets)):
        target = targets[i]
        if max:
            target *= (1.0-max_diff)
        else:
            target *= (1.0+max_diff)
        for j in range(len(data[i][1])):
            if (not max and data[i][1][j][1] <= target) or (max and data[i][1][j][1] >= target):
                result.append(data[i][1][j][0])
                break
    return result
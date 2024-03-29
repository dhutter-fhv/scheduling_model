def get_data(id):
    n_workstations = 0
    recipes = []
    operation_times = []
    if id == 0:
        # Instance 1, Kacem et al. (2002b)
        n_workstations = 5
        recipes = [3, 3, 4, 2]  # contains amount of tasks per recipe
        operation_times = [
            [2, 5, 4, 1, 2], # recipe 0, task 0 processing times on workstations 0, 1, 2, 3, 4
            [5, 4, 5, 7, 5], # recipe 0, task 1 processing times on workstations 0, 1, 2, 3, 4
            [4, 5, 5, 4, 5], # recipe 0, task 2 processing times ...
            [2, 5, 4, 7, 8], # recipe 1, task 0 processing times
            [5, 6, 9, 8, 5], # recipe 1, task 1 processing times
            [4, 5, 4, 54, 5], # . . .
            [9, 8, 6, 7, 9],
            [6, 1, 2, 5, 4],
            [2, 5, 4, 2, 4],
            [4, 5, 2, 1, 5],
            [1, 5, 2, 4, 12],
            [5, 1, 2, 1, 2]
        ]
    elif id == 1:
        # Instance 2, Kacem et al. (2002b)
        n_workstations = 7
        recipes = [3, 2, 3, 3, 3, 3, 3, 3, 3, 3]
        operation_times = [
            [2, 8, 5, 8, 9, 4, 3],
            [5, 3, 8, 1, 9, 3, 6],
            [1, 2, 6, 4, 1, 7, 2],
            [7, 1, 8, 5, 4, 3, 9],
            [2, 4, 5, 10, 6, 4, 9],
            [5, 1, 7, 1, 6, 6, 2],
            [8, 7, 4, 56, 9, 8, 4],
            [5, 14, 1, 9, 6, 5, 8],
            [3, 5, 2, 5, 4, 5, 7],
            [5, 6, 3, 6, 5, 15, 2],
            [6, 5, 4, 9, 5, 4, 3],
            [9, 8, 2, 8, 6, 1, 7],
            [6, 1, 4, 1, 10, 4, 3],
            [11, 13, 9, 8, 9, 10, 8],
            [4, 2, 7, 8, 3, 10, 7],
            [12, 5, 4, 5, 4, 5, 5],
            [4, 2, 15, 99, 4, 7, 3],
            [9, 5, 11, 2, 5, 4, 2],
            [9, 4, 13, 10, 7, 6, 8],
            [4, 3, 25, 3, 8, 1, 2],
            [1, 2, 6, 11, 13, 3, 5]
        ]
    elif id == 2:
        # Instance 3, Kacem et al. (2002b)
        n_workstations = 10
        recipes = [3, 3, 3, 3, 3, 3, 3, 3, 3, 3]
        operation_times = [
            [1, 4, 6, 9, 3, 5, 2, 8, 9, 5],
            [4, 1, 1, 3, 4, 8, 10, 4, 11, 4],
            [3, 2, 5, 1, 5, 6, 9, 5, 10, 3],
            [2, 10, 4, 5, 9, 8, 4, 15, 8, 4],
            [4, 8, 7, 1, 9, 6, 1, 10, 7, 1],
            [6, 11, 2, 7, 5, 3, 5, 14, 9, 2],
            [8, 5, 8, 9, 4, 3, 5, 3, 8, 1],
            [9, 3, 6, 1, 2, 6, 4, 1, 7, 2],
            [7, 1, 8, 5, 4, 9, 1, 2, 3, 4],
            [5, 10, 6, 4, 9, 5, 1, 7, 1, 6],
            [4, 2, 3, 8, 7, 4, 6, 9, 8, 4],
            [7, 3, 12, 1, 6, 5, 8, 3, 5, 2],
            [7, 10, 4, 5, 6, 3, 5, 15, 2, 6],
            [5, 6, 3, 9, 8, 2, 8, 6, 1, 7],
            [6, 1, 4, 1, 10, 4, 3, 11, 13, 9],
            [8, 9, 10, 8, 4, 2, 7, 8, 3, 10],
            [7, 3, 12, 5, 4, 3, 6, 9, 2, 15],
            [4, 7, 3, 6, 3, 4, 1, 5, 1, 11],
            [1, 7, 8, 3, 4, 9, 4, 13, 10, 7],
            [3, 8, 1, 2, 3, 6, 11, 2, 13, 3],
            [5, 4, 2, 1, 2, 1, 8, 14, 5, 7],
            [5, 7, 11, 3, 2, 9, 8, 5, 12, 8],
            [8, 3, 10, 7, 5, 13, 4, 6, 8, 4],
            [6, 2, 13, 5, 4, 3, 5, 7, 9, 5],
            [3, 9, 1, 3, 8, 1, 6, 7, 5, 4],
            [4, 6, 2, 5, 7, 3, 1, 9, 6, 7],
            [8, 5, 4, 8, 6, 1, 2, 3, 10, 12],
            [4, 3, 1, 6, 7, 1, 2, 6, 20, 6],
            [3, 1, 8, 1, 9, 4, 1, 4, 17, 15],
            [9, 2, 4, 2, 3, 5, 2, 4, 10, 23]
        ]
    elif id == 3:
        # Instance 4, Kacem et al. (2002b)
        n_workstations = 10
        recipes = [4, 4, 4, 4, 4, 2, 2, 4, 4, 4, 4, 4, 4, 4, 4]
        operation_times = [
            [1, 4, 6, 9, 3, 5, 2, 8, 9, 4],
            [1, 1, 3, 4, 8, 10, 4, 11, 4, 3],
            [2, 5, 1, 5, 6, 9, 5, 10, 3, 2],
            [10, 4, 5, 9, 8, 4, 15, 8, 4, 4],
            [4, 8, 7, 1, 9, 6, 1, 10, 7, 1],
            [6, 11, 2, 7, 5, 3, 5, 14, 9, 2],
            [8, 5, 8, 9, 4, 3, 5, 3, 8, 1],
            [9, 3, 6, 1, 2, 6, 4, 1, 7, 2],
            [7, 1, 8, 5, 4, 9, 1, 2, 3, 4],
            [5, 10, 6, 4, 9, 5, 1, 7, 1, 6],
            [4, 2, 3, 8, 7, 4, 6, 9, 8, 4],
            [7, 3, 12, 1, 6, 5, 8, 3, 5, 2],
            [6, 2, 5, 4, 1, 2, 3, 6, 5, 4],
            [8, 5, 7, 4, 1, 2, 36, 5, 8, 5],
            [9, 6, 2, 4, 5, 1, 3, 6, 5, 2],
            [11, 4, 5, 6, 2, 7, 5, 4, 2, 1],
            [6, 9, 2, 3, 5, 8, 7, 4, 1, 2],
            [5, 4, 6, 3, 5, 2, 28, 7, 4, 5],
            [6, 2, 4, 3, 6, 5, 2, 4, 7, 9],
            [6, 5, 4, 2, 3, 2, 5, 4, 7, 5],
            [4, 1, 3, 2, 6, 9, 8, 5, 4, 2],
            [1, 3, 6, 5, 4, 7, 5, 4, 6, 5],
            [1, 4, 2, 5, 3, 6, 9, 8, 5, 4],
            [2, 1, 4, 5, 2, 3, 5, 4, 2, 5],
            [2, 3, 6, 2, 5, 4, 1, 5, 8, 7],
            [4, 5, 6, 2, 3, 5, 4, 1, 2, 5],
            [3, 5, 4, 2, 5, 49, 8, 5, 4, 5],
            [1, 2, 36, 5, 2, 3, 6, 4, 11, 2],
            [6, 3, 2, 22, 44, 11, 10, 23, 5, 1],
            [2, 3, 2, 12, 15, 10, 12, 14, 18, 16],
            [20, 17, 12, 5, 9, 6, 4, 7, 5, 6],
            [9, 8, 7, 4, 5, 8, 7, 4, 56, 2],
            [5, 8, 7, 4, 56, 3, 2, 5, 4, 1],
            [2, 5, 6, 9, 8, 5, 4, 2, 5, 4],
            [6, 3, 2, 5, 4, 7, 4, 5, 2, 1],
            [3, 2, 5, 6, 5, 8, 7, 4, 5, 2],
            [1, 2, 3, 6, 5, 2, 1, 4, 2, 1],
            [2, 3, 6, 3, 2, 1, 4, 10, 12, 1],
            [3, 6, 2, 5, 8, 4, 6, 3, 2, 5],
            [4, 1, 45, 6, 2, 4, 1, 25, 2, 4],
            [9, 8, 5, 6, 3, 6, 5, 2, 4, 2],
            [5, 8, 9, 5, 4, 75, 63, 6, 5, 21],
            [12, 5, 4, 6, 3, 2, 5, 4, 2, 5],
            [8, 7, 9, 5, 6, 3, 2, 5, 8, 4],
            [4, 2, 5, 6, 8, 5, 6, 4, 6, 2],
            [3, 5, 4, 7, 5, 8, 6, 6, 3, 2],
            [5, 4, 5, 8, 5, 4, 6, 5, 4, 2],
            [3, 2, 5, 6, 5 ,4, 8, 5, 6, 4],
            [2, 3, 5, 4, 6, 5, 4, 85, 4, 5],
            [6, 2, 4, 5, 8, 6, 5, 4, 2, 6],
            [3, 25, 4, 8, 5, 6, 3, 2, 5, 4],
            [8, 5, 6, 4, 2, 3, 6, 8, 5, 4],
            [2, 5, 6, 8, 5, 6, 3, 2, 5, 4],
            [5, 6, 2, 5, 4, 2, 5, 3, 2, 5],
            [4, 5, 2, 3, 5, 2, 8, 4, 7, 5],
            [6, 2, 11, 14, 2, 3, 6, 5, 4, 8]
        ]
    return n_workstations, recipes, operation_times
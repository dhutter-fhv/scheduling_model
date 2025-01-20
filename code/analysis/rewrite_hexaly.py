with open(r'/home/dhu/Downloads/results/results_hexaly.txt', 'r') as in_file:
    lines = in_file.readlines()
    result = []
    for line in lines:#[-1:]:
        data = line.split(';')
        if not line.startswith('Error'):
            if data[2] == data[3]:
                data[1] = '1'

        result.append(';'.join(data))
        #print(result)
    with open(r'/home/dhu/Downloads/results/results_hexaly_rewritten.txt', 'w') as out_file:
        out_file.writelines(result)

with open(r'/home/dhu/Downloads/results/results_cplex_lp.txt', 'r') as in_file:
    lines = in_file.readlines()
    result = []
    for line in lines:#[-1:]:
        data = line.split(';')
        if not line.startswith('Error'):
            if data[2] == data[3]:
                data[1] = '1'

        result.append(';'.join(data))
        #print(result)
    with open(r'/home/dhu/Downloads/results/results_cplex_lp_rewritten.txt', 'w') as out_file:
        out_file.writelines(result)

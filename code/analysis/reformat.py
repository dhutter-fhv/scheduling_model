from os import listdir
base_path = '/home/dhu/Downloads/ga_results'
files = listdir(base_path)

for file in files:
    reading = True
    counter = 0
    out_text = ['[']
    new_entry = False
    with open(f'{base_path}/{file}', 'r') as f:
        print(f'Converting: {file}')
        while reading:
            c = f.read(1)
            if c:
                if new_entry:
                    out_text.append(',')
                    new_entry = False
                out_text.append(c)
                if c == '{':
                    counter += 1
                elif c == '}':
                    counter -= 1
                    if counter == 0:
                        new_entry = True
            else:
                reading = False
        out_text.append(']')
        with open(f'{base_path}/../converted/{file}', 'w') as out_file:
            out_text = ''.join(out_text)
            out_file.write(out_text)
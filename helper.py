from typing import Dict, List, Tuple, IO
from functools import reduce
def list_to_string(data:List[str]):
    return reduce(lambda a,b: a+"\n"+b, data)

def write_table(f:IO, dims:List[int], data:List[List[str]]):
    f.write("\\begin{table}[h]"+"\n")
    tmp=reduce(lambda a,b: a+"|"+b, ["l" for _ in range(dims[0])])
    f.write("\\begin{tabular}{|"+f"{tmp}"+"|}\n")
    f.write("\\hline"+"\n")
    for i in range(dims[1]):
        f.write(reduce(lambda a,b: a+"&"+b, [data[i][j] for j in range(dims[0])])+"\\\\ \\hline\n")
    f.write("\\end{tabular}"+"\n")
    f.write("\\end{table}"+"\n")
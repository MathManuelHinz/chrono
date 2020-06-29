from typing import Dict, List, Tuple, IO
from functools import reduce
from datetime import datetime, date

def is_in(t1:datetime, b1:datetime, b2:datetime)->bool:
    assert b1 < b2
    return t1 >= b1 and t1 <= b2

def get_intersect(l1:List, l2:List)->List:
    return list(filter(lambda x: x in l2, l1))

def get_color(scheme:Dict[str, str], tags:List[str])->str:
    for tag in tags:
        if tag in scheme.keys():
            return scheme[tag]
    print(f"Used default color for {tags}")
    return scheme["default"]

def list_to_string(data:List[str])->str:
    return reduce(lambda a,b: a+"\n"+b, data)

def write_table(f:IO, dims:List[int], data:List[List[str]])->None:
    f.write("\\begin{table}[h]"+"\n")
    tmp=reduce(lambda a,b: a+"|"+b, ["l" for _ in range(dims[0])])
    f.write("\\begin{tabular}{|"+f"{tmp}"+"|}\n")
    f.write("\\hline"+"\n")
    for i in range(dims[1]):
        f.write(reduce(lambda a,b: a+"&"+b, [data[i][j] for j in range(dims[0])])+"\\\\ \\hline\n")
    f.write("\\end{tabular}"+"\n")
    f.write("\\end{table}"+"\n")

def split_command(command:str)->List[str]:
    #Die Ecken
    if "\"" in command:
        s=int(command.find("\""))
        for i in range(s+1, len(command)):
            if command[i]=="\"":
                if not s==0:
                    a=split_command(command[0:s-1])
                else:
                    a=[]
                b=[command[s+1:i]]
                if not i == len(command)-1:
                    c=split_command(command[i+2:])
                else:
                    c=[]
                return a+b+c
    else:
        rtn= command.split(" ")
        return list(filter(lambda l: not l=="", rtn))
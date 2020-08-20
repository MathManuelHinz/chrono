from subprocess import call
from typing import Dict, List, Tuple, IO,Callable
from functools import reduce
from datetime import datetime, date, time

WEEKDAYS=["Monday", "Tuesday", "Wendsday", "Thursday", "Friday","Saturday", "Sunday"]

SECONDS_IN_A_DAY=86400

MSSH_color_scheme:Dict[str, str]={
    "default":"black",
    "leben":"black",
    "relax":"black",
    "mathe":"red",
    "uni":"red",
    "creative":"green",
    "programming":"blue",
    "tine":"magenta",
    "korean":"magenta"
}

def is_in(t1:datetime, b1:datetime, b2:datetime)->bool:
    """Checks if t1 is in between b1 and b2. Asserts that b1 < b2."""
    assert b1 < b2
    return t1 >= b1 and t1 <= b2

def get_intersect(l1:List, l2:List)->List:
    """Gets the intersection of two lists."""
    return list(filter(lambda x: x in l2, l1))

def get_color(scheme:Dict[str, str], tags:List[str])->str:
    """Failsave way to get a color based on a color scheme. Can only fail if scheme does not contain the key \"default\"."""
    for tag in tags:
        if tag in scheme.keys():
            return scheme[tag]
    print(f"Used default color for {tags}")
    return scheme["default"]

def list_to_string(data:List[str])->str:
    """Reduces a list of strings to a single string with linebreaks between two elements of the list."""
    return reduce(lambda a,b: a+"\n"+b, data)

def write_table(f:IO, dims:List[int], data:List[List[str]])->None:
    """Writes a table (LaTex) representing the data 2d list."""
    f.write("\\begin{table}[h]"+"\n")
    tmp=reduce(lambda a,b: a+"|"+b, ["l" for _ in range(dims[0])])
    f.write("\\begin{tabular}{|"+f"{tmp}"+"|}\n")
    f.write("\\hline"+"\n")
    for i in range(dims[1]):
        f.write(reduce(lambda a,b: a+"&"+b, [data[i][j] for j in range(dims[0])])+"\\\\ \\hline\n")
    f.write("\\end{tabular}"+"\n")
    f.write("\\end{table}"+"\n")

def split_command(command:str)->List[str]:
    """Splits commands by spaces, ignoring content in quotes."""
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

def get_seconds(t:time)->int:
    """Returns the seconds in a time object."""
    return t.second + t.minute*60 + t.hour*60*60

def get_lambda(alias:str,cmds=Dict[str, Callable]):
    """Turns an alias (see alias documentation) into a function."""
    splitcmd=split_command(alias)
    return (lambda *xs: cmds[splitcmd[0]](xs[0],xs[1],*[arg if (not "$" in arg) else xs[int(arg.replace("$",""))+1] for arg in splitcmd[1:]]))

def time_from_str(str_time:str)->time:
    """Returns the time object associated with the given string."""
    return time(int(str_time[0:2]),int(str_time[3:5]))

def date_from_str(str_date:str)->date:
    """Returns the date object associated with the given string."""
    return date(int(str_date[0:4]),int(str_date[5:7]),int(str_date[8:10])) 

def get_tf_length(tf:Tuple[time, time])->int:
    """Returns the length of a timeframe."""
    return abs((tf[1].hour-tf[0].hour)*60*60+(tf[1].minute-tf[0].minute)*60+(tf[1].second-tf[0].second))

def seconds_to_time(seconds:int)->time:
    """Converts seconds to a time object."""
    seconds = seconds % (24 * 3600) 
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return time(hour=hours,minute=minutes,second=seconds) 
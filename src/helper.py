import logging
import sqlite3
from typing import Dict, Generator, List, Tuple, IO, Callable, Any
from functools import reduce
from datetime import datetime, time
from inspect import signature
from collections.abc import Iterable
import matplotlib.pyplot as plt
from math import floor
from datetime import timedelta

WEEKDAYS=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday","Saturday", "Sunday"]

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

def is_iterable(obj:Any)->bool:
    """Checks if a given object is an iterable."""
    return isinstance(obj, Iterable)

def get_two(list:List[Any])->Generator[Any,None,None]: #better type soon
    """cursed"""
    for x in list:
        if is_iterable(x) and not isinstance(x,str):
            for e in x:
                yield e
        else:
            yield x


def is_in(t1:datetime, b1:datetime, b2:datetime)->bool:
    """Checks if t1 is in between b1 and b2. Asserts that b1 < b2."""
    assert b1 < b2
    return t1 >= b1 and t1 <= b2

def get_intersect(l1:List[Any], l2:List[Any])->List[Any]:
    """Gets the intersection of two lists."""
    return list(filter(lambda x: x in l2, l1))

def get_color(scheme:Dict[str, str], tags:List[str])->str:
    """Failsave way to get a color based on a color scheme. Can only fail if scheme does not contain the key \"default\"."""
    for tag in tags:
        if tag in scheme.keys():
            return scheme[tag]
    logging.warn(f"Used default color for {tags}")
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

def split_command(command:str)->List[str]:  # type: ignore
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

def get_nargs(f:Callable[[Any],Any])->int:
    """Gets the number of arguments a given function takes."""
    sig=signature(f)
    return len(sig.parameters)

def get_slice_start(args:List[str])->int:
    """Helper function specifically to be used by cursed_get_lambda."""
    indis=[int(arg.replace("$","")) for arg in args if "$" in arg and "$N" not in arg]
    return sum(indis)+2

def cursed_get_lambda(alias:str,cmds=Dict[str, Callable[[Any],Any]])->Callable[[Any],Any]:
    """Turns an alias (see alias documentation) into a function. Works with multiple commands. Either cursed or genius, edit: definitely cursed."""
    get_cmds=(alias.split(" |> ")) #Inspired by f#
    splitcmds=[split_command(cmd) for cmd in get_cmds]
    return (lambda *xs: reduce(lambda acc, sc: cmds[sc[0].lower()](xs[0],acc,*get_two([arg if (not "$" in arg)\
         else (xs[int(arg.replace("$",""))+1] if (not "$N" in arg) else xs[slice(get_slice_start(sc[1:]),None)]) for arg in sc[1:]])), splitcmds, xs[1]))

def time_from_str(str_time:str)->time:
    """Returns the time object associated with the given string."""
    return time(int(str_time[0:2]),int(str_time[3:5]))

def get_tf_length(tf:Tuple[time, time])->int:
    """Returns the length of a timeframe."""
    return abs((tf[1].hour-tf[0].hour)*60*60+(tf[1].minute-tf[0].minute)*60+(tf[1].second-tf[0].second))

def seconds_to_time(seconds:int)->time:
    """Converts seconds to a time object."""
    seconds=abs(seconds)
    seconds = seconds % (24 * 3600) 
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return time(hour=hours,minute=minutes,second=seconds) 

def sleepdata_to_time(sleepdata:Tuple[time,time,bool])->time:
    """Converts sleepdata to a time object describing the sleep duration.""" 
    return seconds_to_time(seconds=abs(get_tf_length((sleepdata[0],sleepdata[1]))-int(sleepdata[2])*(SECONDS_IN_A_DAY)))

def what_or_none(l:List[Any],scheme:Dict[str,str])->str:
    """Returns the first element of a List of ChronoEvents by representing it as a colored string. 
    If the given list has no first element the string \"Nothing\" is returned."""

    if len(l)>0:
        return "\\textcolor{"+get_color(scheme, l[0].tags)+"}{"+f"{l[0].what[:15]}"+"}"  
    else:
        return ""

def concatsem(a:str,b:str)->str:
    return a+";"+b

def get_pace_ticks(ysp:List[float],n:int=5)->Tuple[List[float],List[str]]:
    ysp.sort()
    assert not n==0
    return [ysp[i*int(len(ysp)/n)] for i in range(n)], [seconds_to_time(int(ysp[i*int(len(ysp)/n)])).isoformat()[3:] for i in range(n)]

def heatmap(project, tag:str, reference:str, start_date:str="start", end_date:str="stop", title=""):
    """Draws a heat map for a specific var:tag with at most 15 vertical labels with data from 
    [var:start_date,var:end_date]."""
    if title=="": title="Heatmap: " + tag
    days=project.analysis_get_between(start_date,end_date,reference)
    events=list(filter(lambda a: tag in a[0].tags,
        reduce(lambda a,b: a+b, [[(event,day.date) for event in day.events] for day in days])))
    starts=[]
    ends=[]
    for event in events:
        starts.append(event[0].start)
        ends.append(event[0].end)
    start:time=time(hour=min(starts).hour)
    if (ehour:=max(ends).hour)==23:
        end:time=time(hour=23,minute=59)
    else:
        end:time=time(hour=ehour+1)
    td=datetime.today()
    steps=(end.hour-start.hour)*4
    yt=min(15, steps)
    timeframes=[[(datetime.combine(td,start)+i*timedelta(minutes=15)),(datetime.combine(td,start)+(i+1)*timedelta(minutes=15))]
        for i in range(steps)]
    heatmap:List[List[float]]=[[0 for __ in range(7)] for _ in timeframes]
    for event in events:
        estart=datetime.combine(datetime.today(), event[0].start)
        eend=datetime.combine(datetime.today(), event[0].end)
        for i, t in enumerate(timeframes):
            if t[0]<=estart<=t[1] or t[0]<=eend<=t[1] or estart<=t[0]<=eend or estart<=t[1]<=eend:
                    heatmap[i][event[1].weekday()]+=1
    plt.imshow(heatmap, cmap="hot",interpolation="nearest", aspect=10/steps)
    plt.title(title)
    plt.xticks([i for i in range(7)], map(lambda x: x[:3],WEEKDAYS))
    plt.yticks([floor(i*(steps-1)/yt) for i in range(yt)], [timeframes[floor(i*(steps-1)/yt)][0].time() for i in range(yt)])
    plt.colorbar()
    plt.get_current_fig_manager().set_window_title(title)

def create_db(cur:sqlite3.Cursor):
    """Create database (sqlite)."""
    cur.execute('''CREATE TABLE IF NOT EXISTS
    ChronoDay
               (date date NOT NULL, 
                PRIMARY KEY(date))''')
    cur.execute('''CREATE TABLE IF NOT EXISTS
    ChronoEvent
               (event_id INTEGER NOT NULL, 
                date date NOT NULL,
                what TEXT NOT NULL,
                tags TEXT NOT NULL,
                start TIME NOT NULL,
                end TIME NOT NULL,
                PRIMARY KEY(event_id),
                FOREIGN KEY(date) REFERENCES ChronoDay(date))''')
    cur.execute('''CREATE TABLE IF NOT EXISTS
    ChronoTime
               (time_id INTEGER NOT NULL, 
                date date NOT NULL,
                what TEXT NOT NULL,
                tags TEXT NOT NULL,
                start TIME NOT NULL,
                PRIMARY KEY(time_id),
                FOREIGN KEY(date) REFERENCES ChronoDay(date))''')
    cur.execute('''CREATE TABLE IF NOT EXISTS
    ChronoPlank
               (plank_id INTEGER NOT NULL, 
                date date NOT NULL,
                time real NOT NULL,
                start_time TIME NOT NULL,
                PRIMARY KEY(plank_id),
                FOREIGN KEY(date) REFERENCES ChronoDay(date))''')
    cur.execute('''CREATE TABLE IF NOT EXISTS
    ChronoNote
               (note_id INTEGER NOT NULL, 
                text TEXT NOT NULL,
                datetime TEXT NOT NULL,
                PRIMARY KEY(note_id))''')
    cur.execute('''CREATE TABLE IF NOT EXISTS
    ChronoRun
               (run_id INTEGER NOT NULL, 
                date date NOT NULL,
                time TIME NOT NULL,
                start_time TIME NOT NULL,
                distance REAL NOT NULL,
                PRIMARY KEY(run_id),
                FOREIGN KEY(date) REFERENCES ChronoDay(date))''')
    cur.execute('''CREATE TABLE IF NOT EXISTS
    ChronoPushup
               (pushup_id INTEGER NOT NULL, 
                date date NOT NULL,
                reps int,
                time real NOT NULL,
                start_time TIME NOT NULL,
                PRIMARY KEY(pushup_id),
                FOREIGN KEY(date) REFERENCES ChronoDay(date))''')

def times_tags_to_ints(times:List[List[time]])->List[List[int]]:
    return [[t.hour*60*60+t.minute*60+t.second for t in tl] for tl in times]

def time_to_int(t:time)->int:
    return t.hour*60*60+t.minute*60+t.second

def add_time_delta(t:time,td:timedelta):
    return (datetime.combine(datetime.today().date(),t)+td).time()

def str_to_seconds(str_s:str)->int:
    if str_s.count(":")==1:
        return int(str_s[0:2])*60+int(str_s[3:5])
    elif str_s.count(":")==2:
        return int(str_s[0:2])*60*60+int(str_s[3:5])*60+int(str_s[6:8])
    else:
        raise Exception(f"Invalid input: {str_s}")
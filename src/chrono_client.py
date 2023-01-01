import json
import logging
import os
import shutil
import subprocess
import calendar
from datetime import (date, datetime, time, timedelta)
from functools import reduce
from inspect import signature, Parameter
from typing import (Callable, Dict, List, Tuple, Union, Set, Optional, Any)
from os import mkdir, path
import networkx as nx
import sqlite3
import imageio
import src.monotone_clustering as mc
import numpy as np
from scipy.fft import fft, fftfreq

import matplotlib.pyplot as plt
import matplotlib.animation as animation

from src.helper import (create_db, get_color, get_intersect, heatmap, list_to_string, seconds_to_time, split_command, str_to_seconds, times_tags_to_ints,
                    write_table, time_from_str, get_tf_length, 
                    WEEKDAYS, MSSH_color_scheme, sleepdata_to_time, cursed_get_lambda, what_or_none, 
                    concatsem, get_pace_ticks,times_tags_to_ints, time_to_int, add_time_delta, fix_oura, get_sleep_phase)

from src.sport import (ChronoPlankEvent, ChronoRunningEvent, ChronoSitUpsEvent, 
                   ChronoPushUpEvent, ChronoSportEvent)

from src.atoms import (ChronoEvent, ChronoTime, ChronoNote)

from src.oura import get_sleep

VERSION="2.0.0.d"

REF_MAN="Reference Management"
DAY_MAN="ChronoDay Management"
EVE_MAN="ChronoEvent Management"
SPO_MAN="ChronoSport Management"
ANA="Analysis"
EXP="Export"
DIS="Display"
NOT="Notes"
OUR="Oura"
MIS="Miscellanea"

class ChronoDay:
    """This class is used to organize ChronoEvent- and  ChronoTimes-objects. 
    Each page in the exported pdf should correspond to one ChronoDay-object."""
     
    events:List[ChronoEvent]
    date:date
    silent_events:List[ChronoTime]
    sport:Dict[str, List[ChronoSportEvent]]
    functions:Dict[str,float]

    def __init__(self, events:List[ChronoEvent], input_date:str):
        """Constructor: ChronoDay.
        input_date will be converted to a date object and
        events will be saved as is. 
        Attributes:
            events: A list of ChronoEvents. 
            input_date: The date of the Day. Should be of the format YYYY-MM-DD"""
        self.events=events
        self.date=date(int(input_date[0:4]),int(input_date[5:7]),int(input_date[8:10])) 
        self.silent_events=[]
        self.sport={"runs":[],"pushups":[],"planks":[],"situps":[]}
        self.sleep=""
        self.functions=dict()

    def __repr__(self)->str:
        """Returns a string representation of this object. Used by the command today"""
        if self.events == []:
            return  f"{self.date.__str__()}:\n\n"
        else: return f"{self.date.__str__()}:\n" + reduce(lambda a,b: a+"\n\n"+b, [event.__repr__() for event in sorted(self.events, key=lambda x: x.start)], "") +"\n"

    def check_overlap(self, event1:ChronoEvent, event2:ChronoEvent)->bool:
        """Checks if two events overlap."""
        if event1.start==event2.start:
            rtn=True 
        elif event1.start < event2.start:
            rtn= event2.start < event1.end
        else:
            rtn= event1.start < event2.end
        return rtn

    def add_event(self, event:ChronoEvent, force:bool=False)->None:
        """
        This function tries to add an event to the events list. 
        This fails if there is an overlap with an already existing event. Adding the event can be forced by 
        setting force to True. In this case overlapping existing events will be deleted. 
        """
        if not reduce(lambda a,b: a or b, [self.check_overlap(e, event) for e in self.events], False) or self.events==[]:
            self.events.append(event)
        elif force:
            self.events.append(event)
            todel=[]
            for e in self.events:
                if self.check_overlap(e, event) and not e==event:
                    todel.append(e)
            for e in todel:
                self.events.remove(e)
        else:
            logging.warning(f"Failed to add {event} on {self.date}") 
            raise Exception("Overlap")

    def get_slots(self)->List[ChronoEvent]:
        """Returns the events sorted by starting time."""
        return sorted(self.events, key=lambda x:x.start)

    def get_bounds(self)->Tuple[time, time]:
        """Returns the earliest starting time and the latest ending time."""
        assert not self.events==[]
        starts=[event.start for event in self.events]
        ends=[event.end for event in self.events]
        return min(starts), max(ends)

    def merge(self)->None:
        """Merges two events into one if they have the same what attribute and no time in between them."""
        self.events.sort(key=lambda x:x.start)
        for e1 in self.events:
            for e2 in self.events:
                if not e1==e2 and e1.end==e2.start and e1.what==e2.what and e1.tags==e2.tags:
                    e=ChronoEvent(e1.start.isoformat(), e2.end.isoformat(), e1.what, list(set(e1.tags+e2.tags)))
                    logging.critical(f"merged to {e}")
                    self.events.remove(e1)
                    self.events.remove(e2)
                    self.add_event(e)
                    return self.merge()

    def to_dict(self)->Dict[str, Union[str, Dict[str, Union[str, List[str]]],List[Dict[str, Union[str, List[str]]]]]]:
        """Used to save the object as a json."""
        d:Dict[str, Union[str, Dict[str, Union[str, List[str]]]]]=dict()
        d["date"]=self.date.__str__()
        d["events"]=[event.to_dict() for event in self.events]
        d["sport"]={key:[entry.to_dict() for entry in self.sport[key]] for key in self.sport.keys()}
        d["functions"]=self.functions
        d["sleep"]=self.sleep
        return d

    def add_run(self, run:ChronoRunningEvent)->None:
        """Adds a run event to the "runs" list."""
        self.sport["runs"].append(run)
        self.update_after_run()

    def add_situp(self, sit:ChronoSitUpsEvent)->None:
        """Adds a situp event to the "situp" list."""
        self.sport["situps"].append(sit)

    def add_pushup(self, pu:ChronoPushUpEvent)->None:
        """Adds a pushup event to the "pushup" list."""
        self.sport["pushups"].append(pu)

    def add_plank(self, plank:ChronoPlankEvent)->None:
        """Adds a plank event to the "plank" list."""
        self.sport["planks"].append(plank)

    def get_tags(self)->List[str]:
        return list(set(reduce(lambda a,b:a+b,[event.tags for event in self.events])))

    def add_function(self, function_name:str, function_value:float):
        self.functions[function_name]=function_value
        return

    def get_function(self, function_name:str)->float:
        if function_name in self.functions.keys():
            return self.functions[function_name]
        else: return 0
    
    def update_after_run(self):
        self.add_function("run_time",sum([run.time/3600 for run in self.sport["runs"]]))
        self.add_function("run_distance",sum([run.distance for run in self.sport["runs"]]))

class ChronoSchedule:
    
    days:List[List[List[ChronoEvent]]]
    sdays:List[List[List[Dict[str, Any]]]]

    def __init__(self, path:str):
        """Constructor of ChronoSchedule."""
        with open(path, "r+", encoding="utf-8") as f:
            data=json.load(f)
        self.days=[[[] for _ in range(7)] for i in range(len(data["events"]))]
        for i,week in enumerate(data["events"]):
            for j  in range(7):
                self.days[i][j]=[ChronoEvent(e["start"], e["end"], e["what"], e["tags"]) for e in week[j]]
        self.sdays=[[[] for _ in range(7)] for i in range(len(data["sevents"]))]
        for i,week in enumerate(data["sevents"]):
            for j  in range(7):
                self.sdays[i][j]=[{"start":day["start"],"what":day["what"],"tags":day["tags"]} for day in week[j]]

class ChronoProject:

    path:str
    name:str
    todo:List[ChronoNote]
    days:Dict[str, ChronoDay]
    sevents:List[ChronoTime]
    schedule:ChronoSchedule
    schedulemod:int
    scheme:Dict[str, str]
    forbidden:List[str]

    def __init__(self, name:str, path:str):
        """Constructor of ChronoProject."""
        self.name=name
        self.path=path
        self.days=dict()
        self.sevents=[]
        self.schedule=None
        self.todo=[]
        self.header=["\\documentclass{article}"]
        self.scheme=MSSH_color_scheme
        self.load_settings()
        self.forbidden=["sleep_phase_deep","sleep_phase_light","sleep_phase_rem","sleep_phase_awake","all_sleep","run_distance","run_time"]

    def set_schedule(self,schedule:ChronoSchedule)->None:
        """Sets the schedule for this project."""
        self.schedule=schedule
        if schedule==None: self.schedulemod=0
        else: self.schedulemod=len(self.schedule.days)        

    def load_settings(self)->None:
        """ Loads settings from "settings.json"."""
        with open("data/settings.json", "r+", encoding="utf-8") as f:
            self.settings=json.load(f)
        self.settings["alias"]={key.lower():self.settings["alias"][key]for key in self.settings["alias"].keys()}
        self.scheme=self.settings["color_scheme"]

    def set_alias(self, cmds:Dict[str,Callable])->None:
        """Creates the alias Dict. Needs load_settings to be called first"""
        self.alias={key.lower():cursed_get_lambda(self.settings["alias"][key], cmds) for key in self.settings["alias"].keys()}

    def add_note(self, note:ChronoNote)->None:
        """ Adds a note to the todo list."""
        if not note.text in map(lambda x: x.text, self.todo):
            self.todo.append(note)
        else:
            print("duplicate ChronoNote")

    def add_day(self,day:ChronoDay)->None:
        """Adds a day to the days dict."""
        if not day.date.isoformat() in self.days.keys():
            if self.settings["schedule"] and day.events==[]:
                #day.events += self.schedule.days[int(day.date.isocalendar()[1])%self.schedulemod][day.date.weekday()]
                for event in self.schedule.days[int(day.date.isocalendar()[1])%self.schedulemod][day.date.weekday()]:
                    day.add_event(event)
                day.merge()
            self.days[day.date.isoformat()]=day
            if self.settings["schedule"]:
                sevents = []
                td=timedelta(days=1)
                cd:date=day.date
                for _ in range(self.settings["schedule_headsup"]+1):
                    week=cd.isocalendar()[1]%len(self.schedule.sdays)
                    weekday=cd.weekday()
                    sevents += [ChronoTime(cd.isoformat(), sevent["start"], sevent["what"], sevent["tags"]) for sevent in self.schedule.sdays[week][weekday]]
                    cd += td
                self.sevents=list(set(self.sevents+sevents))
        else:
            print(f"Adding {day.date} failed ...")
            logging.warning(f"can`t add day {day.date.isoformat()}")

    def add_event(self, event:ChronoEvent, date:str, force:bool=False)->None:
        """ Adds a ChronoEvent to a given day."""
        self.days[date].add_event(event, force)

    def __repr__(self)->str:
        """Represents this object as a string."""
        return reduce(lambda a,b: a+"\n"+b, [day.__repr__() for day in self.days.values()])

    def get_meta(self)->List[str]:
        """Generates metadata for the LaTeX file."""
        return ["\\title{" + f"{self.name}"+"}"]

    def export_pdf(self, days:List[str]=[""])->None:
        """ Exports the object to a LaTeX -> PDF file."""
        if not path.exists("./pdfs/"):
                mkdir("./pdfs/")
        if days==[""]:
            days=[day for day in self.days.keys()]
        days=[self.days[key] for key in filter(lambda x: x in self.days.keys(), days)]
        header=["\\documentclass{article}", "\\usepackage{xcolor}","\\usepackage{hyperref}"]
        with open(self.name+".tex", "w+", encoding="utf-8") as f:
            f.write(list_to_string(header)+"\n"+list_to_string(self.get_meta())+"\n")
            f.write("\\begin{document}\n")
            f.write("\\maketitle\n")
            for day in sorted(days, key=lambda x: x.date):
                if day.events == []:
                    pass
                else:
                    day.merge()
                    f.write("\\section*{"+f"{day.date}"+ "}\n")
                    f.write("\\hypertarget{"+f"{day.date}"+"}{}\n")
                    slots=day.get_slots()
                    data=[[f"{slot.start.isoformat()}-{slot.end.isoformat()}", "\\textcolor{"+get_color(self.scheme, slot.tags)+"}{"+f"{slot.what}"+"}"]for slot in slots]
                    write_table(f, [2, len(slots)], data=data)
                    write_table(f, [2, len(day.silent_events)], data=[[time.start.isoformat(), time.what] for time in day.silent_events])
                    f.write("\\clearpage")
            f.write("\\end{document}\n")
        subprocess.run(["pdflatex", self.name+".tex"], stdout=subprocess.DEVNULL)
        subprocess.run(["pdflatex", self.name+".tex"], stdout=subprocess.DEVNULL)
        if os.path.isfile(f"{self.name}.log"):os.remove(f"{self.name}.log")
        if os.path.isfile(f"{self.name}.aux"):os.remove(f"{self.name}.aux")
        if os.path.isfile(f"{self.name}.nav"):os.remove(f"{self.name}.nav")
        if os.path.isfile(f"{self.name}.out"):os.remove(f"{self.name}.out")
        if os.path.isfile(f"{self.name}.toc"):os.remove(f"{self.name}.toc")
        if os.path.isfile(f"{self.name}.tex"):os.remove(f"{self.name}.tex")
        os.replace(self.name+".pdf","./pdfs/"+self.name+".pdf")
        
    def save(self, path:Optional[str]=None)->None:
        """Saves the current state of the project to a json file. """
        if path == None: path=self.path
        export=dict()
        export["todo"]=[note.to_dict() for note in self.todo]
        export["name"]=self.name
        export["path"]=path
        export["days"]={key:self.days[key].to_dict() for key in self.days.keys()}
        export["sevents"]=[sev.to_dict() for sev in self.sevents]
        with open("data/"+path+".json", "w+", encoding="utf-8") as f:
            json.dump(export, f, indent=4)

    def get_poi(self)->Set[time]:
        """ Collects all points of interest (starts / ends of all events)."""
        poi=set()
        for day in self.days.values():
            for event in day.events:
                poi.add(event.start)
                poi.add(event.end)
        return poi

    def add_silent(self, stime:ChronoTime)->None:
        """Adds a ChronoTime to sevents."""
        self.sevents.append(stime)

    def analysis_get(self, discriminator:Callable[[ChronoDay],bool])->List[ChronoDay]:
        """Filters the self.days using the discriminator."""
        return [day for day in self.days.values() if discriminator(day)]

    def date_from_str(self, str_date:str, reference:str="")->date:
        """Returns the date object associated with the given string."""
        ds=[day.date for day in self.days.values()]
        if str_date=="start": 
            return min(ds)
        elif str_date=="stop": 
            return max(ds)
        elif str_date=="today": 
            return date.today()
        elif str_date=="ref":
            return date(int(reference[:4]), int(reference[5:7]), int(reference[8:]))
        elif "i" == str_date[0]:
            index=int(str_date[1:])
            return ds[index]
        else:
            return date(int(str_date[0:4]),int(str_date[5:7]),int(str_date[8:10])) 

    def analysis_get_between(self, start_date:str, end_date:str, reference:str)->List[ChronoDay]:
        """Returns a sorted sublist of self.days."""
        start_date_date=self.date_from_str(start_date, reference)
        end_date_date=self.date_from_str(end_date, reference)
        return list(sorted(self.analysis_get(lambda x: start_date_date<=x.date<=end_date_date), key=lambda x: x.date))

    def get_tag_graph(self, start_date:str, end_date:str, reference:str, ignored_tags:List[str]=[])->nx.Graph:
        days=sorted(self.analysis_get_between(start_date,end_date,reference), key=lambda x: x.date)
        g=nx.Graph()
        for day in days:
            for event in day.events:
                if len(event.tags)==1:
                    g.add_node(event.tags[0])
                else:
                    for tag1 in event.tags:
                        for tag2 in event.tags:
                            if tag1 != tag2 and tag1 not in ignored_tags and tag2 not in ignored_tags:                          
                                g.add_edge(tag1, tag2)
        return g

    def get_f_ug(self, g:nx.Graph, start_date:str, end_date:str, reference:str,)->Tuple[Dict[str, float], nx.Graph]:
        rtn:Dict[str, float]={node:0 for node in g.nodes}
        days=self.analysis_get_between(start_date, end_date, reference)
        for day in days:
            for event in day.events:
                tf_length=get_tf_length((event.start, event.end))
                for tag in event.tags:
                    rtn[tag] += tf_length
                    for tag2 in event.tags:
                        if (tag,tag2) in g.edges:
                            g.add_edge(tag,tag2, weight=tf_length) #Ich bin extrem dumm
        return rtn, g

    def get_ccs(self, g:nx.Graph)->List[List[str]]:
        ccs=nx.connected_components(g)
        return [list(cc) for cc in ccs]

    def get_gbl_data(self, start_date:str, end_date:str, reference:str, ignored_tags:List[str]=[])->Tuple[nx.Graph,Dict[str,float]]:
        days=sorted(self.analysis_get_between(start_date,end_date,reference), key=lambda x: x.date)
        g=nx.Graph()
        tags:List[str]=[tag for tag in reduce(lambda a,b:a+b,[day.get_tags() for day in days]) if not tag in ignored_tags]
        f:Dict[str,float]={tag:0 for tag in tags}
        for day in days:
            for event in day.events:
                for tag in event.tags:
                    if not tag in ignored_tags:
                        f[tag]+=get_tf_length((event.start,event.end))/3600
                if len(event.tags)==1 and not event.tags[0]:
                    g.add_node(event.tags[0])
                else:
                    for tag1 in event.tags:
                        for tag2 in event.tags:
                            if tag1 != tag2 and tag1 not in ignored_tags and tag2 not in ignored_tags:                          
                                g.add_edge(tag1, tag2)
        return g,f
    
    def get_tags(self)->List[str]:
        tags=set()
        for day in self.days.values():
            for tag in day.get_tags():
                tags.add(tag)
        return tags

    def get_function(self, date:datetime.date, function_name:str, interpolate:int=0)->float:
        if not date.isoformat() in self.days.keys():
            return 0
        elif function_name in self.days[date.isoformat()].functions.keys():
            return self.days[date.isoformat()].functions[function_name]
        elif interpolate==0:
            return 0
        else:
            days=[date.isoformat() for date in [date-timedelta(days=i) for i in range(1,interpolate)]+[date+timedelta(days=i) for i in range(1,interpolate)]]
            return sum([self.days[date].get_function(function_name) for date in days if date in self.days.keys()])/max(1,len([self.days[date].get_function(function_name) for date in days if date in self.days.keys() and function_name in self.days[date].functions.keys()]))

    def get_functions(self, days:List[ChronoDay])->List[str]:
        fs=set()
        for day in days:
            for f in day.functions.keys():
                fs.add(f)
        return fs


class MSSH:

    @staticmethod
    def c_setr(project:ChronoProject, reference:str, new_reference:str)->str:
        """Sets the reference to var:new_reference. new_reference supports IntelliRef."""
        new_reference=project.date_from_str(new_reference,reference).isoformat()
        if not (new_reference in project.days.keys()): 
            try: 
                print("Couldn`t find reference, generating new ChronoDay.")
                project.add_day(ChronoDay(input_date=new_reference, events=[]))
            except:
                logging.warning("Couldn`t find or create reference.")
                print("Couldn`t find or create reference.")
        return new_reference

    @staticmethod
    def c_create_day(project:ChronoProject, reference:str, date:str, start:str="08:00", end:str="22:00")->str:
        """Creates a ChronoDay given:"""
        if len(date.split("-"))==3:
            project.add_day(ChronoDay(input_date=date, events=[]))
        elif date=="today":
            project.add_day(ChronoDay(input_date=datetime.now().isoformat(), events=[]))
        else:
            print("failed")
            logging.info(f"failed: createDay({reference},{date},{start},{end})")
        return reference

    @staticmethod
    def c_create_event(project:ChronoProject, reference:str, what:str, tags:str="relax", start:str="08:00", end:str="10:00", force:str="1")->str:
        """Creates a ChronoEvent given:"""
        if start == end:
            raise Exception("Requirement: start != end")
        if reference in project.days.keys():
            try:
                if time_from_str(start) <= time_from_str(end):
                    project.add_event(ChronoEvent(start=start, end=end, what=what, tags=tags.split(",")), reference, force=int(force))
                else:
                    next_day=project.date_from_str(reference)+timedelta(days=1)
                    print("Creating 2 Events ...")
                    logging.info("Creating 2 Events ...")
                    project.add_event(ChronoEvent(start=start, end="23:59", what=what, tags=tags.split(",")), reference, force=int(force))
                    project.add_day(ChronoDay(input_date=next_day.isoformat(), events=[]))
                    project.add_event(ChronoEvent(start="00:00", end=end, what=what, tags=tags.split(",")), reference, force=int(force))
            except Exception as e:
                print(e)
                logging.info(e)
        else:
            print("invalid key")
            logging.info(f"invalid key (addEvent) : {reference}")
        return reference

    @staticmethod
    def c_create_time(project:ChronoProject, reference:str, what:str, tags:str, start:str, idate:str="ref")->str:
        """var:idate supports IntelliRef. Creates a ChronoTime given:"""
        idate=project.date_from_str(idate).isoformat()
        try:
            project.add_silent(ChronoTime(idate,start=start,what=what, tags=tags.split(",")))
        except Exception as e:
            print(e)
            logging.info(e)
        return reference

    @staticmethod
    def c_days(project:ChronoProject, reference:str)->str:
        """Prints the days saved in this ChronoProject."""
        print(project.days.keys())
        return reference
    
    @staticmethod
    def c_mk(project:ChronoProject, reference:str, days:str="")->str:
        """Exports a set of days (seperated by commata) to pdf."""
        project.export_pdf([date.today().isoformat() if day=="today" else day for day in days.split(",")])
        return reference

    @staticmethod
    def c_show(project:ChronoProject, reference:str)->str:
        """Exports the ChronoProject to pdf and opens the file."""
        project.export_pdf()
        subprocess.Popen([project.settings["pdfpath"], "/A" ,f"nameddest={date.today().isoformat()}", "./pdfs/"+project.name+".pdf"], shell=True)
        return reference

    @staticmethod
    def c_gen_days(project:ChronoProject, reference:str, days:str="7")->str:
        """Generates the next var:days days (including today)."""
        d=date.today()
        for _ in range(int(days)):
            project.add_day(ChronoDay(input_date=d.isoformat(), events=[]))
            d += timedelta(days=1)
        return reference
    
    @staticmethod
    def c_clear(project:ChronoProject, reference:str, code:str="0")->str:
        """Saves the project to a backup and deletes all days if the var:code is correct."""
        if code == project.settings["code"]:
            project.save(path=project.path+"_backup") 
            project.days={}
        else:
            logging.warning(f"wrong code: {code}")
        return reference

    @staticmethod
    def c_clear_future(project:ChronoProject, reference:str, code:str="0")->str:
        """Clears all days in the future if the var:code is correct."""
        if code==project.settings["code"]:
            project.save(path=project.path+"_backup") 
            keys=[]
            for key in project.days.keys():
                if project.days[key].date > date.today():
                    keys.append(key)
            for key in keys:
                project.days.pop(key)
        else:
            logging.warning(f"wrong code: {code}")
        return reference

    @staticmethod
    def c_get_current(project:ChronoProject, reference:str)->str:
        """Gets the current event."""
        if date.today().isoformat() in project.days.keys():
            for event in project.days[date.today().isoformat()].events:
                if event.start <= datetime.now().time()<=event.end:
                    print(event)
                    return reference
        print("no current event")
        return reference

    @staticmethod
    def c_get_next(project:ChronoProject, reference:str)->str:
        """Get next ChronoEvent"""
        if date.today().isoformat() in project.days.keys():
           for slot in project.days[date.today().isoformat()].get_slots():
               print(slot)
        print("no current event")
        return reference

    @staticmethod
    def c_today(project:ChronoProject, reference:str)->str:
        """Prints the plan for today."""
        if reference in project.days.keys():
            project.days[reference].merge()
            print(project.days[reference])
            cse=[sevent for sevent in project.sevents if sevent.tdate.isoformat()==reference]
            if not cse == []:
                print("Today's ChronoTimes: ")
                for sevent in cse:
                    print(sevent)
        else:
            print("no plan for today")
        return reference

    @staticmethod
    def c_delete_day(project:ChronoProject, reference:str)->str:
        """Deletes the reference day and sets reference to base"""
        if reference in project.days.keys():
            project.days.pop(reference)
            print("Deleted "+ reference)
            logging.info("Deleted "+ reference)
        return "base"
    
    @staticmethod
    def c_delete_event(project:ChronoProject, reference:str, start:str, stop:str)->str:
        """Deletes the event."""
        if reference in project.days.keys():
            for event in project.days[reference].events:
                if event.start.isoformat()[:5]==start and event.end.isoformat()[:5]==stop:
                    print("removed")
                    project.days[reference].events.remove(event)
                    return reference
        return reference

    @staticmethod
    def c_end(project:ChronoProject, reference:str)->str:
        """Ends the current event."""
        for event in project.days[date.today().isoformat()].events:
            if event.start <= datetime.now().time()<=event.end:
                event.end=datetime.now().time()
                return reference
        logging.warning("couldn`t end event: no current event")
        return reference

    @staticmethod
    def c_times(project:ChronoProject, reference:str, days:str="1")->str:
        """Prints the ChronoTimes of the next var:days days (relative to reference)."""
        d=project.date_from_str(reference)
        allowed_delta=timedelta(days=int(days))
        for sevent in project.sevents:
            if d-sevent.tdate <= allowed_delta:
                print(sevent)
        return reference

    @staticmethod
    def c_change_event_time(project:ChronoProject, reference:str, start:str, stop:str, nstart:str="08:00", nend:str="10:00")->str:
        """Changes the timeframe of a ChronoEvent."""
        if reference in project.days.keys():
            if not reduce(lambda a,b: a or b, [(not ( e.start.isoformat()[:-3]==start and e.end.isoformat()[:-3]==stop)) and check_in_timeframe((time_from_str(nstart),time_from_str(nend)),e) for e in project.days[reference].events], False):
                for e in project.days[reference].events:
                    if e.start.isoformat()[:-3]==start and e.end.isoformat()[:-3]==stop:
                        e.start=time_from_str(nstart)
                        e.end=time_from_str(nend)
                        return reference
        return reference

    @staticmethod        
    def c_change_event_what(project:ChronoProject, reference:str, start:str, stop:str, what:str)->str:
        """Changes the what of a ChronoEvent."""
        if reference in project.days.keys():
            for e in project.days[reference].events:
                if e.start.isoformat()[:-3]==start and e.end.isoformat()[:-3]==stop:
                    e.what=what
        return reference

    @staticmethod        
    def c_change_event_tags(project:ChronoProject, reference:str, start:str, stop:str, tags:str)->str:
        """Changes the tags of a ChronoEvent."""
        if reference in project.days.keys():
            for e in project.days[reference].events:
                if e.start.isoformat()[:-3]==start and e.end.isoformat()[:-3]==stop:
                    e.tags=tags.split(",")
        return reference

    @staticmethod
    def c_change_event(project:ChronoProject, reference:str, start:str, stop:str, mode:str, *args)->str:
        """Changes the something of a ChronoEvent."""
        if mode=="time":
            return MSSH.c_change_event_time(project, reference, start, stop, *args)
        elif mode=="what":
            return MSSH.c_change_event_what(project, reference, start, stop, *args)
        elif mode=="tags":
            return MSSH.c_change_event_tags(project, reference, start, stop, *args)
        else:
            raise Exception("unknown mode")
    
    @staticmethod
    def c_plot_stats(project:ChronoProject, reference:str, tags:str="mathe", r_str:str="7",interpolate:str="0", start_date:str="start", end_date:str="stop", )->str:
        """Plots the hours of var:tags and their sum. Calls fillemptydays. Both var:start_date and var:end_date support IntelliRef."""
        assert not "sum" in tags
        plt.clf()
        #preperation
        MSSH.c_fill_empty_days(project,reference,start_date,end_date)
        tags=tags.split(",")
        ticksi=5
        r=int(r_str)
        days = project.analysis_get_between(start_date, end_date, reference)
        n=len(days)
        xs=[i for i in range(n)]
        ys={tag:[] for tag in tags}
        fs=project.get_functions(days)
        #populate ys
        for day in days:
            for tag in tags:
                if tag in fs:
                    ys[tag].append(project.get_function(day.date,tag,interpolate=int(interpolate)))
                else:
                    ys[tag].append(get_time(day, tag))

        for tag in tags:
            N=len(ys[tag])
            for i in range(len(ys[tag])):
                if ys[tag][i]=="i": 
                    ys[tag][i]=sum([ys[tag][i+j] for j in range(int(interpolate)) if ys[tag][i+j] != "i" and i+j<N])+sum([ys[tag][i-j] for j in range(int(interpolate)) if ys[tag][i-j] != "i"])
                    normalizier=max(1,len([j for j in range(int(interpolate))  if ys[tag][i+j] != "i"and i+j<N])+len([j for j in range(int(interpolate))  if ys[tag][i-j] != "i"]))
                    ys[tag][i]=ys[tag][i]/normalizier

        #Calculate overhead (sum)
        corr=[0.0 for _ in days]
        for i in range(n):
            for event in days[i].events:
                if not (I:=get_intersect(tags, event.tags))==[]:
                    corr[i] += ((datetime.combine(date.today(), event.end)\
                     - datetime.combine(date.today(), event.start))\
                .seconds/3600)*(len(I)-1) 

        if len(tags)>1: 
            ys["sum"]=[sum([ys[tag][i] for tag in tags])-corr[i] for i in range(n)]


        #plot tags+sum
        ax=plt.subplot(111)
        box = ax.get_position()
        ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        for tag in ys.keys():
             plt.plot([x for x in xs[r-1:]], [sum(ys[tag][i-j] for j in range(r))/r for i in range(r-1,len(ys[tag]))], label=tag)

        #Calculate and plot weekday average
        if not days == []: 
            zeroday=days[0].date.weekday()
            if len(tags)>1: WDA=[sum(wds:=[ys["sum"][i] for i in range(n) if (i+zeroday)%7==wd])/max(len(wds),1) for wd in range(7)] 
            else: WDA=[sum(wds:=[ys[tags[0]][i] for i in range(n) if (i+zeroday)%7==wd])/max(len(wds),1) for wd in range(7)] 
            plt.plot(xs,[WDA[day.date.weekday()] for day in days],"--",label="wda")
        
        #Mark "reference" with a *

        try:
            tmp=project.date_from_str(reference)
        except:
            tmp=date.fromisocalendar(1900,1,1)
        if tmp in [day.date for day in days]:
            d=-1
            for i in range(len(days)):
                if days[i].date==tmp:
                    d=i
            try: 
                if len(tags)>1:
                    plt.scatter([d], ys["sum"][d], label="Reference", marker="*", color="red", s=[70])
                else:
                    plt.scatter([d], sum(ys[tags[0]][d-j] for j in range(r))/r, label="Reference", marker="*", color="red", s=[70])
            except:
                logging.warn("Some days are missing.")
                print("Some days are missing.")
        
        #visuals
        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        if n<ticksi:
            plt.xticks([i for i in range(n)], [days[i].date.isoformat() for i in range(n)])
        else:
            plt.xticks([round((n-1)*i/(ticksi-1)) for i in range(ticksi)], [days[round((n-1)*i/(ticksi-1))].date.isoformat() for i in range(ticksi)])
        plt.xlabel("Days")
        plt.ylabel("Quantity")
        logging.info("Displaying plot ...")
        plt.show()
        logging.info("Plot closed")
        return reference

    @staticmethod
    def c_plot_week(project:ChronoProject, reference:str, tags:str="mathe,programming,korean", k:str="7",end_date:str="stop")->str:
        """Plots the hours of var:tags and their sum. over the last var:k days"""
        plt.clf()
        ds=[day.date for day in project.days.values()]
        if end_date=="stop": 
            end=max(ds)
            end_date=end.isoformat()
        elif end_date=="today":
            end=date.today()
            end_date=end.isoformat()
        elif end_date=="ref":
            end=date(int(reference[:4]), int(reference[5:7]), int(reference[8:]))
            end_date=reference
        else:
            end=date(int(end_date[:4]), int(end_date[5:7]), int(end_date[8:]))
        start_date=(end-timedelta(days=int(k))).isoformat()
        MSSH.c_plot_stats(project,reference,tags,start_date,end_date)
        return reference

    @staticmethod
    def c_note(project:ChronoProject, reference:str, text:str, *texts:Tuple[str])->str:
        """Adds a note to the todo list."""
        project.add_note(ChronoNote(reduce(lambda a,b:a+" "+b, [text]+list(texts))))
        return reference

    @staticmethod
    def c_notes(project:ChronoProject, reference:str)->str:
        """Prints all saved notes."""
        print("Notes:")
        for i, note in enumerate(project.todo):
            print(str(i+1)+".: "+str(note))
        return reference

    @staticmethod
    def c_del_note(project:ChronoProject, reference:str, text:str,*texts:Tuple[str])->str:
        """Deletes all ChronoNotes with the text var:text."""
        text=reduce(lambda a,b:a+" "+b, [text]+list(texts))
        project.todo=list(filter(lambda x: not x.text==text , project.todo))
        return reference

    @staticmethod
    def c_del_note_id(project:ChronoProject, reference:str, i:str)->str:
        """Deletes the var:i-th ChronoNote ."""
        project.todo=project.todo[:int(i)-1]+project.todo[int(i):]
        return reference

    @staticmethod
    def c_del_notes(project:ChronoProject, reference:str)->str:
        """Deletes all ChronoNotes."""
        project.todo=[]
        return reference

    @staticmethod
    def c_stats(project:ChronoProject, reference:str, tags:str, start_date:str="start", end_date:str="stop")->str:
        """Displays stats for given tags."""
        tags=tags.split(",")
        hours=[]
        days=project.analysis_get_between(start_date, end_date, reference)
        for tag in tags:
            hours=[]
            for day in days:
                hours.append(get_time(day, tag))
            rest=restrict(days,hours, 7)
            print(f"{tag}: Daily Avg (hours): {sum(hours)/len(hours)}\n"+f"this week: {sum(rest)/len(rest)} hours")
        return reference

    @staticmethod
    def c_add_run(project:ChronoProject, reference:str, start_time:str, run_time:str, distance:str)->str:
        """Adds a ChronoRunEvent based on:"""
        runtimei=str_to_seconds(run_time)
        project.days[reference].add_run(ChronoRunningEvent(runtimei,float(distance),time_from_str(start_time)))
        return reference

    @staticmethod
    def c_add_situp(project:ChronoProject, reference:str, start_time:str, situp_time:str, mult:str)->str:
        """Adds a ChronoSitUpsEvent based on:"""
        if len((tmp:=situp_time.split(":")))==2:
            situp_timef=int(tmp[0])+int(tmp[1])/100
        else: situp_timef=int(tmp[0])*60+int(tmp[1])+int(tmp[2])/100
        project.days[reference].add_situp(ChronoSitUpsEvent(situp_timef,int(mult),time(int(start_time[0:2]), int(start_time[3:]))))
        return reference

    @staticmethod
    def c_add_plank(project:ChronoProject, reference:str, start_time:str, p_time:str)->str:
        """Adds a ChronoPlankEvent based on:"""
        if len((tmp:=p_time.split(":")))==2:
            p_timef=int(tmp[0])+int(tmp[1])/100
        else: p_timef=int(tmp[0])*60+int(tmp[1])+int(tmp[2])/100
        project.days[reference].add_plank(ChronoPlankEvent(p_timef,time(int(start_time[0:2]), int(start_time[3:]))))
        return reference

    @staticmethod
    def c_add_pushup(project:ChronoProject, reference:str, start_time:str, times:str, mults:str)->str:
        """Adds a ChronoPushUpEvent based on:"""
        timesfl=[int(tmp[0])+int(tmp[1])/100 if len((tmp:=ct.split(":")))==2 else int(tmp[0])*60+int(tmp[1])+int(tmp[2])/100  for ct in times.split(",")]
        multsil=[int(mult) for mult in mults.split(",")]
        project.days[reference].add_pushup(ChronoPushUpEvent(timesfl,multsil,time(int(start_time[0:2]), int(start_time[3:]))))
        return reference

    @staticmethod
    def c_merge(project:ChronoProject, reference:str)->str:
        """Merges all adjacent Events with the same var:what iff event1.end==event.start."""
        for day in project.days.values():
            day.merge()
        return reference

    @staticmethod
    def c_heatmap(project:ChronoProject, reference:str, tag:str, start_date:str="start", end_date:str="stop")->str:
        """Draws a heat map for a specific var:tag with at most 15 vertical labels with data from 
        [var:start_date,var:end_date]."""
        heatmap(project,tag,reference,start_date,end_date)
        logging.info("Displaying heatmap ...")
        plt.show()
        logging.info("Heatmap closed")
        return reference

    @staticmethod
    def c_split_project(project:ChronoProject, reference:str, split:str, old_name:str)->str:
        """Splits the project into two. Saves [start_date,split] to var:oldname.json and (split, end_date]
         to project.json."""
        tmp=project.days.copy()
        splitdate=project.date_from_str(split,reference)
        project.days = {key:tmp[key] for key in tmp.keys() if tmp[key].date <=splitdate}
        project.save(path=old_name)
        project.days = {key:tmp[key] for key in tmp.keys() if tmp[key].date >splitdate}
        project.save()
        return reference

    @staticmethod
    def c_oura_sleep(project:ChronoProject, reference:str, start:str, stop:str)->str:
        """Gets your sleep data $\n$ [start-1,stop] from oura is such a connection exists."""
        start=project.date_from_str(start, reference).isoformat()
        stop=project.date_from_str(stop, reference).isoformat()
        delete_by_tag(project,reference,"ouras",project.analysis_get_between(start, stop, reference))
        if project.settings["oura"]:
            sleepdata=get_sleep(start_date=start,stop_date=stop,code=project.settings["oura_key"])
            if sleepdata[0]:
                keys=project.days.keys()
                for key in sleepdata[1].keys():
                    css=datetime.fromisoformat(sleepdata[1][key][0]) # current sleep start
                    cse=css+timedelta(minutes=5) # cse
                    pattern_5_min=sleepdata[1][key][2]
                    for i in range(len(pattern_5_min)):
                        try: 
                            if css.date()==cse.date():
                                project.days[css.date().isoformat()].add_event(ChronoEvent(css.time().isoformat(),cse.time().isoformat(),"sleep", ["all_sleep",get_sleep_phase(pattern_5_min[i]),"ouras", "generated"]))
                            elif cse.time().isoformat()!="00:00":
                                print(css,cse)
                                project.days[css.date().isoformat()].add_event(ChronoEvent(css.time().isoformat(),"23:59","sleep", ["all_sleep",get_sleep_phase(pattern_5_min[i]),"ouras", "generated"]))
                                project.days[cse.date().isoformat()].add_event(ChronoEvent("00:00",cse.time().isoformat(),"sleep", ["all_sleep",get_sleep_phase(pattern_5_min[i]),"ouras", "generated"]))
                            else:
                                project.days[css.date().isoformat()].add_event(ChronoEvent(css.time().isoformat(),"23:59","sleep", ["all_sleep",get_sleep_phase(pattern_5_min[i]),"ouras", "generated"]))
                        except:
                            if not css.date().isoformat() in keys: project.add_day(ChronoDay([],css.date().isoformat()))
                            if not cse.date().isoformat() in keys: project.add_day(ChronoDay([],cse.date().isoformat()))
                        project
                        css=cse
                        cse=css+timedelta(minutes=5)
                    project.days[key].sleep=pattern_5_min
                    project.days[key].merge()
        else:           
            print("No oura is linked: Check your settings")
            logging.warning("No oura is linked: Check your settings")   
        return reference 

    @staticmethod
    def c_get_sleep(project:ChronoProject, reference:str, sdate:str)->str:
        """Prints the sleep data from a specific var:sdate (and the day before if the sleep event has the split_sleep)."""
        sdate=project.date_from_str(sdate, reference).isoformat()
        if sdate in project.days.keys():
            sleep_es:List[ChronoEvent]=[]
            for event in project.days[sdate].events:
                if "sleep" in event.tags:
                    sleep_es.append(event)
            if sleep_es!=[] and "split_sleep" in sorted(sleep_es,key=lambda x:x.start)[0].tags:
                yesterday:date=project.days[sdate].date-timedelta(days=1)
                if yesterday.isoformat() in project.days.keys():
                    print(yesterday.isoformat()+":"+str(max([event for event in project.days[yesterday.isoformat()].events if "split_sleep" in event.tags],key=lambda x:x.start)))
            elif sleep_es==[]:
                logging.info("No sleep data")
                print("No sleep data :(")
            for sleep_e in sleep_es:
                print(sdate+":"+str(sleep_e))
        else:
            print(sdate+" is not a valid key")
            logging.warning(sdate+" is not a valid key")
        return reference
    
    @staticmethod
    def c_last_sleep(project:ChronoProject, reference:str)->str:
        """Gets all sleep events of the current day (and the day before if the sleep event has the split_sleep)"""
        MSSH.c_get_sleep(project, reference, reference)
        return reference

    @staticmethod
    def c_show_run(project:ChronoProject, reference:str)->str:
        """Displays all runs which happend on the referenced day."""
        if reference in project.days.keys():
            print(project.days[reference].sport["runs"])
        return reference
    
    @staticmethod
    def c_run_today(project:ChronoProject, reference:str)->str:
        """Displays a short analysis of all runs which happend on the referenced day."""
        if reference in project.days.keys():
            if project.days[reference].sport["runs"] == []:
                print("no runs today :(")
            else:
                lengths=sum([run.time for run in project.days[reference].sport["runs"]])
                length=seconds_to_time(int(lengths))
                distance=sum([run.distance for run in project.days[reference].sport["runs"]])
                pace=seconds_to_time(int(lengths/distance))
                print(f"{reference}: You ran {distance} in {length}. That makes a pace of {pace.isoformat()[3:]} per kilometer.")
        return reference

    @staticmethod
    def c_runplot(project:ChronoProject, reference:str,start_date:str="start",end_date:str="stop")->str:
        """Plots the distance run each day in [start_date, end_date]. Both var:start_date and var:end_date support IntelliRef."""
        plt.clf()
        days = project.analysis_get_between(start_date, end_date, reference)
        xs=[]
        ys=[]#distance  
        ysp=[]#pace
        plt.close() # "Fix": 2 plots open, but one is empty
        fig, ax1 = plt.subplots()

        ax2 = ax1.twinx()

        ax1.set_xlabel("Days")
        ax1.set_ylabel("Distance")
        ax2.set_ylabel("Pace")

        for i in range(len(days)):
            lengths=sum([run.time for run in days[i].sport["runs"]])
            distance=sum([run.distance for run in days[i].sport["runs"]])
            pace=lengths/max(distance,1)
            if distance > 0:
                xs.append(i)
                ys.append(distance)
                ysp.append(pace)
        ax1.scatter(xs,ys,label="Distance",color="b")
        ax2.plot(xs,ysp,label="Pace",color="r")
        ticks=get_pace_ticks(ysp)
        ax2.set_yticks(ticks[0])
        ax2.set_yticklabels(ticks[1])
        fig.legend()
        logging.info("Displaying plot ...")
        plt.show() 
        logging.info("Plot closed") 
        return reference

    @staticmethod
    def c_del_run(project:ChronoProject, reference:str, start_time:str)->str:
        """Deletes a given run on the referenced day."""
        if reference in project.days.keys():
            project.days[reference].sport["runs"]=list(filter(lambda run: run.start_time.isoformat()[:5]!=start_time, project.days[reference].sport["runs"]))
        return reference

    @staticmethod
    def c_del_situp(project:ChronoProject, reference:str, start_time:str)->str:
        """Deletes a given situp on the referenced day."""
        if reference in project.days.keys():
            project.days[reference].sport["situps"]=list(filter(lambda situp: situp.start_time.isoformat()[:5]!=start_time, project.days[reference].sport["situps"]))
        return reference
    
    @staticmethod
    def c_del_plank(project:ChronoProject, reference:str, start_time:str)->str:
        """Deletes a given plank on the referenced day."""
        if reference in project.days.keys():
            project.days[reference].sport["planks"]=list(filter(lambda plank: plank.start_time.isoformat()[:5]!=start_time, project.days[reference].sport["planks"]))
        return reference

    @staticmethod
    def c_del_pushup(project:ChronoProject, reference:str, start_time:str)->str:
        """Deletes a given pushup on the referenced day."""
        if reference in project.days.keys():
            project.days[reference].sport["pushups"]=list(filter(lambda pushup: pushup.start_time.isoformat()[:5]!=start_time, project.days[reference].sport["pushups"]))
        return reference

    @staticmethod
    def c_fill_empty_days(project:ChronoProject, reference:str,start_date:str="start",end_date:str="stop")->str:
        """Fills up any missing days between var:start_date and var:end_date,  
        but does not populate them based on the schedule! Both var:start_date and var:end_date support IntelliRef."""
        days = project.analysis_get_between(start_date, end_date, reference)
        current_day=days[0].date
        last_day=days[-1]
        td=timedelta(days=1)
        while current_day < last_day.date:
            if not (c_date:=current_day.isoformat()) in project.days.keys():
                project.days[c_date]=ChronoDay(events=[], input_date=c_date)
            current_day += td
        return reference

    @staticmethod
    def c_export_sport(project:ChronoProject, reference:str,start_date:str="start",end_date:str="stop")->str:
        """Exports your sports data  in between [start_date, end_date] to data/sport.json. Both var:start_date and var:end_date support IntelliRef."""
        sport=dict()
        days = project.analysis_get_between(start_date, end_date, reference)
        if not path.exists("./jsons/"):
            mkdir("./jsons/")
        for day in days:
            if not list(day.sport.values()) == [[],[],[],[]]:
                sport[day.date.isoformat()] = {key:[entry.to_dict() for entry in day.sport[key]] for key in day.sport.keys()}
        with open("./jsons/sport.json","w+") as f:
            json.dump(sport,f)
        return reference

    @staticmethod
    def c_exportweek(project:ChronoProject, reference:str,end_date:str="stop")->str:
        """ Exports 7 days ending on var:end_date to a LaTeX -> PDF file and opens the file. var:end_date support IntelliRef."""
        days=project.analysis_get_between("start", end_date, reference)[-7:]
        header=["\\documentclass{article}", "\\usepackage{xcolor}","\\usepackage{hyperref}","\\usepackage{pdflscape}"]
        poi=set()
        for day in days:
            for event in day.events:
                poi.add(event.start)
                poi.add(event.end)
        pois=sorted(poi)
        slots=[(pois[i],pois[i+1]) for i in range(len(pois)-1)]
        with open("weekexport.tex", "w+", encoding="utf-8") as f:
            f.write(list_to_string(header)+"\n"+list_to_string(project.get_meta())+"\n")
            f.write("\\begin{document}\n")
            f.write("\\begin{landscape}\n")
            f.write("\\maketitle\n")
            data=[["Timeslots"]+[WEEKDAYS[day.date.weekday()] for day in days]]+[[f"{slot[0].isoformat()[:-3]}-{slot[1].isoformat()[:-3]}"]+[what_or_none(list(filter(lambda x: check_in_timeframe(slot,x),days[i].events)), project.scheme) for i in range(7)] for slot in slots]
            write_table(f, [8, len(slots)+1], data=data)
            f.write("\\end{landscape}\n")
            f.write("\\end{document}\n")
        subprocess.run(["pdflatex", "weekexport.tex"], stdout=subprocess.DEVNULL)
        subprocess.run(["pdflatex", "weekexport.tex"], stdout=subprocess.DEVNULL)
        if os.path.isfile("weekexport.log"):os.remove("weekexport.log")
        if os.path.isfile("weekexport.aux"):os.remove("weekexport.aux")
        if os.path.isfile("weekexport.nav"):os.remove("weekexport.nav")
        if os.path.isfile("weekexport.out"):os.remove("weekexport.out")
        if os.path.isfile("weekexport.toc"):os.remove("weekexport.toc")
        if os.path.isfile("weekexport.tex"):os.remove("weekexport.tex")
        os.replace("weekexport.pdf","./pdfs/weekexport.pdf")
        subprocess.Popen([project.settings["pdfpath"],"./pdfs/weekexport.pdf"], shell=True)
        return reference

    @staticmethod
    def c_to_csv(project:ChronoProject, reference:str,name:str,start_date:str="start",end_date:str="stop")->str:
        """Exports the events of this project to a csv file. Both var:start_date and var:end_date support IntelliRef."""
        days=project.analysis_get_between(start_date, end_date, reference)
        with open(f"{name}.csv","w+") as f:
            for day in days:
                for event in day.events:
                    f.write(f"{day.date.isoformat()},{event.what},{str(reduce(concatsem, event.tags))},{event.start.isoformat()},{event.end.isoformat()}\n")
        return reference

    @staticmethod
    def c_aliases(project:ChronoProject, reference:str)->str:
        """Prints all aliases."""
        print(list(project.alias.keys()))
        return reference

    @staticmethod
    def c_runsum(project:ChronoProject, reference:str, k:str="6")->str:
        """Displays a short analysis of all runs which happend up to var:k days before var:reference."""
        if reference in project.days.keys():
            start=project.date_from_str(reference)
            end=start-timedelta(days=int(k))
            runs=sum([day.sport["runs"] for day in project.analysis_get_between(end.isoformat(),reference, reference)], [])
            if runs==[]:
                print("Runs=[]")
            else:
                lengths=sum([run.time for run in runs])
                lengtht=seconds_to_time(int(lengths))
                distance=sum([run.distance for run in runs])
                pace=seconds_to_time(int(lengths/distance))
                print(f"{reference}: You ran {distance} in {lengtht}. That makes a pace of {pace.isoformat()[3:]} per kilometer.")
        else:
            logging.warn(f"Can't find reference: {reference}")
            print("Reference not found")
        return reference

    @staticmethod
    def c_heatmap_summary(project:ChronoProject, reference:str)->str:
        """ Creates a pdf file containing a heatmap for each tag. The heatmap includes all days."""
        tbr=[["_","\\_"],["ä","\\\"a"],["ü","\\\"u"],["ö","\\\"o"]]
        cdays=project.analysis_get_between("start", "stop", reference)
        days:List[date]=[day.date for day in cdays]
        tags=set(reduce(lambda a,b:a+b,[event.tags for day in cdays  for event in day.events]))
        for tag in tags:
            heatmap(project,tag,reference)
            if not path.exists("./imgs/"):
                mkdir("./imgs/")
            if not path.exists("./pdfs/"):
                mkdir("./pdfs/")
            plt.savefig("./imgs/"+tag+".png")
            plt.clf()
        logging.info("Wrote images")
        header=["\\documentclass{article}", "\\usepackage{xcolor}", "\\usepackage{hyperref}", "\\usepackage{float}",
                "\\usepackage{graphicx}", "\\usepackage[encoding,filenameencoding=utf8]{grffile}"]
        with open("Summary.tex", "w+", encoding="utf-8") as f:
            f.write(list_to_string(header)+"\n"+"\\title{Summary: "+min(days).isoformat()+" - "+max(days).isoformat()+"}\n")
            f.write("\\begin{document}\n")
            f.write("\\maketitle\n")
            for tag in tags:
                rep_tag=tag
                for rep in tbr:
                    rep_tag=rep_tag.replace(rep[0], rep[1])
                f.write("\\section*{"+f"{rep_tag}"+ "}\n")
                f.write("\\hypertarget{"+f"{rep_tag}"+"}{}\n")
                f.write("\\begin{figure}[H]\n")
                f.write("\\centering\n")
                f.write("\\includegraphics{"+"./imgs/"+tag+".png"+"}\n")
                f.write("\\caption{"+rep_tag+"}\n")
                f.write("\\end{figure}\n")
                f.write("\\clearpage\n")
            f.write("\\end{document}\n")
        logging.info("generated .tex file")
        subprocess.run(["pdflatex", "Summary.tex"], stdout=subprocess.DEVNULL)
        subprocess.run(["pdflatex", "Summary.tex"], stdout=subprocess.DEVNULL)
        if os.path.isfile("Summary.log"):os.remove("Summary.log")
        if os.path.isfile("Summary.aux"):os.remove("Summary.aux")
        if os.path.isfile("Summary.nav"):os.remove("Summary.nav")
        if os.path.isfile("Summary.out"):os.remove("Summary.out")
        if os.path.isfile("Summary.toc"):os.remove("Summary.toc")
        if os.path.isfile("Summary.tex"):os.remove("Summary.tex")
        if os.path.isfile("Summary.tex.bak"):os.remove("Summary.tex.bak")
        shutil.rmtree("./imgs/")
        os.replace("Summary.pdf","./pdfs/Summary.pdf")
        logging.info("Removed useless files and generated pdf")
        subprocess.Popen([project.settings["pdfpath"],"./pdfs/Summary.pdf"], shell=True)
        logging.info("Pdf closed")
        return reference

    @staticmethod
    def c_heatmap_animation(project:ChronoProject, reference:str, tag:str)->str:
        "Creates a gif file displaying the evolution of the heatmap of var:tag. Each day is a frame."
        days:List[ChronoDay]=[]
        filenames=[]
        for day in project.days.values():
            if tag in set(reduce(lambda a,b:a+b,[event.tags for event in day.events])):
                days.append(day)
        for i, day in enumerate(days):
            heatmap(project,tag,reference,"start",day.date.isoformat(),tag+": "+day.date.isoformat())
            if not path.exists("./imgs/"):
                mkdir("./imgs/")
            fn="./imgs/"+tag+str(i)+".png"
            plt.savefig(fn)
            filenames.append(fn)
            plt.clf()
        logging.info("Generated images")
        images=[]
        for filename in filenames:
            images.append(imageio.imread(filename))
        if not path.exists("./gifs/"):
                mkdir("./gifs/")
        imageio.mimsave("./gifs/"+tag+".gif", images)
        shutil.rmtree("./imgs/")
        logging.info("Generated gif")
        if project.settings["gif"] != "":
             os.system(project.settings["gif"]+" ./gifs/"+tag+".gif")
        return reference

    @staticmethod
    def c_tag_summary(project:ChronoProject, reference:str, tag:str, start:str="start",end:str="stop")->str:
        """Creates a csv file of var:tag. Each day (with at least 1 event with tag var:tag) $\n$ [var:start, var:end] is represented by a row containing both the date and
           the iso-formatted length of time var:tag was done at this day. Both var:start and var:end support IntelliRef."""
        days=project.analysis_get_between(start, end, reference)
        data=[]
        for day in days:
            if (duration:=get_time(day, tag))>0:
                data.append((day.date, seconds_to_time(int(3600*duration)).isoformat()))
        if not path.exists("./sums/"):
                mkdir("./sums/")
        with open(f"sums/{tag}_{start}_{end}"+".csv","w+") as f:
            for dp in data:
                f.write(dp[0].isoformat()+","+dp[1]+"\n")
        if project.settings["csv"] != "":
             os.system(project.settings["csv"]+f" sums/{tag}_{start}_{end}"+".csv")
        return reference

    @staticmethod
    def c_summary_m(project:ChronoProject, reference:str, tag:str, month:str="", year:str="")->str:
        """Tag summary for a specified month. If either var:year or var:month and var:year are omitted
        those are inferred from  var:reference"""
        if month==""or year=="": ref_date=datetime.fromisoformat(reference).date()
        if month=="": month_ld=ref_date.month
        else: month_ld=int(month)
        if year=="": year_ld=ref_date.year
        else: year_ld=int(year)
        _, ld=calendar.monthrange(year_ld, month_ld)
        MSSH.c_tag_summary(project,reference,tag,date(year=year_ld,month=month_ld, day=1).isoformat(),date(year=year_ld,month=month_ld, day=ld).isoformat())
        return reference

    @staticmethod
    def c_export_schedule(project:ChronoProject, reference:str)->str:
        """Exports the schedule to pdf."""
        header=["\\documentclass{article}", "\\usepackage{xcolor}","\\usepackage{hyperref}","\\usepackage{pdflscape}"]
        poi=set()
        for week in project.schedule.days:
            for day in week:
                for event in day:
                    poi.add(event.start)
                    poi.add(event.end)
        pois=sorted(poi)
        slots=[(pois[i],pois[i+1]) for i in range(len(pois)-1)]
        with open("weekexport.tex", "w+", encoding="utf-8") as f:
            f.write(list_to_string(header)+"\n")
            f.write("\\begin{document}\n")
            f.write("\\begin{landscape}\n")
            for week in project.schedule.days:
                data=[["Timeslots"]+[WEEKDAYS[day] for day in range(7)]]+[[f"{slot[0].isoformat()[:-3]}-{slot[1].isoformat()[:-3]}"]+[what_or_none(list(filter(lambda x: check_in_timeframe(slot,x),week[i])), project.scheme) for i in range(7)] for slot in slots]
                write_table(f, [8, len(slots)+1], data=data)
                f.write("\\clearpage")
            f.write("\\end{landscape}\n")
            f.write("\\end{document}\n")
        subprocess.run(["pdflatex", "weekexport.tex"], stdout=subprocess.DEVNULL)
        subprocess.run(["pdflatex", "weekexport.tex"], stdout=subprocess.DEVNULL)
        if os.path.isfile(f"weekexport.log"):os.remove(f"weekexport.log")
        if os.path.isfile(f"weekexport.aux"):os.remove(f"weekexport.aux")
        if os.path.isfile(f"weekexport.nav"):os.remove(f"weekexport.nav")
        if os.path.isfile(f"weekexport.out"):os.remove(f"weekexport.out")
        if os.path.isfile(f"weekexport.toc"):os.remove(f"weekexport.toc")
        if os.path.isfile(f"weekexport.tex"):os.remove(f"weekexport.tex")
        os.replace("weekexport.pdf","./pdfs/weekexport.pdf")
        subprocess.Popen([project.settings["pdfpath"], "./pdfs/weekexport.pdf"], shell=True)
        return reference

    @staticmethod
    def c_barplot_tags_t(project:ChronoProject, reference:str, tagss:str, start:str="start", end:str="stop")->str:
        """Barplot animation of the distribution of tags over time [var:start, var:end]. Both var:start and var:end support IntelliRef."""
        plt.clf()
        ddays=sorted(project.analysis_get_between(start,end,reference), key=lambda x: x.date)
        tags=tagss.split(",")
        days=[]
        for day in ddays:
            if reduce(lambda a,b: a or b, [tag in set(reduce(lambda a,b:a+b,[event.tags for event in day.events])) for tag in tags]):
                    days.append(day)
        filenames:List[str]=[]
        images=[]
        data:Dict[str, float]={}
        if not path.exists("./imgs/"):
                mkdir("./imgs/")
        for tag in tags:
            data[tag]=0.0
        for day in days:
            for tag in tags:
                    data[tag]+=get_time(day, tag)
            plt.bar(tags, [data[tag] for tag in tags])
            fn="./imgs/"+day.date.isoformat()+".png"
            plt.title(day.date.isoformat())
            plt.savefig(fn)
            filenames.append(fn)
            plt.clf()
        logging.info("Generated images")
        for filename in filenames:
            images.append(imageio.imread(filename))
        if not path.exists("./gifs/"):
                mkdir("./gifs/")
        imageio.mimsave("./gifs/barplot_"+tagss+".gif", images)
        shutil.rmtree("./imgs/")
        if project.settings["gif"] != "":
             os.system(project.settings["gif"] + " ./gifs/barplot_"+tagss+".gif")
        return reference

    @staticmethod
    def c_barplot_tags(project:ChronoProject, reference:str, tagss:str, start:str="start", end:str="stop")->str:
        """Barplot of the distribution of the var:tagss in [var:start, var:stop]. Both var:start and var:end support IntelliRef."""
        plt.clf()
        ddays=sorted(project.analysis_get_between(start,end,reference), key=lambda x: x.date)
        tags=tagss.split(",")
        days=[]
        for day in ddays:
            if reduce(lambda a,b: a or b, [tag in set(reduce(lambda a,b:a+b,[event.tags for event in day.events])) for tag in tags]):
                    days.append(day)
        data:Dict[str, float]={}
        for tag in tags:
            data[tag]=0.0
        for day in days:
            for tag in tags:
                    data[tag]+=get_time(day, tag)
        plt.bar(tags, [data[tag] for tag in tags])
        plt.title(tagss)
        logging.info("Genearted barplot")
        plt.show()
        logging.info("Plot closed")
        return reference

    @staticmethod
    def c_rel_cc(project:ChronoProject, reference:str, tags:str, start:str="start", end:str="stop")->str:
        """Get relevant connected components (excluding connections of var:tags). 
        Does not include tags only connected to tags in var:tags. Both var:start and var:end support IntelliRef."""
        g=project.get_tag_graph(start,end,reference, tags.split(","))
        ccs=project.get_ccs(g)
        for cc in ccs:
            print(cc)
        return reference

    @staticmethod
    def c_top_degrees(project:ChronoProject, reference:str, k:str, start:str="start", end:str="stop")->str:
        """Prints the top var:k degrees of the tag graph. Both var:start and var:end support IntelliRef."""
        g=project.get_tag_graph(start, end, reference)
        top_k=sorted(list(nx.degree(g)), key=lambda x:x[1], reverse=True)[:int(k)]
        print("Graph consists of " + str(len(g.nodes)) + " tags:")
        for tag in top_k:
            print(f"{tag[0]} has degree {tag[1]}")
        return reference

    @staticmethod
    def c_export_graph_data(project:ChronoProject, reference:str, start:str="start", end:str="stop")->str:
        """Exports graph data to graph.json. Both var:start and var:end support IntelliRef."""
        if not path.exists("./jsons/"):
            mkdir("./jsons/")
        g=project.get_tag_graph(start, end, reference)
        ccs=project.get_ccs(g)
        data:Dict[str,Any]={"ccs":ccs}
        data["degrees"]={node[0]:node[1] for node in nx.degree(g)}
        f, g=project.get_f_ug(g,start,end,reference)
        data["f"]=f
        data["weights"]={f"({u},{v})":w for u,v,w in g.edges(data=True)} 
        with open(f"./jsons/graph.json", "w+") as f:
            json.dump(data,f,indent=4)
        
        return reference

    @staticmethod
    def c_export_db(project:ChronoProject, reference:str)->str:
        """Save the project and export the data to a sqlite database."""
        project.save()
        if os.path.isfile("data/"+project.path+".db"):
            os.remove("data/"+project.path+".db")
        con = sqlite3.connect("data/"+project.path+".db")
        cur = con.cursor()
        create_db(cur)
        with open("data/"+project.path+".json") as f:
            data=json.loads(f.read())
        for note in data["todo"]:
            cur.execute("INSERT INTO ChronoNote (text, datetime) VALUES (?,?)", [note["text"], note["datetime"]])
        for day in data["days"]:
            cur.execute("INSERT INTO ChronoDay (date) VALUES (?)", [day])
            for event in data["days"][day]["events"]:
                cur.execute("INSERT INTO ChronoEvent (date, what,tags,start,end) VALUES (?,?,?,?,?)", 
                [day, event["what"], reduce(lambda a,b: a+","+b, event["tags"]), event["start"], event["end"]])
            for run in data["days"][day]["sport"]["runs"]:
                cur.execute("INSERT INTO ChronoRun (date, time,start_time,distance) VALUES (?,?,?,?)", 
                [day, run["time"], run["start_time"], run["distance"]])
            for pushup in data["days"][day]["sport"]["pushups"]:
                for i in range(len(pushup["times"])):
                    cur.execute("INSERT INTO ChronoPushup (date, time, reps, start_time) VALUES (?,?,?,?)", 
                    [day, pushup["times"][i], pushup["mults"][i],pushup["start_time"]])
            for plank in data["days"][day]["sport"]["planks"]:
                cur.execute("INSERT INTO ChronoPlank (date, time, start_time) VALUES (?,?,?)", 
                [day, plank["time"], plank["start_time"]])
        for time in data["sevents"]:
            cur.execute("INSERT INTO ChronoTime (date, what, tags, start) VALUES (?,?,?,?)", 
            [time["tdate"], time["what"], reduce(lambda a,b: a+","+b, time["tags"]), time["start"]])
        con.commit()
        con.close()
        return reference

    @staticmethod
    def c_tags(project:ChronoProject, reference:str, start:str="start", end:str="stop")->str:
        """Prints all tags in [var:start,var:end]. Both var:start and var:end support IntelliRef."""
        days=project.analysis_get_between(start, end, reference)
        tags=set(reduce(lambda a,b:a+b,[event.tags for day in days  for event in day.events]))
        print(tags)
        return reference

    @staticmethod
    def c_export_graph_img(project:ChronoProject, reference:str, start:str="start", end:str="stop")->str:
        """Saves a picture of the tag graph from [var:start,var:end]. Both var:start and var:end support IntelliRef."""
        if not path.exists("./uimgs/"):
            mkdir("./uimgs/")
        G=project.get_tag_graph(start, end, reference)
        for i, cc in enumerate(nx.connected_components(G)):
            plt.clf()
            size=len(cc)
            plt.figure(figsize=(size*15/69+5-3*15/69,size*15/69+5-3*15/69)) #don'task
            sub_g=G.subgraph(cc)
            pos=nx.circular_layout(sub_g,scale=2)
            nx.draw(sub_g, pos, with_labels=True, edge_color="tab:red", node_size=300)
            plt.savefig(f"./uimgs/Graph-{start}-{end}-{i}")
        return reference

    @staticmethod
    def c_display_graph_img(project:ChronoProject, reference:str, start:str="start", end:str="stop")->str:
        """Saves a picture of the tag graph from [var:start,var:end]. Both var:start and var:end support IntelliRef."""
        G=project.get_tag_graph(start, end, reference)
        for cc in nx.connected_components(G):
            plt.clf()
            sub_g=G.subgraph(cc)
            pos=nx.circular_layout(sub_g,scale=2)
            nx.draw(sub_g, pos, with_labels=True, edge_color="tab:red", node_size=300)
            logging.info("Plotted a cc")
            plt.show()
            logging.info("Plot closed")
        return reference   

    @staticmethod
    def c_rename_tag(project:ChronoProject, reference:str, old_tag:str, new_tag:str)->str:
        """Rename all instances of var:old_tag to var:new_tag."""
        for day in project.days.values():
            for event in day.events:
                event.tags=[tag if tag!= old_tag else new_tag for tag in event.tags]
        return reference

    @staticmethod
    def c_delete_tag(project:ChronoProject, reference:str, del_tag:str)->str:
        """Delete all instances of var:del_tag. If the event has no tags after the deletion, tags=["deleted_tag"]"""
        for day in project.days.values():
            for event in day.events:
                n=len(event.tags)
                event.tags=[tag for tag in event.tags if tag != del_tag]
                if 0==len(event.tags)<n:
                    event.tags=["deleted_tag"]
                    logging.warning(f"Tags got deleted and the tags of {day.date} is now [deleted_tag]")
        return reference

    @staticmethod
    def c_delete_by_tag(project:ChronoProject, reference:str, tag:str, start:str, stop:str)->str:
        """Deletes all events with var:tag $\n$ tags. Both var:start and var:end support IntelliRef."""
        days=project.analysis_get_between(start,stop,reference)
        delete_by_tag(project,reference,tag,days)
        return reference

    @staticmethod
    def c_earliest_latest_plot(project:ChronoProject, reference:str, tags:str, start:str="start", stop:str="stop")->str:
        """Plot the earliest start and the latest stop of var:tag over time=[var:start,var:stop]. Both var:start and var:end support IntelliRef."""
        days=sorted(project.analysis_get_between(start, stop, reference),key=lambda x:x.date)
        tags_list=tags.split(",")
        no_time=time(hour=0,minute=0,second=0,microsecond=0)
        xs=[i for i,_ in enumerate(days)]
        ys_time={tag:[[no_time for _ in days],[no_time  for _ in days]] for tag in tags_list}
        for i,day in enumerate(days):
            if get_intersect(day.get_tags(), tags_list)!=[]:
                for tag in tags_list:
                    ys_time[tag][0][i]=min([event.start for event in day.events if tag in event.tags])
                    ys_time[tag][1][i]=max([event.start for event in day.events if tag in event.tags])
        ys={tag:times_tags_to_ints(ys_time[tag]) for tag in ys_time.keys()}
        for tag in tags_list:
            plt.plot([x for i,x in enumerate(xs) if ys[tag][0][i]!=0],[y for y in ys[tag][0] if y!=0],label=tag+" start",marker="*")
            plt.plot([x for i,x in enumerate(xs) if ys[tag][1][i]!=0],[y for y in ys[tag][1] if y!=0],label=tag+" stop",marker="*")
        plt.legend()
        plt.ylabel("Time")
        plt.xlabel("Date")
        max_y=max([max(max(ys[tag][0]),max(ys[tag][1])) for tag in tags_list])
        min_y=min([min(min(ys[tag][0]),min(ys[tag][1])) for tag in tags_list])
        yticks=[round(min_y*(5-i)/5+i/5*max_y) for i in range(6)]
        plt.yticks(yticks, [seconds_to_time(y).isoformat() for y in yticks])
        plt.show()    
        return reference

    @staticmethod
    def c_earliest_latest_sleep(project:ChronoProject, reference:str, start:str="start", stop:str="stop")->str:
        """Plots the start / end of the (nightly) sleep over time=[var:start,var:stop]. Both var:start and var:end support IntelliRef."""
        days=sorted(project.analysis_get_between(start, stop, reference),key=lambda x:x.date)
        if (days[0].date-timedelta(days=1)).isoformat() in project.days.keys():
            days=[project.days[(days[0].date-timedelta(days=1)).isoformat()]] + days
        xs:List[int]=[]
        ys:Tuple[List[int],List[int]]=([],[])
        for i in range(1,len(days)):
            split_sleep=False
            if "sleep" in days[i].get_tags():
                for event in days[i].events:
                    if "split_sleep" in event.tags:
                        split_sleep=True
                if not split_sleep:
                    xs.append(i)
                    ys[0].append(max([time_to_int(event.start) for event in days[i].events if "sleep" in event.tags]))
                    ys[1].append(min([time_to_int(event.end) for event in days[i].events if "sleep" in event.tags]))
                else:
                    for event in days[i-1].events:
                        if event.end==time(hour=23,minute=59) and "split_sleep" in event.tags:
                            ys[0].append(time_to_int(event.start)-24*60*60)
                            xs.append(i)
                            ys[1].append(min([time_to_int(event.end) for event in days[i].events if "sleep" in event.tags]))
        plt.plot([x for x in xs],[y for y in ys[0]],label="sleep start",marker="*")
        plt.plot([x for x in xs],[y for y in ys[1]],label="sleep stop",marker="*")
        plt.legend()
        plt.ylabel("Time")
        plt.xlabel("Date")
        max_y=max(ys[0]+ys[1])
        min_y=min(ys[0]+ys[1])
        yticks=[round(min_y*(5-i)/5+i/5*max_y) for i in range(6)]+[0]
        plt.yticks(yticks, [seconds_to_time(y).isoformat() if y>=0 else "-"+seconds_to_time(-y).isoformat() for y in yticks])
        plt.show()
        return reference

    @staticmethod
    def c_mk_event_by_delta(project:ChronoProject, reference:str, what:str,tags:str,start:str,duration:str,force:str="1")->str:
        """Creates a ChronoEvent(var:what,var:tags,var:start,var:start+var:duration)."""
        dur=time_from_str(duration)
        end_time=add_time_delta(time_from_str(start),timedelta(hours=dur.hour,minutes=dur.minute)).isoformat()
        MSSH.c_create_event(project,reference,what,tags,start,end_time,force)
        return reference

    @staticmethod
    def c_run_path(project:ChronoProject, reference:str, start:str="start", stop:str="stop")->str:
        """Plot the path of runs in (run_time,distance) space. Both var:start and var:end support IntelliRef."""
        days = project.analysis_get_between(start, stop, reference)
        xs=[] #distance
        ys=[] #time  
        for i in range(len(days)):
            lengths=sum([run.time for run in days[i].sport["runs"]])
            distance=sum([run.distance for run in days[i].sport["runs"]])
            pace=lengths/max(distance,1)
            if distance > 0:
                xs.append(distance)
                ys.append(pace)
        plt.close() # "Fix": 2 plots open, but one is empty
        fig, ax = plt.subplots()
        line, = ax.plot([], [], lw=2)
        ax.set_xlim(0.9*min(xs),1.1*max(xs))
        ax.set_ylim(0.9*min(ys),1.1*max(ys))
        ticks=get_pace_ticks(ys)
        ax.set_yticks(ticks[0])
        ax.set_yticklabels(ticks[1])

        def init():
            line.set_data([], [])
            return line,

        def animate(i, xs, ys):
            i=i%len(xs)
            line.set_data(xs[:i], ys[:i])
            ax.set_title(f"{i}/{len(xs)}")
            return line,    

        anim = animation.FuncAnimation(fig, lambda x: animate(x,xs,ys), init_func=init,
                               frames=len(xs)-1, interval=100, blit=False)

        plt.grid(True)
        logging.info("Displaying plot ...")
        plt.show()
        logging.info("Plot closed") 
        return reference

    @staticmethod
    def c_intelli_ref(project:ChronoProject, reference:str, sdate:str)->str:
        """
        Prints var:sdate as interpreted by IntelliRef.

        "start": The < date of all ChronoDays.

        "stop": The > date of all ChronoDays.

        "ref": The current reference.

        "today": The current date.

        "ix\" where x is an integer: The xth ChronoDay (sorted by date and starting at x=0). Also supports negative x (Going backwards from the > date).
        """
        print(project.date_from_str(sdate, reference).isoformat())
        return reference

    @staticmethod
    def c_gblf(project:ChronoProject, reference:str, ignored_tags:str,start:str="start", stop:str="stop")->str:
        """gblf: clusters after the latest split and prints the output."""
        G,f=project.get_gbl_data(start,stop,reference,ignored_tags.split(","))
        rho,clustering,events=mc.gbl_get_split_force(G,f)
        print(f"Clustering at {rho}:")
        for cluster in clustering:
            print(cluster)
        logging.info(f"Events: {events}")
        return reference

    @staticmethod
    def c_treeview(project:ChronoProject, reference:str, ignored_tags:str, start:str="start", stop:str="stop")->str:
        """TreeView of the CRMs after ignoring specified tags. Data is filtered to be from days in [start,stop]."""
        G,f=project.get_gbl_data(start,stop,reference,ignored_tags.split(","))
        ccs_data=mc.gbl_get_ccs(G,f)
        ccs=[cc for _,cc in ccs_data]
        assert len(ccs_data)>0
        n=len(ccs)
        subclusters=[{j:[k for k in range(len(ccs[i+1])) if mc.subset(ccs[i+1][k],ccs[i][j])] for j in range(len(ccs[i]))} for i in range(n-1)]
        trees=[[[] for j in range(n)] for i in range(len(ccs[0]))]
        for i in range(len(ccs[0])):
            trees[i][0].append(i)
            for j in range(n-1):
                tmp=list(reduce(lambda a,b:a+b,[subclusters[j][index] for index in trees[i][j]],[]))
                trees[i][j+1]=tmp
        x_start=0
        pos=[[[] for _ in ccs[0]] for cluster in ccs]    
        for tree in trees:
            xs=[]
            ys=[]
            for i,level in enumerate(tree):
                xs+=[x_start+j for j in range(len(level))]
                ys+=[i for _ in level]
                for index,j in enumerate(level):
                    pos[i][j]=[x_start+index,i]
            for i,level in enumerate(tree):
                if i < n-1:
                    for j1 in level:
                        for j2 in subclusters[i][j1]:
                            plt.plot([pos[i][j1][0],pos[i+1][j2][0]],[i,i+1],color="black")
            x_start+=max(len(level) for level in tree)
            plt.scatter(xs,ys,color="red")
        plt.yticks([i for i in range(len(ccs))],[cc[0] for cc in ccs_data])
        plt.show()
        return reference

    @staticmethod
    def c_fftplot(project:ChronoProject, reference:str,tag:str,min_period_length:str="2",max_period_length:str="31", start:str="start", stop:str="stop")->str:
        """FFT of a tag in the specified timeframe. Will shorten the timeframe if the tag does not occ on the first day."""
        MSSH.c_fill_empty_days(project,reference,start,stop)
        days = project.analysis_get_between(start, stop, reference)
        n=len(days)
        tags=project.get_tags()
        index_offsets:List[int]=[0,n-1]    
        if tag in tags:  
            for i in range(0,n):
                if tag in days[i].get_tags():
                    index_offsets[0]=i
                    break
            for i in range(1,n+1):
                if (tag in days[n-i].get_tags()):
                    index_offsets[1]=n-i
                    break
        else:
            for i in range(0,n):
                if tag in days[i].functions.keys():
                    index_offsets[0]=i
                    break
            for i in range(1,n+1):
                if tag in days[n-i].functions.keys():
                    index_offsets[1]=n-i
                    break
        if index_offsets[0]>0:
            logging.info(f"Ignored the first {index_offsets[0]} day(s)")
        if index_offsets[1]>0:
            logging.info(f"Ignored the last {index_offsets[1]} day(s)")
        ys=[]
        #populate ys
        for day in days[index_offsets[0]:index_offsets[1]]:
            if tag in day.functions.keys():
                ys.append(day.functions[tag])
            else:
                ys.append(get_time(day, tag))
        if len(ys)>0:avg=sum(ys)/len(ys)
        else: avg=0
        ys=[y-avg for y in ys]
        N = index_offsets[1]-index_offsets[0]
        T = 1
        y = np.array(ys)
        yf = fft(y)
        xf = [1/v if v!=0 else 2*(n+1) for v in list(fftfreq(N, T)[:N//2])]
        tmp=(2.0/N * np.abs(yf[:N//2]))
        plt.plot(xf, tmp,label=f"Influence(1/f), {N} data points")
        plt.scatter(xf, tmp,marker="*",c="red")
        if max_period_length=="max": max_period_length=str(n+1)
        plt.xlim(int(min_period_length),int(max_period_length))
        plt.grid()
        plt.title(f"fft({tag}):[{days[index_offsets[0]].date.isoformat()},{days[index_offsets[1]].date.isoformat()}]")
        plt.legend()
        plt.show()
        return reference

    @staticmethod
    def c_set_function(project:ChronoProject, reference:str,function_name:str,function_value:str)->str:
        """Set value of $function_name(reference)"""
        if reference in project.days.keys():
            project.days[reference].add_function(function_name,float(function_value))
        else:
            logging.warning(reference+" is not a valid date. Can't add function "+function_name)
        return reference

    @staticmethod
    def c_get_function(project:ChronoProject, reference:str,function_name:str)->str:
        """Set value of $function_name(reference)"""
        if reference in project.days.keys():
            print(project.days[reference].functions[function_name])
        else:
            logging.warning(reference+" is not a valid date. Can't view function "+function_name)
        return reference

    @staticmethod
    def c_review_days(project:ChronoProject, reference:str, ndays:str,interpolate:str="3")->str:
        assert len(project.settings["review_days"]["tags"])==9 #TODO: verbessern
        n_days=int(ndays)
        MSSH.c_oura_sleep(project,"ref",(datetime.today().date()-timedelta(days=n_days+1)).isoformat(),"stop")
        days=project.analysis_get_between("start","stop","ref")[-int(n_days)-1:-1]
        fs=project.get_functions(days)
        tags=project.settings["review_days"]["tags"]
        goals=project.settings["review_days"]["goals"]
        ys={tag:[] for tag in tags}
        goal_colors=project.settings["review_days"]["goal_colors"]
        normalizer={key:n_days*project.settings["review_days"]["normalizer"][key] for key in project.settings["review_days"]["normalizer"].keys()}
        for day in days:
            for tag in tags:
                if tag in fs: 
                    ys[tag].append(project.get_function(day.date,tag,int(interpolate)))
                    normalizer[tag]+=1
                else:
                    ys[tag].append(get_time(day, tag))
        tags_sum={tag:sum(ys[tag]) for tag in ys.keys()}
        fig, axs = plt.subplots(3, 3)
        for i in range(9):
            axs[i//3, i%3].plot(ys[tags[i]],label="Data")
            axs[i//3, i%3].scatter([j for j in range(len(ys[tags[i]]))],ys[tags[i]],label="DataPoints",c="red",marker="*")
            axs[i//3, i%3].plot([tags_sum[tags[i]]/max(normalizer[tags[i]],1) for _ in range(n_days)],label="Average")
            axs[i//3, i%3].plot([goals[tags[i]] for _ in range(n_days)],label="Reference")
            axs[i//3, i%3].set_title(tags[i],color=goal_colors[tags[i]][int(goals[tags[i]]<=tags_sum[tags[i]]/max(normalizer[tags[i]],1))])
        if tags[i]=="weight":
            axs[i//3, i%3].set_ylim((min([y for y in ys[tags[i]] if y >0])-1,max(max(ys[tags[i]])+1,goals[tags[i]])))
        elif tags[i]=="all_sleep":
            axs[i//3, i%3].set_ylim((min([y for y in ys[tags[i]] if y >0])-1,max(max(ys[tags[i]])+1,goals[tags[i]])))
            axs[i//3, i%3].legend(loc=2,prop={'size': 6})
        fig.tight_layout(pad=1.0)
        plt.show()
        return reference

    @staticmethod
    def c_show_sleep_day(project:ChronoProject, reference:str, day:str)->str:
        """"Plot the sleep phases of the given day. 4~Awake,3~Rem,2~light,1~deep"""
        if day in project.days.keys():
            if not project.days[day].sleep=="":
                events=[e for e in project.days[day].events if "all_sleep" in e.tags]
                plt.plot([int(sp) for sp in fix_oura(project.days[day].sleep)],label=f"sleepphases: {day}")
                plt.xticks([0,len(project.days[day].sleep)-1], [events[0].start.isoformat(),events[-1].end.isoformat()])
                plt.yticks([1,2,3,4],["deep","light","rem","awake"])
                plt.legend()
                plt.show()
        return reference

class ChronoClient:

    path:str
    project:Optional[ChronoProject]
    command_set:Dict[str, Callable[[Union[List[str],ChronoProject],str], None]]

    def c_quit(self, project:ChronoProject, reference:str)->str:
        """Quits Chrono."""
        print("quitting")
        return reference

    def c_commands(self, project:ChronoProject, reference:str)->str:
        """Prints all commands."""
        print(list(self.command_set.keys()))
        return reference

    def c_refresh(self, project:ChronoProject, reference:str)->str:
        """Saves and rebuilds the project."""
        project.save()
        self.build_ChronoProject(project.schedule)
        project.load_settings()
        project.set_alias(self.command_set)
        return reference

    def c_restore(self, project:ChronoProject, reference:str, code:str="0")->str:
        """Restores a project from a backup."""
        if int(code)==project.settings["code"]:
            tmp=project.path
            if os.path.isfile("data/"+project.path+"_backup.json"):
                self.build_ChronoProject(path=project.path+"_backup")
                self.project.path=tmp
            else:
                print("no backup available")
        return reference

    def c_help(self, project:ChronoProject, reference:str, cmd:str)->str:
        """Describes a given var:cmd."""
        cmd=cmd.lower()
        if cmd in project.alias.keys():
            print("calls : "+self.project.settings["alias"][cmd])
            called_cmd=self.project.settings["alias"][cmd].split(" ")[0]
            print(called_cmd+":")
            self.c_help(self.project, reference, called_cmd)
        elif cmd in self.command_set.keys():
            sig=signature(self.command_set[cmd])
            print(self.command_set[cmd].__doc__)
            if not len(sig.parameters.keys())==2:
                sig=str(sig).replace("(project: src.chrono_client.ChronoProject, reference: str", "")\
                    .replace(") -> str", "").replace("(p, r", "").replace(")", "")
                print("Arguments: "+sig[2:].replace(": str",""))
            else:
                print(f"{cmd} takes no arguments")
        else:
            logging.info(f"unknown command : {cmd}")
            print(f"unknown command : {cmd}")
        return reference

    def c_save(self, project:ChronoProject, reference:str)->str:
        """Saves the project."""
        shutil.copy("data/"+project.path+".json", "data/"+project.path+"_backup.json")
        project.save()
        return reference

    def c_lhof(self, project:ChronoProject, reference:str,args:str,f:str,*fargs:str)->str:
        """var:f(var:args+var:fargs) """
        if f in self.command_set.keys():
            argsl=args.split(",")
            aargs=argsl+list(fargs)
            return self.command_set[f](project,reference,*aargs)
        else:
            logging.warn(f"Can't find f: {f}")
            print(f"Can't find f: {f}") 
            return reference

    def c_rhof(self, project:ChronoProject, reference:str,args:str,f:str,*fargs:str)->str:
        """var:f(var:fargs+args)"""
        if f in self.command_set.keys():
            argsl=args.split(",")
            f_signature=signature(self.command_set[f])
            n=len(f_signature.parameters.items())
            test=[v.default for k, v in f_signature.parameters.items() if v.default is not Parameter.empty]
            aargs=list(fargs)+test[-(n-len(fargs)-len(argsl)):-len(argsl)]+argsl
            return self.command_set[f](project,reference,*aargs)
        else:
            logging.warn(f"Can't find f: {f}")
            print(f"Can't find f: {f}") 
            return reference

    def c_ihof(self, project:ChronoProject, reference:str,args:str,i:str,f:str,*fargs:str)->str:
        """var:f(var:fargs[0:i]+var:args+var:fargs[i:])."""
        raise NotImplementedError
        if f in self.command_set.keys():
            argsl=args.split(",")
            aargs=list(fargs)
            aargs=aargs[0:int(i)]+argsl+aargs[int(i):]
            return self.command_set[f](project,reference,*aargs)
        else:
            logging.warn(f"Can't find f: {f}")
            print(f"Can't find f: {f}") 
            return reference

    def c_options(self, project:ChronoProject, reference:str)->str:
        """Opens the settings file."""
        subprocess.Popen(["code","data/settings.json"], shell=True)
        return reference

    def c_write_overview(self, project:ChronoProject, reference:str)->str:
        """Writes an overview (pdf) of all commands / aliases."""
        to_section:Dict[str, List[str]]={
            REF_MAN:["setreference",
                "intelliref"],
            DAY_MAN:["mkday",
                "generatedays",
                "clear",
                "clearfuture",
                "deleteday",
                "fillemptydays"],
            EVE_MAN:["mkevent",
                "mktime",
                "changeeventtime",
                "changeeventwhat",
                "changeeventtags",
                "changeevent",
                "deleteevent",
                "end",
                "merge",
                "renametag",
                "deletetag",
                "deletebytag",
                "mkeventdelta"],
            SPO_MAN:["addrun",
                "addsitup",
                "addpushup",
                "addplank",
                "showruns",
                "plotrun",
                "delrun",
                "delsitup",
                "delpushup",
                "delplank",
                "runsum",
                "runstats"],
            DIS:["days",
                "times",
                "getcurrent",
                "today",
                "aliases",
                "exportschedule",
                "mk",
                "show",
                "tags",
                "help",
                "commands",
                "overview"],
            ANA:["plot",
                "plotweek",
                "stats",
                "heatmap",
                "heatmapsummary",
                "heatmapanimation",
                "rcc",
                "topdegrees",
                "bartagstime",
                 "bartags",
                "exportgraphimage",
                "showgraph",
                "earliestlatestplot",
                "earliestlatestplotsleep",
                "runpath"],
            NOT:["note",
                "notes",
                "deletenote",
                "deletenoteid",
                "deletenotes"],
            EXP:["split",
                "exportsport",
                "exportweek",
                "exportcsv",
                "tagsummary",
                "tagsummarymonth",
                "exportgraph",
                "exportdatabase"],
            OUR:["ourasleep",
                "getsleep",
                "lastnightsleep"],
            MIS:["quit",
                "restore",
                "refresh",
                "save",
                "lhof",
                "rhof",
                "ihof",
                "options"]}   
        header=["\\documentclass{article}", "\\usepackage{xcolor}", "\\usepackage{hyperref}", "\\usepackage{float}",
                "\\usepackage{graphicx}", "\\usepackage[encoding,filenameencoding=utf8]{grffile}"]
        with open("Overview.tex", "w+", encoding="utf-8") as f:
            f.write(list_to_string(header)+"\n"+"\\title{Overview: "+VERSION+"}\n")
            f.write("\\begin{document}\n")
            f.write("\\maketitle\n")
            f.write("\\section{Features}\n")
            f.write("\\subsection{IntelliRef}\n")
            f.write("IntelliRef supports the following shortcuts:\n")
            f.write("\\begin{itemize}\n")
            f.write("\\item \"start\": The $<$ date of all ChronoDays.\n")
            f.write("\\item \"stop\": The $>$ date of all ChronoDays.\n")
            f.write("\\item \"ref\": The current reference.\n")
            f.write("\\item \"today\": The current date.\n")
            f.write("\\item \"ix\" where x is an integer: The xth ChronoDay (sorted by date and starting at x=0). Also supports negative x (Going backwards from the $>$ date).\n")
            f.write("\\end{itemize}\n")
            f.write("\\section{Commands}\n")
            for key in to_section.keys():
                f.write("\\subsection{"+key+"}\n")
                for cmd in to_section[key]:
                    if not cmd=="options":
                        f.write("\\subsubsection*{"+cmd+"}\n\n")
                        sig=signature(self.command_set[cmd])
                        if not self.command_set[cmd].__doc__==None: 
                            f.write(self.command_set[cmd].__doc__.replace("_","\_").replace("<","$<$").replace(">","$>$")+"\n\n")
                        if not len(sig.parameters.keys())==2:
                            sig=str(sig).replace("(project: src.chrono_client.ChronoProject, reference: str", "")\
                                .replace(") -> str", "").replace("(p, r", "").replace(")", "").replace("_","\_")
                            f.write("Arguments: "+sig[2:].replace(": str","")+"\n")
                        else:
                            f.write(f"{cmd} takes no arguments\n\n")
                    else: 
                        f.write("\\subsubsection*{"+cmd+"}\n\n") # spaghetti code, but whatever. Try to fix this if you dare 
                        sig=signature(self.c_options)
                        if not self.command_set[cmd].__doc__==None: 
                            f.write(self.c_options.__doc__.replace("_","\_")+"\n\n")
                        if not len(sig.parameters.keys())==2:
                            sig=str(sig).replace("(project: src.chrono_client.ChronoProject, reference: str", "")\
                                .replace(") -> str", "").replace("(p, r", "").replace(")", "").replace("_","\_")
                            f.write(sig[2:]+"\n")
                        else:
                            f.write(f"{cmd} takes no arguments\n\n")
            f.write("\\section{Aliases}")
            for alias in self.project.alias.keys():
                f.write("\\subsection*{"+alias+"}\n")
                f.write(alias+" calls : "+self.project.settings["alias"][alias].replace("|>"," followed by ").replace("$","\\$").replace("_","\_")+"\n")
            f.write("\\end{document}\n")
        logging.info("generated .tex file")
        subprocess.run(["pdflatex", "Overview.tex"], stdout=subprocess.DEVNULL)
        subprocess.run(["pdflatex", "Overview.tex"], stdout=subprocess.DEVNULL)
        if os.path.isfile("Overview.tex"): os.remove("Overview.log")
        if os.path.isfile("Overview.aux"): os.remove("Overview.aux")
        if os.path.isfile("Overview.nav"): os.remove("Overview.nav")
        if os.path.isfile("Overview.out"): os.remove("Overview.out")
        if os.path.isfile("Overview.toc"): os.remove("Overview.toc")
        if os.path.isfile("Overview.tex"): os.remove("Overview.tex")
        if os.path.isfile("Overview.tex.bak"): os.remove("Overview.tex.bak")
        os.replace("Overview.pdf","./pdfs/Overview.pdf")
        logging.info("Removed useless files and generated pdf")
        subprocess.Popen([project.settings["pdfpath"],"./pdfs/Overview.pdf"], shell=True)
        logging.info("Pdf closed")
        return reference

    def add_commands(self)->None:
        """ Adds commands to the command set of this object."""
        self.command_set["quit"]=self.c_quit
        self.command_set["commands"]=self.c_commands
        self.command_set["restore"]=self.c_restore
        self.command_set["refresh"]=self.c_refresh
        self.command_set["help"]=self.c_help
        self.command_set["save"]=self.c_save
        self.command_set["lhof"]=self.c_lhof
        self.command_set["rhof"]=self.c_rhof
        self.command_set["ihof"]=self.c_ihof
        self.command_set["options"]=self.c_options
        self.command_set["overview"]=self.c_write_overview

    def __init__(self, path:str,s:ChronoSchedule,command_set:Dict[str, Callable[[Union[List[str],ChronoProject],str], None]]={}):
        self.path=path
        self.project=None
        self.command_set=command_set
        logging.basicConfig(filename="log.txt", level=logging.INFO)
        self.build_ChronoProject(s)

    def run(self)->None:
        """ Main loop of Chrono."""
        logging.info(f"run at : {datetime.today()}, Version: {VERSION}")
        if self.project== None:
            raise Exception("Missing project")
        last_command=""
        reference:str="base"
        print("Chrono active")
        if len(self.project.days.values())==0:
            print("No ChronoDays detected. If you are new consider using the \"help\"/\"commands\" commands to get more information.")
            print("For a more detailed documentation visit: https://github.com/MathManuelHinz/chrono/tree/master/documentation")
        while not last_command == "quit":
            print(reference, end=":")
            ip=split_command(input())
            if ip==[]:
                print("Please enter a command")
            else:
                last_command=ip[0].lower()
                if last_command in self.project.alias.keys():
                    logging.info(msg=f"{ip}")
                    try: reference = self.project.alias[last_command](self.project, reference, *ip[1:])
                    except Exception as e:
                        logging.warning(e)
                        print(e)
                elif last_command in self.command_set.keys():
                    logging.info(msg=f"{ip}")
                    try :reference= self.command_set[last_command](self.project, reference, *ip[1:])
                    except Exception as e:
                        logging.warning(e)
                        print(e)
                else:
                    logging.info(msg=f"Failed command: {ip}")
                    print("This command does not exist")
        logging.shutdown()

    def build_ChronoProject(self, s:ChronoSchedule=None, path:Optional[str]=None)->None:
        """ Builds a ChronoProject from a given path. """
        if path == None: path=self.path
        with open(path+".json", "r+", encoding="utf-8") as f:
            d=json.load(f)
        p=ChronoProject(name=d["name"], path=d["path"])
        if not s==None: p.set_schedule(s)
        for note in d["todo"]:
            p.todo.append(ChronoNote(note["text"], datetime.fromisoformat(note["datetime"])))
        for day in d["days"].values():
            events=[ChronoEvent(start=event["start"], end=event["end"], what=event["what"], tags=event["tags"]) for event in day["events"]]
            sport={sport:day["sport"][sport] for sport in day["sport"].keys()}
            p.add_day(ChronoDay(events=events, input_date=day["date"]))
            p.days[day["date"]].functions=day["functions"]
            for run in sport["runs"]:
                p.days[day["date"]].add_run(ChronoRunningEvent(run["time"],run["distance"],time_from_str(run["start_time"])))
            for situp in sport["situps"]:
                p.days[day["date"]].add_situp(ChronoSitUpsEvent(situp["time"],situp["mult"],time_from_str(situp["start_time"])))
            for plank in sport["planks"]:
                p.days[day["date"]].add_plank(ChronoPlankEvent(plank["time"],time_from_str(plank["start_time"])))
            for pushup in sport["pushups"]:
                p.days[day["date"]].add_pushup(ChronoPushUpEvent(pushup["times"],pushup["mults"],time_from_str(pushup["start_time"])))
            p.days[day["date"]].sleep=day["sleep"]
            p.days[day["date"]].update_after_run()   
        self.project=p
        self.project.sevents=[ChronoTime(sevent["tdate"], start=sevent["start"], what=sevent["what"], tags=sevent["tags"]) for sevent in d["sevents"]]
        self.add_commands()
        self.project.set_alias(self.command_set)

    def __repr__(self)->str:
        return self.project.__repr__()


def get_time(day:ChronoDay, tag:str)->float:
    """
    Returns the time [hours] a certain activity associated with the tag has been done on a given day. 
    """
    return sum([((datetime.combine(date.today(), event.end)\
                     - datetime.combine(date.today(), event.start))\
                .seconds/3600)*(tag in event.tags) for event in day.events])

def get_intersect_sum(day:ChronoDay, tags:List[str])->float:
    """
    Returns the amount of seconds a certain activity associated with the tags has been done on a given day. 
    Events which match with multiple tags are only counted once.
    """
    overhead=0
    for event in day.events:
        if not (I:=get_intersect(tags, event.tags))==[]:
            overhead += ((datetime.combine(date.today(), event.end)\
                - datetime.combine(date.today(), event.start))\
        .seconds/3600)*(len(I)-1)
    return overhead

def restrict(days:List[ChronoDay], coupling:List[float], width:int)->List[ChronoDay]:
    """
    Returns a subset of the list coupling, which are <= width days away from today.
    """
    tmp = date.today()
    rtn=[]
    for i, day in enumerate(days):
        if (tmp-day.date).days<=width:
            rtn.append(coupling[i])
    return rtn

def check_in_timeframe(tf:Tuple[time, time], event:ChronoEvent)->bool:
    """
    Checks if a ChronoEvent overlaps with a given timeframe.
    """
    return (tf[0]<= event.start and event.start < tf[1]) or (tf[0]< event.end and event.end <= tf[1])\
            or (event.start <= tf[0] and tf[0]<event.end) or (event.start < tf[1] and tf[1]<=event.end)

def delete_by_tag(project:ChronoProject, reference:str, tag:str, days:List[ChronoDay]):
    """Deletes all events with var:tag $\n$ tags."""
    for day in days:
        day.events=[event for event in day.events if not tag in event.tags]

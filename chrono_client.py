import json
from typing import Dict, List, Tuple, Callable, Union
from functools import reduce
from datetime import datetime, time, date, timedelta
from helper import list_to_string, write_table, split_command
import os
import logging
import subprocess
import secrets
from inspect import signature
#todo
#restructure times
#assert
#times
#-setup
#project stats
#add times to schedule?
#check overlap
#Fix ChronoDay
#Fix Schedule
#show schedule
#Hausarbeiten
#adobe api
#times / Waking up

class ChronoTime:
    """ This class should be used for very short events, such as deadlines."""

    start:time
    what:str
    tags:List[str]

    def __init__(self, start:str, what:str, tags:List[str]=[]):
        """Constructor: ChronoTime. start input will be converted to a time object, 
        the other inputs will be used as attributes. 
        Attributes:
            start: Should be of the form HH:MM
            what: Should be a reasonably short string
            tags: Should be a list of tags, seperated by "," given as a single string"""
        self.start=time(int(start[0:2]), int(start[3:5]))
        self.what=what
        self.tags=tags

    def to_dict(self)->Dict[str, Union[str, List[str]]]:
        """Used to save the object as a json."""
        d=dict()
        d["start"]=self.start.isoformat() #HH:MM:SS
        d["what"]=self.what
        d["tags"]=self.tags
        return d

    def __repr__(self)->str:
        """Returns a string representation of this object. Used by the command times"""
        return f"Time: {self.start}, what: {self.what}"

class ChronoEvent:
    """This class is used for all events which are to long for ChronoTime. 
    The majority of events should be ChronoEvents."""

    start:time
    end:time
    what:str
    tags:List[str]

    def __init__(self, start:str, end:str, what:str, tags:List[str]=[]):
        """Constructor: ChronoEvent. start and end input will be converted to a time object, 
        the other inputs will be directly used as attributes. 
        The starting time has to be strictly before the ending time.
        Attributes:
            start: Should be of the format HH:MM
            end: Should be of the format HH:MM
            what: Should be a reasonably short string
            tags: Should be a list of tags, seperated by "," given in the form of single string"""
        
        self.start=time(int(start[0:2]), int(start[3:5]))
        self.end=time(int(end[0:2]), int(end[3:5]))
        self.what=what
        self.tags=tags
        assert self.start<self.end

    def __repr__(self)->str:
        """Returns a string representation of this object. Used by the command today"""
        return f"From {self.start.isoformat()} until {self.end.isoformat()} : {self.what}"

    def to_dict(self)->Dict[str, Union[str, List[str]]]:
        """Used to save the object as a json."""
        d=dict()
        d["start"]=self.start.isoformat()
        d["end"]=self.end.isoformat()
        d["what"]=self.what
        d["tags"]=self.tags
        return d


class ChronoDay:
    """This class is used to organize ChronoEvent- and  ChronoTimes-objects. 
    Each page in the exported pdf should correspond to one ChronoDay-object."""
     
    day_start:time
    day_end:time
    events:List[ChronoEvent]
    date:date
    silent_events:List[ChronoTime]


    def __init__(self, events:List[ChronoEvent], input_date:str,day_start:str=None, day_end:str=None):
        """Constructor: ChronoDay. day_start and day_end input will be converted to a time object, 
        input_date will be converted to a date object and
        events will be saved as is. 
        Attributes:
            events: A list of ChronoEvents. Should be none empty if day_start, day_end are omitted, unless a schedule is used.
            input_date: The date of the Day. Should be of the format YYYY-MM-DD
            day_start: Optional, if events isn`t empty. Should be of the format HH:MM
            day_end: Optional, if events isn`t empty. Should be of the format HH:MM"""
        self.events=events
        if not events == []:
            maxmin=self.get_bounds()
        if day_start == None:
            try: self.day_start=maxmin[0]
            except: logging.warning("ChronoDay needs to have at least one of the following: none empty events list, day_start")
        else:
            self.day_start=time(int(day_start[0:2]), int(day_start[3:5]))
        if day_end == None:
            try: self.day_end=maxmin[1]
            except: logging.warning("ChronoDay needs to have at least one of the following: none empty events list, day_end")
        else:
            self.day_end=time(int(day_end[0:2]), int(day_end[3:5]))
        self.date=date(int(input_date[0:4]), int(input_date[5:7]), int(input_date[8:10]))
        self.silent_events=[]

    def __repr__(self)->str:
        """Returns a string representation of this object. Used by the command today"""
        if self.events == []:
            return  f"{self.date.__str__()}:\n\nFrom {self.day_start.isoformat()} till {self.day_end.isoformat()}\n\n"
        else: return f"{self.date.__str__()}:\n\nFrom {self.day_start.isoformat()} till {self.day_end.isoformat()}\n\n" + reduce(lambda a,b: a+"\n\n"+b, [event.__repr__() for event in sorted(self.events, key=lambda x: x.start)])

    def check_overlap(self, event1:ChronoEvent, event2:ChronoEvent)->bool:
        """Checks if two events overlap."""
        if event1.start==event2.start:
            rtn=True 
        elif event1.start < event2.start:
            rtn= event2.start < event1.end
        else:
            rtn= event1.start < event2.end
        return rtn

    def add_silent(self, silent_event:ChronoTime)->None:
        """Adds a ChronoTime object to the silent_events list."""
        self.silent_events.append(silent_event)

    def add_event(self, event:ChronoEvent, force:bool=False)->None:
        """
        This function tries a event to the events list. 
        This fails if there is an overlap with an already existing event. Adding the event can be forced by 
        setting force to True. In this case overlapping existing events will be deleted. 
        Adding an event may change the day_start, day_end attributes.
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
        else: raise Exception("Overlap")
        cs, ce=self.get_bounds()
        if event.start <= cs:
            self.day_start=event.start
        if event.end >= ce:
            self.day_end=event.end

    def fill_empty(self, what:str="Relax")->None: #not implemented yet
        raise NotImplementedError
        pass

    def get_slots(self)->List[ChronoEvent]:
        """returns the events sorted by starting time."""
        return sorted(self.events, key=lambda x:x.start)

    def get_bounds(self)->Tuple[str, str]:
        """Returns the earliest starting time and the latest ending time."""
        assert not self.events==[]
        starts=[event.start for event in self.events]
        ends=[event.end for event in self.events]
        return min(starts), max(ends)

    def merge(self)->None:
        """Merges two events into one if they have the same what attribute and no time in between them."""
        for e1 in self.events:
            for e2 in self.events:
                if not e1==e2 and e1.end==e2.start and e1.what==e2.what:
                    e=ChronoEvent(e1.start.isoformat(), e2.end.isoformat(), e1.what, list(set(e1.tags+e2.tags)))
                    logging.critical(f"merged to {e}")
                    self.events.remove(e1)
                    self.events.remove(e2)
                    self.add_event(e)
                    return self.merge()

    def to_dict(self)->Dict[str, Union[str, Dict[str, Union[str, List[str]]]]]:
        """Used to save the object as a json."""
        d=dict()
        d["day_start"]=self.day_start.isoformat()
        d["day_end"]=self.day_end.isoformat()
        d["date"]=self.date.__str__()
        d["events"]=[event.to_dict() for event in self.events]
        d["sevents"]=[event.to_dict() for event in self.silent_events]
        return d

class ChronoSchedule:
    
    days:List[List[ChronoEvent]]

    def __init__(self, path):
        self.days=[[] for _ in range(7)]
        with open(path, "r+", encoding="utf-8") as f:
            data=json.load(f)
        for i  in range(7):
            self.days[i]=[ChronoEvent(e["start"], e["end"], e["what"], e["tags"]) for e in data[i]]
    
MSSH_color_scheme:Dict[str, str]={
    "leben":"black",
    "relax":"black",
    "mathe":"red",
    "uni":"red",
    "creative":"green",
    "programming":"blue",
    "tine":"magenta"
}

class ChronoProject:

    path:str
    name:str
    days:Dict[str, ChronoDay]
    schedule:ChronoSchedule

    def __init__(self, name:str, path:str, schedule:ChronoSchedule=None):
        self.name=name
        self.path=path
        self.days=dict()
        self.schedule=schedule
    
        self.header=["\\documentclass{article}"]

    def add_day(self,day:ChronoDay)->None:
        if not day.date.isoformat() in self.days.keys():
            if not self.schedule == None:
                day.events += self.schedule.days[day.date.weekday()]
                day.day_start, day.day_end = day.get_bounds()
            self.days[day.date.isoformat()]=day
        else:
            logging.warning(f"can`t add day {day.date.isoformat()}")

    def add_event(self, event:ChronoEvent, date:str, force:bool=False)->None:
        self.days[date].add_event(event, force)

    def __repr__(self)->str:
        return reduce(lambda a,b: a+"\n"+b, [day.__repr__() for day in self.days.values()])

    def get_meta(self)->List[str]:
        return ["\\title{" + f"{self.name}"+"}"]

    def export_pdf(self, days=[""])->int:
        if days==[""]:
            days=[day for day in self.days.keys()]
        days=[self.days[key] for key in filter(lambda x: x in self.days.keys(), days)]
        header=["\\documentclass{article}", "\\usepackage{xcolor}"]
        with open(self.name+".tex", "w+", encoding="utf-8") as f:
            f.write(list_to_string(header)+"\n"+list_to_string(self.get_meta())+"\n")
            f.write("\\begin{document}\n")
            f.write("\\maketitle\n")
            pagen=1
            for day in sorted(days, key=lambda x: x.date):
                if day.date < date.today():
                    pagen += 1
                if day.events == []:
                    pass
                else:
                    day.merge()
                    f.write("\\section*{"+f"{day.date}"+ "}\n")
                    stats=ChronoStats.get_stats(day)
                    write_table(f, dims=[2, len(stats)], data=[[stat[0], str(stat[1])] for stat in stats])
                    slots=day.get_slots()
                    data=[[f"{slot.start.isoformat()}-{slot.end.isoformat()}", "\\textcolor{"+MSSH_color_scheme[slot.tags[0]]+"}{"+f"{slot.what}"+"}"]for slot in slots]
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
        return pagen
        
    def save(self, path=None)->None:
        if path == None: path=self.path
        export=dict()
        export["name"]=self.name
        export["path"]=path
        export["days"]={key:self.days[key].to_dict() for key in self.days.keys()}
        with open(path+".json", "w+", encoding="utf-8") as f:
            json.dump(export, f)

class MSSH:

    @staticmethod
    def c_setr(project:ChronoProject, reference:str, new_reference:str)->str:
        if new_reference=="today":return date.today().isoformat()
        return new_reference

    @staticmethod
    def c_create_day(project:ChronoProject, reference:str, date:str, start="08:00", end="22:00")->str:
        if len(date.split("-"))==3:
            project.add_day(ChronoDay(input_date=date, events=[], day_start=start, day_end=end))
        elif date=="today":
            project.add_day(ChronoDay(input_date=datetime.now().isoformat(), events=[], day_start=start, day_end=end))
        else:
            print("failed")
            logging.info(f"failed: createDay({reference},{date},{start},{end})")
        return "base"

    @staticmethod
    def c_create_event(project:ChronoProject, reference:str, what:str, tags:str="relax", start:str="08:00", end:str="10:00", force:bool=False)->str:
        if reference in project.days.keys():
            try:
                project.add_event(ChronoEvent(start=start, end=end, what=what, tags=tags.split(",")), reference, force=int(force))
            except Exception as e:
                print(e)
                logging.info(e)
        else:
            print("invalid key")
            logging.info(f"invalid key (addEvent) : {reference}")
        return reference

    @staticmethod
    def c_create_time(project:ChronoProject, reference:str, what:str, tags:str="relax", start:str="08:00")->str:
        if reference in project.days.keys():
            try:
                project.days[reference].add_silent(ChronoTime(start=start,what=what, tags=tags.split(",")))
            except Exception as e:
                print(e)
                logging.info(e)
        else:
            print("invalid key")
            logging.info(f"invalid key (addEvent) : {reference}")
        return reference

    @staticmethod
    def c_days(project:ChronoProject, reference:str)->str:
        print(project.days.keys())
        return reference
    
    @staticmethod
    def c_mk(project:ChronoProject, reference:str, days="")->str:
        project.export_pdf([date.today().isoformat() if day=="today" else day for day in days.split(",")])
        return reference

    @staticmethod
    def c_save(project:ChronoProject, reference:str)->str:
        project.save()
        return reference

    @staticmethod
    def c_show(project:ChronoProject, reference:str, days="")->str:
        page=project.export_pdf([date.today().isoformat() if day=="today" else day for day in days.split(",")])
        if page > len(project.days.keys()): page=1
        if not days == "": page=1 
        subprocess.Popen([secrets.path, "/A" ,f"page={page}", project.name+".pdf"], shell=True)
        return reference

    @staticmethod
    def c_gen_days(project:ChronoProject, reference:str, days:str="7")->str:
        d=date.today()
        for _ in range(int(days)):
            project.add_day(ChronoDay(input_date=d.isoformat(), events=[]))
            d += timedelta(days=1)
        return reference
    
    @staticmethod
    def c_clear(project:ChronoProject, reference:str, code:str="0")->str:
        if code == "42279":
            project.save(path="backup") 
            project.days={}
        else:
            logging.warning(f"wrong code: {code}")
        return reference

    @staticmethod
    def c_clear_future(project:ChronoProject, reference:str, code:str="0")->str:
        if code == "42279":
            project.save(path="backup") 
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
        if date.today().isoformat() in project.days.keys():
            for event in project.days[date.today().isoformat()].events:
                if event.start <= datetime.now().time()<=event.end:
                    print(event)
                    return reference
        print("no current event")
        return reference

    @staticmethod
    def c_get_next(project:ChronoProject, reference:str)->str:
        if date.today().isoformat() in project.days.keys():
           for slot in project.days[date.today().isoformat()].get_slots():
               print(slot)
        print("no current event")
        return reference

    @staticmethod
    def c_today(project:ChronoProject, reference:str)->str:
        if date.today().isoformat() in project.days.keys():
            print(project.days[date.today().isoformat()])
        else:
            print("no plan for today")
        return reference

    @staticmethod
    def c_day(project:ChronoProject, reference:str)->str:
        if reference in project.days.keys():
            print(project.days[reference])
        else:
            print(f"no plan for {reference}")
        return reference

    @staticmethod
    def c_delete_day(project:ChronoProject, reference:str)->str:
        if reference in project.days.keys():
            project.days.pop(reference)
            print(project.days)
        return reference
    
    @staticmethod
    def c_delete_event(project:ChronoProject, reference:str, start:str, stop:str)->str:
        if reference in project.days.keys():
            for event in project.days[reference].events:
                if event.start.isoformat()[:5]==start and event.end.isoformat()[:5]==stop:
                    print("removed")
                    project.days[reference].events.remove(event)
                    return reference
        return reference

    @staticmethod
    def c_end(project:ChronoProject, reference:str)->str:
        for event in project.days[date.today().isoformat()].events:
            if event.start <= datetime.now().time()<=event.end:
                event.end=datetime.now().time()
                return reference
        logging.warning("coudln`t end event: no current event")
        return reference

    @staticmethod
    def c_times(project:ChronoProject, reference:str, days:int="1")->str:
        d=date.today()
        for _ in range(int(days)):
            if d.isoformat() in project.days.keys():
                for time in project.days[d.isoformat()].silent_events:
                    print(f"{d.isoformat()} : {time}")
            d += timedelta(days=1)
        return reference

    @staticmethod
    def c_change_event_time(project:ChronoProject, reference:str, start:str, stop:str, nstart:str="08:00", nend:str="10:00")->str:
        if reference in project.days.keys():
            for e in project.days[reference].events:
                if e.start.isoformat()[:-3]==start and e.end.isoformat()[:-3]==stop:
                    e.start=time(int(nstart[0:2]), int(nstart[3:5]))
                    e.end=time(int(nend[0:2]), int(nend[3:5]))
                    return reference

    @staticmethod        
    def c_change_event_what(project:ChronoProject, reference:str, start:str, stop:str, what:str)->str:
        if reference in project.days.keys():
            for e in project.days[reference].events:
                if e.start.isoformat()[:-3]==start and e.end.isoformat()[:-3]==stop:
                    e.what=what
                    return reference

    @staticmethod        
    def c_change_event_tags(project:ChronoProject, reference:str, start:str, stop:str, tags:str)->str:
        if reference in project.days.keys():
            for e in project.days[reference].events:
                if e.start.isoformat()[:-3]==start and e.end.isoformat()[:-3]==stop:
                    e.tags=tags.split(",")
                    return reference

    @staticmethod
    def c_change_event(project:ChronoProject, reference:str, start:str, stop:str, mode:str, *args)->str:
        if mode=="time":
            return MSSH.c_change_event_time(project, reference, start, stop, *args)
        elif mode=="what":
            return MSSH.c_change_event_what(project, reference, start, stop, *args)
        elif mode=="tags":
            return MSSH.c_change_event_tags(project, reference, start, stop, *args)
        else:
            raise Exception("unknown mode")
        
MSSH_COMMS={
    "setr":MSSH.c_setr,
    "save":MSSH.c_save,
    "mkDay":MSSH.c_create_day,
    "mkEvent":MSSH.c_create_event,
    "mkTime":MSSH.c_create_time,
    "days":MSSH.c_days,
    "mk":MSSH.c_mk,
    "show":MSSH.c_show,
    "times":MSSH.c_times,
    "genDays":MSSH.c_gen_days,
    "clear":MSSH.c_clear,
    "clearf":MSSH.c_clear_future,
    "getCurrent":MSSH.c_get_current,
    "today":MSSH.c_today,
    "day":MSSH.c_day,
    "changeEtime":MSSH.c_change_event_time,
    "changeEwhat":MSSH.c_change_event_what,
    "changeEtags":MSSH.c_change_event_tags,
    "changeEvent":MSSH.c_change_event,
    "delDay":MSSH.c_delete_day,
    "delEvent":MSSH.c_delete_event, 
    "end":MSSH.c_end
}

class ChronoClient:

    def c_quit(self, project:ChronoProject, reference:str)->str:
        print("quitting")
        return reference

    def c_commands(self, project:ChronoProject, reference:str)->str:
        print(self.command_set.keys())
        return reference

    def c_refresh(self, project:ChronoProject, reference:str)->str:
        project.save()
        self.build_ChronoProject()
        return reference

    def c_restore(self, project:ChronoProject, reference:str, code:str=0)->str:
        if code== "42279":
            tmp=project.path
            if os.path.isfile("backup.json"):
                self.build_ChronoProject(path="backup")
                self.project.path=tmp
            else:
                print("no backup available")
        return reference

    def c_help(self, project:ChronoProject, reference:str, cmd:str):
        if cmd in self.command_set.keys():
            sig=signature(self.command_set[cmd])
            if not len(sig.parameters.keys())==2:
                sig=str(sig).replace("(project: chrono_client.ChronoProject, reference: str", "").replace(") -> str", "")
                print(sig[2:])
            else:
                print(f"{cmd} takes no arguments")
        else:
            logging.info(f"unknown command : {cmd}")
            print(f"unknown command : {cmd}")
        return reference

    def __init__(self, path:str, command_set:Dict[str, Callable[[List[str]], None]]={}):
        self.path=path
        self.project=None
        self.command_set=command_set
        self.command_set["quit"]=self.c_quit
        self.command_set["commands"]=self.c_commands
        self.command_set["restore"]=self.c_restore
        self.command_set["refresh"]=self.c_refresh
        self.command_set["help"]=self.c_help
        logging.basicConfig(filename="log.txt", level=logging.INFO)

    def run(self)->None:
        logging.info(f"run at : {datetime.today()}")
        if self.project== None:
            raise Exception("Missing project")
        commands=[""]
        reference="base"

        print("Chrono active")
        
        while not commands[-1] == "quit":
            print(reference, end=":")
            ip=split_command(input())
            commands.append(ip[0])
            if commands[-1] in self.command_set.keys():
                logging.info(msg=f"{ip}")
                try :reference= self.command_set[commands[-1]](self.project, reference, *ip[1:])
                except Exception as e:
                    logging.warning(e)
                    print(e)
            else:
                logging.info(msg=f"failed command: {ip}")
                print("This command does not exist")
        logging.shutdown()

    def build_ChronoProject(self, path:str=None)->ChronoProject:
        if path == None: path=self.path
        with open(path+".json", "r+", encoding="utf-8") as f:
            d=json.load(f)
        p=ChronoProject(name=d["name"], path=d["path"])
        for day in d["days"].values():
            events=[ChronoEvent(start=event["start"], end=event["end"], what=event["what"], tags=event["tags"]) for event in day["events"]]
            sevents=[ChronoTime(start=event["start"], what=event["what"], tags=event["tags"]) for event in day["sevents"]]
            p.add_day(ChronoDay(events=events, input_date=day["date"], day_start=day["day_start"], day_end=day["day_end"]))
            for time in sevents:
                p.days[day["date"]].add_silent(time)
        self.project=p

    def __repr__(self)->str:
        return self.project.__repr__()

class ChronoStats:
    @staticmethod
    def get_stats(chrono:Union[ChronoDay])->List[Tuple[str,float]]:
        if type(chrono)==ChronoDay:
            return ChronoStats.get_stats_day(chrono)

    @staticmethod
    def get_stats_day(day:ChronoDay)->List[Tuple[str,float]]:
        mathe=sum([((datetime.combine(date.today(), event.end) - datetime.combine(date.today(), event.start)).seconds/3600)*("mathe" in event.tags) for event in day.events])
        leben=sum([((datetime.combine(date.today(), event.end) - datetime.combine(date.today(), event.start)).seconds/3600)*("leben" in event.tags) for event in day.events])
        vorlesung=sum([((datetime.combine(date.today(), event.end) - datetime.combine(date.today(), event.start)).seconds/3600)*("vorlesung" in event.tags) for event in day.events])
        nvorlesung=mathe-vorlesung
        return [("Stunden Mathe", round(mathe, ndigits=3)), ("Stunden Vorlesung", round(vorlesung, ndigits=3)),("Stunden Mathe (nicht Vorlesung)", round(nvorlesung, ndigits=3)), ("Stunden Leben", round(leben, ndigits=3))]
        
import json
from typing import Dict, List, Tuple, Callable, Union
from functools import reduce
from datetime import datetime, time, date, timedelta
from helper import list_to_string, write_table, split_command, get_color, get_intersect
import os
import logging
import subprocess
from inspect import signature
import matplotlib.pyplot as plt
import shutil
#todo
#ToDo
#getNext
#speed up plot_week
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
#adobe api, send help
#times / Waking up
#docstring ausführlicher
#tests
#tageslücken

WEEKDAYS=["Monday", "Tuesday", "Wendsday", "Thursday", "Friday","Saturday", "Sunday"]

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
    

class ChronoNote:
    """One bullet point on the todo list."""
    text:str
    dt:datetime

    def __init__(self, text:str, dt:datetime=datetime.now()):
        """Saves a text and takes dt to be the time this object gets created."""
        self.text=text
        self.dt=dt
    
    def __repr__(self)->str:
        return self.text

    def to_dict(self)->Dict[str, str]:
        """Used to save the ChronoNote."""
        d=dict()
        d["text"]=self.text
        d["datetime"]=self.dt.date().isoformat()+"_"+self.dt.time().isoformat()
        return d


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


class ChronoProject:

    path:str
    name:str
    todo:List[ChronoNote]
    days:Dict[str, ChronoDay]
    schedule:ChronoSchedule

    def __init__(self, name:str, path:str, schedule:ChronoSchedule=None):
        self.name=name
        self.path=path
        self.days=dict()
        self.schedule=schedule
        self.todo=[]
        self.header=["\\documentclass{article}"]
        self.scheme=MSSH_color_scheme
        self.load_settings()

    def load_settings(self)->None:
        with open("settings.json", "r+", encoding="utf-8") as f:
            self.settings=json.load(f)
        self.scheme=self.settings["color_scheme"]

    def add_note(self, note:ChronoNote)->None:
        if not note.text in map(lambda x: x.text, self.todo):
            self.todo.append(note)
        else:
            print("duplicate ChronoNote")

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
        header=["\\documentclass{article}", "\\usepackage{xcolor}","\\usepackage{hyperref}"]
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
                    f.write("\\hypertarget{"+f"{day.date}"+"}{}\n")
                    #stats=ChronoStats.get_stats(day)
                    #write_table(f, dims=[2, len(stats)], data=[[stat[0], str(stat[1])] for stat in stats])
                    slots=day.get_slots()
                    data=[[f"{slot.start.isoformat()}-{slot.end.isoformat()}", "\\textcolor{"+get_color(self.scheme, slot.tags)+"}{"+f"{slot.what}"+"}"]for slot in slots]
                    write_table(f, [2, len(slots)], data=data)
                    write_table(f, [2, len(day.silent_events)], data=[[time.start.isoformat(), time.what] for time in day.silent_events])
                    f.write("\\clearpage")
            f.write("\\section*{"+"ToDo:"+"}\n")
            f.write("\\begin{enumerate}\n")
            for note in self.todo:
                f.write("\\item " + note.text + "\n")
            f.write("\\end{enumerate}\n")
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
        export["todo"]=[note.to_dict() for note in self.todo]
        export["name"]=self.name
        export["path"]=path
        export["days"]={key:self.days[key].to_dict() for key in self.days.keys()}
        with open(path+".json", "w+", encoding="utf-8") as f:
            json.dump(export, f)


class MSSH:

    @staticmethod
    def c_setr(project:ChronoProject, reference:str, new_reference:str)->str:
        """sets the reference to var:reference."""
        if new_reference=="today":new_reference=date.today().isoformat()
        if not (new_reference in project.days.keys()): 
            try: 
                print("Couldn`t find reference, generating new ChronoDay.")
                project.add_day(ChronoDay(input_date=new_reference, events=[]))
            except:
                print("Couldn`t find or create reference.")
        return new_reference

    @staticmethod
    def c_create_day(project:ChronoProject, reference:str, date:str, start="08:00", end="22:00")->str:
        """Creates a ChronoDay given:"""
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
        """Creates a ChronoEvent given:"""
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
        """Creates a ChronoTime given:"""
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
        """Prints the days saved in this ChronoProject."""
        print(project.days.keys())
        return reference
    
    @staticmethod
    def c_mk(project:ChronoProject, reference:str, days="")->str:
        """Exports a set of days (seperated by commata) to pdf."""
        project.export_pdf([date.today().isoformat() if day=="today" else day for day in days.split(",")])
        return reference

    @staticmethod
    def c_show(project:ChronoProject, reference:str, days="")->str:
        """Exports the ChronoProject to pdf and opens the file."""
        project.export_pdf()
        subprocess.Popen([project.settings["pdfpath"], "/A" ,f"nameddest={date.today().isoformat()}", project.name+".pdf"], shell=True)
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
        if code == "42279":
            project.save(path="backup") 
            project.days={}
        else:
            logging.warning(f"wrong code: {code}")
        return reference

    @staticmethod
    def c_clear_future(project:ChronoProject, reference:str, code:str="0")->str:
        """Clears all days in the future if the var:code is correct."""
        if code==project.settings["code"]:
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
        """Get the current event."""
        if date.today().isoformat() in project.days.keys():
            for event in project.days[date.today().isoformat()].events:
                if event.start <= datetime.now().time()<=event.end:
                    print(event)
                    return reference
        print("no current event")
        return reference

    @staticmethod
    def c_get_next(project:ChronoProject, reference:str)->str:
        """G"""
        if date.today().isoformat() in project.days.keys():
           for slot in project.days[date.today().isoformat()].get_slots():
               print(slot)
        print("no current event")
        return reference

    @staticmethod
    def c_today(project:ChronoProject, reference:str)->str:
        """Prints the plan for today."""
        if date.today().isoformat() in project.days.keys():
            print(project.days[date.today().isoformat()])
        else:
            print("no plan for today")
        return reference

    @staticmethod
    def c_day(project:ChronoProject, reference:str)->str:
        """Prints the plan for the current reference."""
        if reference in project.days.keys():
            print(project.days[reference])
        else:
            print(f"no plan for {reference}")
        return reference

    @staticmethod
    def c_delete_day(project:ChronoProject, reference:str)->str:
        """Deletes the reference day."""
        if reference in project.days.keys():
            project.days.pop(reference)
            print(project.days)
        return reference
    
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
    def c_times(project:ChronoProject, reference:str, days:int="1")->str:
        """Prints the ChronoTimes of the next var:days days."""
        d=date.today()
        for _ in range(int(days)):
            if d.isoformat() in project.days.keys():
                for time in project.days[d.isoformat()].silent_events:
                    print(f"{d.isoformat()} : {time}")
            d += timedelta(days=1)
        return reference

    @staticmethod
    def c_change_event_time(project:ChronoProject, reference:str, start:str, stop:str, nstart:str="08:00", nend:str="10:00")->str:
        """Changes the timeframe of a ChronoEvent."""
        if reference in project.days.keys():
            for e in project.days[reference].events:
                if e.start.isoformat()[:-3]==start and e.end.isoformat()[:-3]==stop:
                    e.start=time(int(nstart[0:2]), int(nstart[3:5]))
                    e.end=time(int(nend[0:2]), int(nend[3:5]))
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
    def c_plot_stats(project:ChronoProject, reference:str, tags:str="mathe,programming")->str:
        """Plots the hours of var:tags and their sum."""
        tags=tags.split(",")
        n=len(project.days)
        assert not "sum" in tags
        xs=[i for i in range(n)]
        ys={tag:[] for tag in tags}
        days = list(sorted(project.days.values(), key=lambda x: x.date))
        for day in days:
            for tag in tags:
                ys[tag].append(get_time(day, tag))
        corr=[0 for day in days]
        for i in range(n):
           corr[i]=get_intersect_sum(days[i], tags)
        corr=[0 for day in days]
        for i in range(n):
            for event in days[i].events:
                if not (I:=get_intersect(tags, event.tags))==[]:
                    corr[i] += ((datetime.combine(date.today(), event.end)\
                     - datetime.combine(date.today(), event.start))\
                .seconds/3600)*(len(I)-1)
        ys["sum"]=[sum([ys[tag][i] for tag in tags])-corr[i] for i in range(n)] #fix here
        ax=plt.subplot(111)
        box = ax.get_position()
        ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        for tag in ys.keys():
            plt.plot(xs, ys[tag], label=tag)
        if not days == []: 
            zeroday=days[0].date.weekday()
            WDA=[sum(wds:=[ys["sum"][i] for i in range(n) if (i+zeroday)%7==wd])/len(wds) for wd in range(7)] 
            plt.plot(xs,[WDA[day.date.weekday()] for day in days],"--",label="wda")
        if (tmp := date.today()).isoformat() in project.days.keys():
            plt.scatter([d:=(tmp-days[0].date).days], ys["sum"][d], label="Today", marker="*", color="red", s=[70])
        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        plt.show()
        return reference

    @staticmethod
    def c_plot_week(project:ChronoProject, reference:str, tags:str="mathe,programming,korean", k:str="7")->str:
        """Plots the hours of var:tags and their sum."""
        k=int(k)
        tags=tags.split(",")
        n=len(project.days)
        assert not "sum" in tags
        xs=[i for i in range(n)]
        ys={tag:[] for tag in tags}
        days = list(sorted(project.days.values(), key=lambda x: x.date))
        for day in days:
            for tag in tags:
                ys[tag].append(get_time(day, tag))
        corr=[0 for day in days]
        for i in range(n):
            corr[i]=get_intersect_sum(days[i], tags)
        ys["sum"]=[sum([ys[tag][i] for tag in tags])-corr[i] for i in range(n)]
        ax=plt.subplot(111)
        box = ax.get_position()
        ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        tmp = date.today()
        d=(tmp-days[0].date).days
        week_splice=lambda x : x[d-k:d+1]
        for tag in ys.keys():
            plt.plot(week_splice(xs), week_splice(ys[tag]), label=tag)
        if not days == []: 
            zeroday=days[0].date.weekday()
            WDA=[sum(wds:=[ys["sum"][i] for i in range(n) if (i+zeroday)%7==wd])/len(wds) for wd in range(7)] 
            plt.plot(week_splice(xs),week_splice([WDA[day.date.weekday()] for day in days]),"--",label="wda")
        if tmp.isoformat() in project.days.keys():
            plt.scatter([d], ys["sum"][d], label="Today", marker="*", color="red", s=[70])
        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        plt.xticks(week_splice(xs), week_splice([WEEKDAYS[day.date.weekday()][0:3]+"." for day in days]))
        plt.show()
        return reference

    @staticmethod
    def c_note(project:ChronoProject, reference:str, text:str)->str:
        """Adds a note to the todo list."""
        project.add_note(ChronoNote(text))
        return reference

    @staticmethod
    def c_todo(project:ChronoProject, reference:str)->str:
        """Prints todo list."""
        print("Todo:")
        for i, note in enumerate(project.todo):
            print(str(i+1)+".: "+str(note))
        return reference

    @staticmethod
    def c_del_note(project:ChronoProject, reference:str, text:str)->str:
        """Deletes the ChronoNote with the text var:text."""
        project.todo=list(filter(lambda x: not x.text==text , project.todo))
        return reference

    @staticmethod
    def c_stats(project:ChronoProject, reference:str, tags:str)->str:
        """Displays stats for given tags."""
        tags=tags.split(",")
        hours=[]
        days=list(project.days.values())
        for tag in tags:
            hours=[]
            for day in days:
                hours.append(get_time(day, tag))
            rest=restrict(days,hours, 7)
            print(f"{tag}: Daily Avg (hours): {sum(hours)/len(hours)},"+f"this week: {sum(rest)/len(rest)} hours")
        return reference


MSSH_COMMS={
    "setr":MSSH.c_setr,
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
    "end":MSSH.c_end,
    "plot":MSSH.c_plot_stats,
    "plotw":MSSH.c_plot_week,
    "note":MSSH.c_note,
    "todo":MSSH.c_todo,
    "deln":MSSH.c_del_note,
    "stats":MSSH.c_stats
}


class ChronoClient:

    def c_quit(self, project:ChronoProject, reference:str)->str:
        """Quits Chrono."""
        print("quitting")
        return reference

    def c_commands(self, project:ChronoProject, reference:str)->str:
        """Prints all commands."""
        print(self.command_set.keys())
        return reference

    def c_refresh(self, project:ChronoProject, reference:str)->str:
        """Saves and rebuilds the project."""
        project.save()
        self.build_ChronoProject()
        project.load_settings()
        return reference

    def c_restore(self, project:ChronoProject, reference:str, code:str=0)->str:
        """Restores a project from a backup."""
        if code==project.settings["code"]:
            tmp=project.path
            if os.path.isfile("backup.json"):
                self.build_ChronoProject(path="backup")
                self.project.path=tmp
            else:
                print("no backup available")
        return reference

    def c_help(self, project:ChronoProject, reference:str, cmd:str)->str:
        """Describes a given var:cmd."""
        if cmd in self.command_set.keys():
            sig=signature(self.command_set[cmd])
            if not len(sig.parameters.keys())==2:
                sig=str(sig).replace("(project: chrono_client.ChronoProject, reference: str", "")\
                    .replace(") -> str", "").replace("(p, r", "").replace(")", "")
                print(sig[2:])
            else:
                print(f"{cmd} takes no arguments")
            if (cmd.replace("mk", "") in self.project.settings["mk_shortcuts"].keys()):
                print(self.project.settings["mk_shortcuts"][cmd.replace("mk", "")][2])
            else: print(self.command_set[cmd].__doc__)
        else:
            logging.info(f"unknown command : {cmd}")
            print(f"unknown command : {cmd}")
        return reference

    def c_save(self, project:ChronoProject, reference:str)->str:
        """Saves the project."""
        shutil.copy(project.path+".json", project.path+"_backup.json")
        project.save()
        return reference

    def add_commands(self)->None:
        self.command_set["quit"]=self.c_quit
        self.command_set["commands"]=self.c_commands
        self.command_set["restore"]=self.c_restore
        self.command_set["refresh"]=self.c_refresh
        self.command_set["help"]=self.c_help
        self.command_set["save"]=self.c_save
        for key in self.project.settings["mk_shortcuts"].keys():
            nk="mk"+key
            self.command_set[nk]=lambda p,r,start,stop,what=self.project.settings["mk_shortcuts"][key][0],tags=self.project.settings["mk_shortcuts"][key][1]: self.command_set["mkEvent"](p,r,what,tags,start,stop)

    def __init__(self, path:str, command_set:Dict[str, Callable[[List[str]], None]]={}):
        self.path=path
        self.project=None
        self.command_set=command_set
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
        for note in d["todo"]:
            p.todo.append(ChronoNote(note["text"], datetime.fromisoformat(note["datetime"])))
        for day in d["days"].values():
            events=[ChronoEvent(start=event["start"], end=event["end"], what=event["what"], tags=event["tags"]) for event in day["events"]]
            sevents=[ChronoTime(start=event["start"], what=event["what"], tags=event["tags"]) for event in day["sevents"]]
            p.add_day(ChronoDay(events=events, input_date=day["date"], day_start=day["day_start"], day_end=day["day_end"]))
            for time in sevents:
                p.days[day["date"]].add_silent(time)
        self.project=p
        self.add_commands()

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
        return [("Stunden Mathe", round(mathe, ndigits=3)),
                ("Stunden Vorlesung", round(vorlesung, ndigits=3)),
                ("Stunden Mathe (nicht Vorlesung)", round(nvorlesung, ndigits=3)),
                ("Stunden Leben", round(leben, ndigits=3))]

def get_time(day:ChronoDay, tag:str)->float:
    return sum([((datetime.combine(date.today(), event.end)\
                     - datetime.combine(date.today(), event.start))\
                .seconds/3600)*(tag in event.tags) for event in day.events])

def get_intersect_sum(day:ChronoDay, tags:List[str])->float:
    overhead=0
    for event in day.events:
        if not (I:=get_intersect(tags, event.tags))==[]:
            overhead += ((datetime.combine(date.today(), event.end)\
                - datetime.combine(date.today(), event.start))\
        .seconds/3600)*(len(I)-1)
    return overhead

def restrict(days:List[ChronoDay], coupling:List[float], width:int)->List[ChronoDay]:
    tmp = date.today()
    rtn=[]
    for i, day in enumerate(days):
        if (tmp-day.date).days<=width:
            rtn.append(coupling[i])
    return rtn
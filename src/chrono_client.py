import json
import logging
import os
import shutil
import subprocess
from datetime import (date, datetime, time, timedelta)
from functools import reduce
from inspect import signature
from typing import (Callable, Dict, List, Tuple, Union, Set, Optional)

import matplotlib.pyplot as plt

from src.helper import (get_color, get_intersect, list_to_string, seconds_to_time, split_command,
                    write_table,get_seconds, time_from_str, date_from_str, get_tf_length, 
                    WEEKDAYS, MSSH_color_scheme, sleepdata_to_time, cursed_get_lambda, what_or_none, 
                    concatsem, get_pace_ticks)

from src.sport import (ChronoPlankEvent, ChronoRunningEvent, ChronoSitUpsEvent, 
                   ChronoPushUpEvent, ChronoSportEvent)

from src.atoms import (ChronoEvent, ChronoTime, ChronoNote)

from src.oura import get_sleep

VERSION="1.0.0"

class ChronoDay:
    """This class is used to organize ChronoEvent- and  ChronoTimes-objects. 
    Each page in the exported pdf should correspond to one ChronoDay-object."""
     
    events:List[ChronoEvent]
    date:date
    silent_events:List[ChronoTime]
    sport:Dict[str, List[ChronoSportEvent]]
    sleep:Tuple[time]


    def __init__(self, events:List[ChronoEvent], input_date:str):
        """Constructor: ChronoDay.
        input_date will be converted to a date object and
        events will be saved as is. 
        Attributes:
            events: A list of ChronoEvents. 
            input_date: The date of the Day. Should be of the format YYYY-MM-DD"""
        self.events=events
        self.date=date_from_str(input_date)
        self.silent_events=[]
        self.sport={"runs":[],"pushups":[],"planks":[],"situps":[]}
        self.sleep=()

    def __repr__(self)->str:
        """Returns a string representation of this object. Used by the command today"""
        if self.events == []:
            return  f"{self.date.__str__()}:\n\n"
        else: return f"{self.date.__str__()}:\n" + reduce(lambda a,b: a+"\n\n"+b, [event.__repr__() for event in sorted(self.events, key=lambda x: x.start)])

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
        else: raise Exception("Overlap")

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
        for e1 in self.events:
            for e2 in self.events:
                if not e1==e2 and e1.end==e2.start and e1.what==e2.what:
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
        if self.sleep==(): d["sleep"]=[]
        else: d["sleep"]=[str(self.sleep[0]),str(self.sleep[1]),self.sleep[2]]
        return d

    def add_run(self, run:ChronoRunningEvent)->None:
        """Adds a run event to the "runs" list."""
        self.sport["runs"].append(run)

    def add_situp(self, sit:ChronoSitUpsEvent)->None:
        """Adds a situp event to the "situp" list."""
        self.sport["situps"].append(sit)

    def add_pushup(self, pu:ChronoPushUpEvent)->None:
        """Adds a pushup event to the "pushup" list."""
        self.sport["pushups"].append(pu)

    def add_plank(self, plank:ChronoPlankEvent)->None:
        """Adds a plank event to the "plank" list."""
        self.sport["planks"].append(plank)

    def get_sleep(self)->time:
        """Returns a time object representing the sleep attribute."""
        return sleepdata_to_time(self.sleep)

class ChronoSchedule:
    
    days:List[List[List[ChronoEvent]]]

    def __init__(self, path:str):
        """Constructor of ChronoSchedule."""
        with open("data/"+path, "r+", encoding="utf-8") as f:
            data=json.load(f)
        self.days=[[[] for _ in range(7)] for i in range(len(data))]
        for i,week in enumerate(data):
            for j  in range(7):
                self.days[i][j]=[ChronoEvent(e["start"], e["end"], e["what"], e["tags"]) for e in week[j]]


class ChronoProject:

    path:str
    name:str
    todo:List[ChronoNote]
    days:Dict[str, ChronoDay]
    sevents:List[ChronoTime]
    schedule:ChronoSchedule
    schedulemod:int
    scheme:Dict[str, str]
    day_zero_sleep:Tuple[time,time,bool]
    forbidden:List[str]

    def __init__(self, name:str, path:str):
        """Constructor of ChronoProject."""
        self.name=name
        self.path=path
        self.days=dict()
        self.schedule=None
        self.todo=[]
        self.header=["\\documentclass{article}"]
        self.scheme=MSSH_color_scheme
        self.load_settings()
        self.day_zero_sleep=()
        self.forbidden=["sleep"]

    def set_schedule(self,schedule:ChronoSchedule)->None:
        """Sets the schedule for this project."""
        self.schedule=schedule
        if schedule==None: self.schedulemod=0
        else: self.schedulemod=len(self.schedule.days)        

    def load_settings(self)->None:
        """ Loads settings from "settings.json"."""
        with open("data/settings.json", "r+", encoding="utf-8") as f:
            self.settings=json.load(f)
        self.scheme=self.settings["color_scheme"]

    def set_alias(self, cmds:Dict[str,Callable])->None:
        """Creates the alias Dict. Needs load_settings to be called first"""
        self.alias={key:cursed_get_lambda(self.settings["alias"][key], cmds) for key in self.settings["alias"].keys()}

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
                day.events += self.schedule.days[int(day.date.isocalendar()[1])%self.schedulemod][day.date.weekday()]
            self.days[day.date.isoformat()]=day
        else:
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
            f.write("\\section*{"+"ToDo:"+"}\n")
            if not self.todo==[]:
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
            json.dump(export, f)

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

    def analysis_get_between(self, start_date:str,end_date:str)->List[ChronoDay]:
        """Returns a sorted sublist of self.days."""
        ds=[day.date for day in self.days.values()]
        if start_date=="start": start_date=min(ds)
        else: start_date=date_from_str(start_date)
        if end_date=="stop": end_date=max(ds)
        else: end_date=date_from_str(end_date)
        return list(sorted(self.analysis_get(lambda x: start_date<=x.date<=end_date), key=lambda x: x.date))

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
            raise Exception("start can't be the same as end")
        if reference in project.days.keys():
            try:
                if time_from_str(start) <= time_from_str(end):
                    project.add_event(ChronoEvent(start=start, end=end, what=what, tags=tags.split(",")), reference, force=int(force))
                else:
                    next_day=date_from_str(reference)+timedelta(days=1)
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
    def c_create_time(project:ChronoProject, reference:str, what:str, tags:str,start:str,idate:str="ref")->str:
        """Creates a ChronoTime given:"""
        if idate=="ref": idate=reference
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
        else:
            print("no plan for today")
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
    def c_times(project:ChronoProject, reference:str, days:str="1")->str:
        """Prints the ChronoTimes of the next var:days days."""
        d=date.today()
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
    def c_plot_stats(project:ChronoProject, reference:str, tags:str="mathe,programming", start_date:str="start", end_date:str="stop")->str:
        """Plots the hours of var:tags and their sum."""

        #preperation
        tags=tags.split(",")
        assert not "sum" in tags
        days = project.analysis_get_between(start_date, end_date)
        n=len(days)
        xs=[i for i in range(n)]
        ys={tag:[] for tag in tags}


        #sleep preperation
        if "sleep" in tags:
            if project.day_zero_sleep==():
                ys["sleep"].append(0)
            else:
                sleep=project.day_zero_sleep
                ys["sleep"].append(get_seconds(sleepdata_to_time(sleep))/3600)
        

        #populate ys
        for day in days:
            for tag in tags:
                if not tag in project.forbidden:
                    ys[tag].append(get_time(day, tag))
                elif tag=="sleep":
                    if not day.sleep==():
                        ys["sleep"].append(get_seconds(day.get_sleep())/3600)
                    else:
                        ys["sleep"].append(0)
        

        if "sleep" in tags: 
            ys["sleep"]=ys["sleep"][:-1]

        #Calculate overhead (sum)
        corr=[0 for _ in days]
        for i in range(n):
            for event in days[i].events:
                if not (I:=get_intersect(tags, event.tags))==[]:
                    corr[i] += ((datetime.combine(date.today(), event.end)\
                     - datetime.combine(date.today(), event.start))\
                .seconds/3600)*(len(I)-1) 
        

        ys["sum"]=[sum([ys[tag][i] for tag in tags if not tag=="sleep"])-corr[i] for i in range(n)]
        
        #plot tags+sum
        ax=plt.subplot(111)
        box = ax.get_position()
        ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        for tag in ys.keys():
            plt.plot(xs, ys[tag], label=tag)

        #Calculate and plot weekday average
        if not days == []: 
            zeroday=days[0].date.weekday()
            WDA=[sum(wds:=[ys["sum"][i] for i in range(n) if (i+zeroday)%7==wd])/max(len(wds),1) for wd in range(7)] 
            plt.plot(xs,[WDA[day.date.weekday()] for day in days],"--",label="wda")
        
        #Mark "reference" with a *
        if reference in [day.date for day in days]:
            d=-1
            tmp=date_from_str(reference)
            for i in range(len(days)):
                if days[i].date==tmp:
                    d=i
            try: plt.scatter([d], ys["sum"][d], label="Today", marker="*", color="red", s=[70])
            except:
                logging.warn("Some days are missing.")
                print("Some days are missing.")
        
        #visuals
        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        plt.xlabel("Days")
        plt.ylabel("Hours")
        plt.show()
        return reference

    @staticmethod
    def c_plot_week(project:ChronoProject, reference:str, tags:str="mathe,programming,korean",k:str="7",start_date:str="start", end_date:str="stop")->str:
        """Plots the hours of var:tags and their sum. over the last var:k days"""
        #prep.
        k=int(k)
        tags=tags.split(",")
        assert not "sum" in tags
        ds=[day.date for day in project.days.values()]
        if start_date=="start": start_date=min(ds)
        else: start_date=date_from_str(start_date)
        if end_date=="stop": end_date=max(ds)
        else: end_date=date_from_str(end_date)
        assert (end_date-start_date).days>=k
        days=project.analysis_get_between(start_date, end_date)
        n=len(days)
        xs=[i for i in range(n)]
        ys={tag:[] for tag in tags}
        days = list(sorted(project.days.values(), key=lambda x: x.date))

        #sleep prep.
        if "sleep" in tags:
            if project.day_zero_sleep==():
                ys["sleep"].append(0)
            else:
                sleep=project.day_zero_sleep
                ys["sleep"].append(get_seconds(sleepdata_to_time(sleep))/3600)
        
        #populate ys
        for day in days:
            for tag in tags:
                if not tag=="sleep":
                    ys[tag].append(get_time(day, tag))
                elif project.settings["oura"]:
                    if not day.sleep == ():
                        ys["sleep"].append(get_seconds(day.get_sleep())/3600)
                    else:
                        ys["sleep"].append(0)
        
        if "sleep" in tags: ys["sleep"]=ys["sleep"][:-1]
        
        #Calculate overhead (sum)
        corr=[0 for _ in days]
        for i in range(n):
            corr[i]=get_intersect_sum(days[i], tags)
        
        ys["sum"]=[sum([ys[tag][i] for tag in tags if not tag=="sleep"])-corr[i] for i in range(n)]
        
        ax=plt.subplot(111)
        box = ax.get_position()
        ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        
        #prep. week splice
        tmp = min(date_from_str(reference),end_date)
        d=(tmp-start_date).days
        week_splice=lambda x : x[d-k:d+1]

        #plot filtered ys
        for tag in ys.keys():
            try: plt.plot(week_splice(xs), week_splice(ys[tag]), label=tag)
            except:
                logging.warn(tag)
                logging.warn(week_splice(xs), week_splice(ys[tag]))

        #Calculate and plot weekday average
        if not days == []: 
            zeroday=days[0].date.weekday()
            WDA=[sum(wds:=[ys["sum"][i] for i in range(n) if (i+zeroday)%7==wd])/max(len(wds),1) for wd in range(7)] 
            plt.plot(week_splice(xs),week_splice([WDA[day.date.weekday()] for day in days]),"--",label="wda")
        
        #Mark "reference" with a *
        if tmp.isoformat() in project.days.keys():
            try: plt.scatter([d], ys["sum"][d], label="Today", marker="*", color="red", s=[70])
            except:
                logging.warn("Some days are missing.")
                print("Some days are missing.")
        
        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        plt.xticks(week_splice(xs), week_splice([WEEKDAYS[day.date.weekday()][0:3]+"." for day in days]))
        plt.xlabel("Days")
        plt.ylabel("Hours")
        plt.show()
        return reference

    @staticmethod
    def c_note(project:ChronoProject, reference:str, text:str, *texts:Tuple[str])->str:
        """Adds a note to the todo list."""
        project.add_note(ChronoNote(reduce(lambda a,b:a+" "+b, [text]+list(texts))))
        return reference

    @staticmethod
    def c_todo(project:ChronoProject, reference:str)->str:
        """Prints all saved notes."""
        print("Notes:")
        for i, note in enumerate(project.todo):
            print(str(i+1)+".: "+str(note))
        return reference

    @staticmethod
    def c_del_note(project:ChronoProject, reference:str, text:str,*texts:Tuple[str])->str:
        """Deletes the ChronoNote with the text var:text."""
        text=reduce(lambda a,b:a+" "+b, [text]+list(texts))
        project.todo=list(filter(lambda x: not x.text==text , project.todo))
        return reference

    @staticmethod
    def c_stats(project:ChronoProject, reference:str, tags:str, start_date:str="start", end_date:str="stop")->str:
        """Displays stats for given tags."""
        tags=tags.split(",")
        hours=[]
        days=project.analysis_get_between(start_date, end_date)
        for tag in tags:
            hours=[]
            for day in days:
                hours.append(get_time(day, tag))
            rest=restrict(days,hours, 7)
            print(f"{tag}: Daily Avg (hours): {sum(hours)/len(hours)},"+f"this week: {sum(rest)/len(rest)} hours")
        return reference

    @staticmethod
    def c_add_run(project:ChronoProject, reference:str, start_time:str, run_time:str, distance:str)->str:
        """Adds a ChronoRunEvent based on:"""
        runtimei=int(run_time[0:2])*60+int(run_time[3:5])
        project.days[reference].add_run(ChronoRunningEvent(runtimei,float(distance),time(int(start_time[0:2]), int(start_time[3:]))))
        return reference

    @staticmethod
    def c_add_situp(project:ChronoProject, reference:str, start_time:str, situp_time:str, mult:str)->str:
        """Adds a ChronoSitUpsEvent based on:"""
        situp_timef=float(situp_time[0:2])*60+float(situp_time[3:5])
        project.days[reference].add_situp(ChronoSitUpsEvent(situp_timef,int(mult),time(int(start_time[0:2]), int(start_time[3:]))))
        return reference

    @staticmethod
    def c_add_plank(project:ChronoProject, reference:str, start_time:str, p_time:str)->str:
        """Adds a ChronoPlankEvent based on:"""
        p_timef=float(p_time[0:2])*60+float(p_time[3:5])
        project.days[reference].add_plank(ChronoPlankEvent(p_timef,time(int(start_time[0:2]), int(start_time[3:]))))
        return reference

    @staticmethod
    def c_add_pushup(project:ChronoProject, reference:str, start_time:str, times:str, mults:str)->str:
        """Adds a ChronoPushUpEvent based on:"""
        timesfl=[float(time[0:2])*60+float(time[3:5]) for time in times.split(",")]
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
    def c_heatmap(project:ChronoProject, reference:str, tag:str, yt:str, start_date:str="start", end_date:str="stop")->str:
        """Draws a heat map for a specific var:tag with var:yt vertical labels with data from 
        [var:start_date,var:end_date]."""
        yt=int(yt)
        c=24*60*60
        days=project.analysis_get_between(start_date,end_date) 
        poi=list(project.get_poi())
        poi.sort()
        timeframes=[(poi[i],poi[i+1]) for i in range(len(poi)-1)]
        events=list(filter(lambda a: tag in a[0].tags, reduce(lambda a,b: a+b, [[(event,day.date) for event in day.events]for day in days])))
        heatmap=[[sum([1 for event in events if check_in_timeframe(tf, event[0]) and event[1].weekday()==i]) for tf in timeframes for _ in range(get_tf_length(tf))] for i in range(7)]
        heatmap=list(zip(*heatmap))
        plt.imshow(heatmap, cmap="hot",interpolation="nearest", aspect=14/c)
        plt.xticks([i for i in range(7)], map(lambda x: x[:3],WEEKDAYS))
        tfl=len(timeframes)
        min_sec=min([get_seconds(poi[i]) for i in range(tfl)])
        plt.yticks([get_seconds(poi[int(i*(tfl/yt))])-min_sec for i in range(yt+1)], [str(poi[int(i*(tfl/yt))]) for i in range(yt+1)])
        plt.colorbar()
        plt.show()
        return reference

    @staticmethod
    def c_split_project(project:ChronoProject, reference:str, split:str, old_name:str)->str:
        """Splits the project into two. Saves [start_date,split] to var:oldname.json and (split, end_date]
         to project.json."""
        tmp=project.days
        splitdate=date_from_str(split)
        project.days = {key:tmp[key] for key in tmp.keys() if tmp[key].date <=splitdate}
        project.save(path=old_name)
        project.days = {key:tmp[key] for key in tmp.keys() if tmp[key].date >splitdate}
        project.save()
        return reference

    @staticmethod
    def c_oura_sleep(project:ChronoProject, reference:str, start:str, stop:str)->str:
        """Gets your sleep data \in [start-1,stop] from oura is such a connection exists."""
        getzeroday=start=="start"
        ds=[day.date for day in project.days.values()]
        if start=="start": start=(min(ds)+timedelta(days=-1)).isoformat()
        if stop=="stop": stop=max(ds).isoformat()
        if project.settings["oura"]:
            sleepdata=get_sleep(start_date=start,stop_date=stop,code=project.settings["oura_key"])
            if sleepdata[0]:
                keys=project.days.keys()
                for key in sleepdata[1].keys():
                    if key in keys:
                        ss=time_from_str(sleepdata[1][key][0])
                        se=time_from_str(sleepdata[1][key][1])
                        project.days[key].sleep=(ss,se,sleepdata[1][key][2])
            if getzeroday:
                ss=time_from_str(sleepdata[1][start][0])
                se=time_from_str(sleepdata[1][start][1])
                project.day_zero_sleep=(ss,se,sleepdata[1][start][2])
        else:
            print("No oura is linked: Check your settings")
            logging.warn("No oura is linked: Check your settings")   
        return reference 

    @staticmethod
    def c_get_sleep(project:ChronoProject, reference:str, sdate:str)->str:
        """Prints the sleep data from a specific var:sdate."""
        if sdate in project.days.keys():
            print(f"Sleep: {list(map(lambda x: x.isoformat(), project.days[sdate].sleep[0:2]))}: {project.days[sdate].sleep[2]} => {project.days[sdate].get_sleep().isoformat()}")
        return reference

    @staticmethod
    def c_set_sleep(project:ChronoProject, reference:str, sdate:str, start:str, stop:str,sameday:str="1")->str:
        """Sets the sleep for var:sdate to (var:start, var:stop, var:sameday)."""
        if sdate in project.days.keys():
            project.days[sdate].sleep=(time_from_str(start),time_from_str(stop),sameday)
        return reference
    
    @staticmethod
    def c_last_night_sleep(project:ChronoProject, reference:str)->str:
        """Gets the sleep of the day before the reference"""
        yesterday=(date_from_str(reference)+timedelta(days=-1)).isoformat()
        MSSH.c_get_sleep(project, reference, yesterday)
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
        """Plots the distance run each day in between [start_date, end_date]."""
        days = project.analysis_get_between(start_date, end_date)
        n=len(days)
        xs=[]
        ys=[]#distance  
        ysp=[]#pace

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
        ax1.legend()
        ax2.legend()
        plt.show()  
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
        but does not populate them based on the schedule!"""
        days = project.analysis_get_between(start_date, end_date)
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
        """Exports your sports data  in between [start_date, end_date] to data/sport.json."""
        sport=dict()
        days = project.analysis_get_between(start_date, end_date)
        for day in days:
            if not list(day.sport.values()) == [[],[],[],[]]:
                sport[day.date.isoformat()] = {key:[entry.to_dict() for entry in day.sport[key]] for key in day.sport.keys()}
        with open("data/sport.json","w+") as f:
            json.dump(sport,f)
        return reference

    @staticmethod
    def c_exportweek(project:ChronoProject, reference:str,end_date:str="stop")->str:
        """ Exports 7 days ending on var:end_date to a LaTeX -> PDF file and opens the file."""
        days=project.analysis_get_between("start", end_date)[-7:]
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
        subprocess.Popen([project.settings["pdfpath"],"weekexport.pdf"], shell=True)
        return reference

    @staticmethod
    def c_to_csv(project:ChronoProject, reference:str,name:str,start_date:str="start",end_date:str="stop")->str:
        """Exports the events of this project to a csv file."""
        days=project.analysis_get_between(start_date, end_date)
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
    def c_runsum(project:ChronoProject, reference:str,k:str="6")->str:
        """Displays a short analysis of all runs which happend up to var:k days before var:reference."""
        if reference in project.days.keys():
            start=date_from_str(reference)
            end=start-timedelta(days=int(k))
            runs=sum([day.sport["runs"] for day in project.analysis_get_between(end.isoformat(),reference)], [])
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
        self.build_ChronoProject()
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
        if cmd in project.alias.keys():
            print("calls : "+self.project.settings["alias"][cmd])
        elif cmd in self.command_set.keys():
            sig=signature(self.command_set[cmd])
            print(self.command_set[cmd].__doc__)
            if not len(sig.parameters.keys())==2:
                sig=str(sig).replace("(project: src.chrono_client.ChronoProject, reference: str", "")\
                    .replace(") -> str", "").replace("(p, r", "").replace(")", "")
                print(sig[2:])
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
        """var:f(var:var:fargs+args)"""
        if f in self.command_set.keys():
            argsl=args.split(",")
            aargs=list(fargs)+argsl
            return self.command_set[f](project,reference,*aargs)
        else:
            logging.warn(f"Can't find f: {f}")
            print(f"Can't find f: {f}") 
            return reference

    def c_ihof(self, project:ChronoProject, reference:str,args:str,i:str,f:str,*fargs:str)->str:
        """var:f(var:fargs[0:i]+var:args+var:fargs[i:]) """
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
        subprocess.Popen(["start","data/settings.json"], shell=True)
        return self.c_refresh(project,reference)

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

    def __init__(self, path:str,s:ChronoSchedule,command_set:Dict[str, Callable[[Union[List[str],ChronoProject],str], None]]={}):
        self.path=path
        self.project=None
        self.command_set=command_set
        logging.basicConfig(filename="data/log.txt", level=logging.INFO)
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
                last_command=ip[0]
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
                    logging.info(msg=f"failed command: {ip}")
                    print("This command does not exist")
        logging.shutdown()

    def build_ChronoProject(self, s:ChronoSchedule=None, path:Optional[str]=None)->None:
        """ Builds a ChronoProject from a given path. """
        if path == None: path=self.path
        with open("data/"+path+".json", "r+", encoding="utf-8") as f:
            d=json.load(f)
        p=ChronoProject(name=d["name"], path=d["path"])
        if not s==None: p.set_schedule(s)
        for note in d["todo"]:
            p.todo.append(ChronoNote(note["text"], datetime.fromisoformat(note["datetime"])))
        for day in d["days"].values():
            events=[ChronoEvent(start=event["start"], end=event["end"], what=event["what"], tags=event["tags"]) for event in day["events"]]
            sport={sport:day["sport"][sport] for sport in day["sport"].keys()}
            p.add_day(ChronoDay(events=events, input_date=day["date"]))
            for run in sport["runs"]:
                p.days[day["date"]].add_run(ChronoRunningEvent(run["time"],run["distance"],time_from_str(run["start_time"])))
            for situp in sport["situps"]:
                p.days[day["date"]].add_situp(ChronoSitUpsEvent(situp["time"],situp["mult"],time_from_str(situp["start_time"])))
            for plank in sport["planks"]:
                p.days[day["date"]].add_plank(ChronoPlankEvent(plank["time"],time_from_str(plank["start_time"])))
            for pushup in sport["pushups"]:
                p.days[day["date"]].add_pushup(ChronoPushUpEvent(pushup["times"],pushup["mults"],time_from_str(pushup["start_time"])))
            if not "sleep" in day.keys(): p.days[day["date"]].sleep=()
            elif day["sleep"]==[]: p.days[day["date"]].sleep=()
            else: p.days[day["date"]].sleep=(time_from_str(day["sleep"][0]),time_from_str(day["sleep"][1]),day["sleep"][2])
        self.project=p
        self.project.sevents=[ChronoTime(sevent["tdate"], start=sevent["start"], what=sevent["what"], tags=sevent["tags"]) for sevent in d["sevents"]]
        self.add_commands()
        self.project.set_alias(self.command_set)

    def __repr__(self)->str:
        return self.project.__repr__()


def get_time(day:ChronoDay, tag:str)->float:
    """
    Returns the amount of seconds a certain activity associated with the tag has been done on a given day. 
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

from typing import (Dict, List, Union)
from datetime import (time, datetime,date)
from src.helper import (time_from_str)

class ChronoTime:
    """ This class should be used for very short events, such as deadlines."""

    start:time
    what:str
    tags:List[str]
    tdate:date

    def __init__(self, tdate:str, start:str, what:str, tags:List[str]=[]):
        """Constructor: ChronoTime. start input will be converted to a time object, 
        the other inputs will be used as attributes. 
        Attributes:
            start: Should be of the form HH:MM
            what: Should be a reasonably short string
            tags: Should be a list of tags, seperated by "," given as a single string"""
        self.tdate=date(int(tdate[0:4]),int(tdate[5:7]),int(tdate[8:10]))
        self.start=time_from_str(start)
        self.what=what
        self.tags=tags

    def to_dict(self)->Dict[str, Union[str, List[str]]]:
        """Used to save the object as a json."""
        d:Dict[str, Union[str, List[str]]]=dict()
        d["tdate"]=self.tdate.isoformat() #YYYY-MM-DD
        d["start"]=self.start.isoformat() #HH:MM:SS
        d["what"]=self.what
        d["tags"]=self.tags
        return d

    def __repr__(self)->str:
        """Returns a string representation of this object. Used by the command times"""
        return f"Date: {self.tdate}, time: {self.start}, what: {self.what}"


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
        
        self.start=time_from_str(start)
        self.end=time_from_str(end)
        self.what=what
        self.tags=[]
        for tag in tags:
            if tag=="":
                print("Empty tags are not allowed, this tag was ignored.")
            elif tag[0]=="&":
                print("Tags can not start with a &, this tag was ignored: "+tag)
            else:
                self.tags.append(tag)
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
from datetime import time
from typing import (Dict, List,Union)

class ChronoSportEvent:

    def to_dict(self):
        pass

class ChronoRunningEvent(ChronoSportEvent):

    def __init__(self, run_time:int, distance:float, start_time:time):
        self.time=run_time
        self.distance=distance
        self.start_time=start_time

    def __repr__(self)->str:
        return f"[start_time:{self.start_time}, time:{self.time}, distance:{self.distance}]"

    def to_dict(self)->Dict[str, Union[float,str]]:
        iso=self.start_time.isoformat()
        return {"time":self.time,"distance":self.distance,"start_time":iso[0:2]+":"+iso[3:5]}

class ChronoPushUpEvent(ChronoSportEvent):
   
    def __init__(self, p_times:List[float], p_mults:List[int], start_time:time):
        self.times=p_times #how long
        self.mults=p_mults #how many
        self.start_time=start_time #when

    def __repr__(self)->str:
        return f"times:{self.times}, mults:{self.mults},start_time:{self.start_time}"

    def to_dict(self)->Dict[str, Union[List[float],List[int],str]]:
        iso=self.start_time.isoformat()
        return {"times":self.times,"mults":self.mults,"start_time":iso[0:2]+":"+iso[3:5]}

class ChronoSitUpsEvent(ChronoSportEvent):

    def __init__(self, p_times:float, mult:int, start_time:time):
        self.time=p_times #how long
        self.mult=mult #how many
        self.start_time=start_time #when

    def __repr__(self)->str:
        return f"time:{self.time}, mult:{self.mult},start_time:{self.start_time}"

    def to_dict(self)->Dict[str, Union[float,int,str]]:
        iso=self.start_time.isoformat()
        return {"time":self.time,"mult":self.mult,"start_time":iso[0:2]+":"+iso[3:5]}

class ChronoPlankEvent(ChronoSportEvent):

    def __init__(self, times:float, start_time:time):
        self.time=times #how long
        self.start_time=start_time #when

    def __repr__(self)->str:
        return f"time:{self.time},start_time:{self.start_time}"

    def to_dict(self)->Dict[str, Union[float,str]]:
        iso=self.start_time.isoformat()
        return {"time":self.time,"start_time":iso[0:2]+":"+iso[3:5]}
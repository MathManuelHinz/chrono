import requests
import json
from typing import (Tuple,Dict,Union,List)
from requests.models import Response


def get_sleep(start_date:str,stop_date:str,code:str="")->Tuple[bool,Dict[str,List[str]]]:
    print(start_date,stop_date)
    response:Response=requests.get(f"https://api.ouraring.com/v1/sleep?start={start_date}&end={stop_date}&access_token={code}")
    if response.status_code==200:
        sleep=json.loads(response.content.decode(encoding="utf-8"))["sleep"]
        return (True, {day["summary_date"]:[day["bedtime_start"][11:-6],day["bedtime_end"][11:-6]] for day in sleep}) 
    else: return (False,{})

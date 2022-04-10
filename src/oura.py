import requests
import json
from typing import (Tuple,Dict)
from requests.models import Response


def get_sleep(start_date:str,stop_date:str,code:str="")->Tuple[bool,Dict[str,Tuple[str,str,str,str]]]:
    print(f"Getting sleep data from: [{start_date},{stop_date}]")
    print("Awaiting response ...")
    response:Response=requests.get(f"https://api.ouraring.com/v1/sleep?start={start_date}&end={stop_date}&access_token={code}")
    if response.status_code==200:
        sleep=json.loads(response.content.decode(encoding="utf-8"))["sleep"]
        return (True, {day["summary_date"]:(day["bedtime_start"][11:-6],day["bedtime_end"][11:-6],day["bedtime_start"][:10],day["bedtime_end"][:10]) for day in sleep}) 
    else:
        print("Failed") 
        return (False,{})

import requests
import json
from typing import (Tuple,Dict)
from requests.models import Response


def get_sleep(start_date:str,stop_date:str,code:str="")->Tuple[bool,Dict[str,Tuple[str,str,str,str,int,int,int]]]:
    print(f"Getting sleep data: [{start_date},{stop_date}]")
    print("Awaiting response ...")
    url = 'https://api.ouraring.com/v2/usercollection/sleep' 
    params={ 
        'start_date':start_date, 
        'end_date': stop_date 
    }
    headers = { 
    'Authorization': "Bearer "+code
    }
    response = requests.request('GET', url, headers=headers, params=params) 
    if response.status_code==200:
        sleep=sleep=json.loads(response.content.decode(encoding="utf-8"))["data"]
        return (True, {day["day"]:(day["bedtime_start"],day["bedtime_end"],day["sleep_phase_5_min"]) for day in sleep}) 
    else:
        print("Failed") 
        return (False,{})

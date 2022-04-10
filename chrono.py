from src.chrono_client import  (ChronoClient, ChronoSchedule)
from src.commands import MSSH_COMMS


if __name__ == "__main__":
    s=ChronoSchedule("schedule.json")
    c=ChronoClient("project", s, MSSH_COMMS)
    c.run()

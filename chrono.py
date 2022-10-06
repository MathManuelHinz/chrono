from src.chrono_client import  (ChronoClient, ChronoSchedule)
from src.commands import MSSH_COMMS


if __name__ == "__main__":
    s=ChronoSchedule("data/schedule.json")
    c=ChronoClient("data/project", s, MSSH_COMMS)
    c.run()

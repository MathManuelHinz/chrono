from src.chrono_client import  (ChronoClient, ChronoSchedule)
from src.commands import MSSH_COMMS


if __name__ == "__main__":
    s=ChronoSchedule("schedule.json")
    c=ChronoClient("zeitplan", MSSH_COMMS)
    c.build_ChronoProject()
    c.project.set_schedule(s)
    c.run()

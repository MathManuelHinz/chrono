from chrono_client import ChronoDay, ChronoEvent,ChronoProject, ChronoClient, MSSH_COMMS, ChronoSchedule
if __name__ == "__main__":
    s=ChronoSchedule("schedule.json")
    c=ChronoClient("zeitplan", MSSH_COMMS)
    c.build_ChronoProject()
    c.project.set_schedule(s)
    c.run()

from infrastructure.scheduler import Scheduler
s = Scheduler()
try:
    s.tick()
except Exception as e:
    print(f"Error: {e}")

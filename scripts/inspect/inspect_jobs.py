import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.scheduler import SchedulerService

if __name__ == '__main__':
    scheduler = SchedulerService.get_scheduler()
    jobs = scheduler.get_jobs()
    for j in jobs:
        print(j.id, j.next_run_time, j.trigger)

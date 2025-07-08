from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Generator, List, Optional

from ..utils.clock import utc_now


TASK_TIMEOUT = timedelta(seconds = 15) # how long to wait for an update before removing task tracker

@dataclass
class Task:
    name: str
    start_time: datetime
    expiration: datetime

class StatusTracker:
    tasks: Dict[str, Task] = {}

    def track(self, name) -> None:
        self.tasks[name].expiration = utc_now() + TASK_TIMEOUT

    def complete(self, name) -> None:
        if name in self.tasks:
            del self.tasks[name]


    def get(self) -> Generator[Task, None, None]:
        for name, t in self.tasks.items():
            if utc_now() > t.expiration:
                del self.tasks[name]
            else:
                yield t




    @contextmanager
    def tracking(self, name: str):
        self.track(name)
        try:
            yield
        finally:
            self.complete(name)

















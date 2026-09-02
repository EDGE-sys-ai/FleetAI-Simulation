import heapq
from dataclasses import dataclass, field
from typing import Callable, Any, List
import time


@dataclass(order=True)
class ScheduledTask:
    execute_time: float
    task_id: int = field(compare=False)
    callback: Callable = field(compare=False)
    args: tuple = field(default_factory=tuple, compare=False)
    kwargs: dict = field(default_factory=dict, compare=False)
    recurring: bool = field(default=False, compare=False)
    interval: float = field(default=0.0, compare=False)


class Scheduler:
    def __init__(self):
        self._queue: List[ScheduledTask] = []
        self._task_counter = 0
        self._current_time = 0.0

    @property
    def current_time(self) -> float:
        return self._current_time

    def schedule(self, delay: float, callback: Callable, *args, **kwargs) -> int:
        self._task_counter += 1
        task = ScheduledTask(
            execute_time=self._current_time + delay,
            task_id=self._task_counter,
            callback=callback,
            args=args,
            kwargs=kwargs,
        )
        heapq.heappush(self._queue, task)
        return self._task_counter

    def schedule_recurring(self, interval: float, callback: Callable, *args, **kwargs) -> int:
        self._task_counter += 1
        task = ScheduledTask(
            execute_time=self._current_time + interval,
            task_id=self._task_counter,
            callback=callback,
            args=args,
            kwargs=kwargs,
            recurring=True,
            interval=interval,
        )
        heapq.heappush(self._queue, task)
        return self._task_counter

    def cancel(self, task_id: int) -> bool:
        for i, task in enumerate(self._queue):
            if task.task_id == task_id:
                self._queue.pop(i)
                heapq.heapify(self._queue)
                return True
        return False

    def update(self, dt: float) -> int:
        self._current_time += dt
        executed = 0
        while self._queue and self._queue[0].execute_time <= self._current_time:
            task = heapq.heappop(self._queue)
            try:
                task.callback(*task.args, **task.kwargs)
                executed += 1
            except Exception as e:
                print(f"Scheduler task error: {e}")
            if task.recurring:
                task.execute_time = self._current_time + task.interval
                heapq.heappush(self._queue, task)
        return executed

    def get_pending_count(self) -> int:
        return len(self._queue)

    def clear(self) -> None:
        self._queue.clear()
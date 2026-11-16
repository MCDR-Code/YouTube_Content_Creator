"""Runs one weekly step at a time in the background for the web app's Run page.

The page starts a step, then polls /run/status to show progress lines and the final result.
Only one step runs at a time, so two clicks can never start two weekly runs at once.
"""
from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field

from ycc import approval, run_week
from ycc.prune import PruneBlocked

STEPS = {
    "prepare": ("Plan and produce this week", run_week.prepare),
    "revise": ("Revise with my change requests", run_week.revise),
    "publish": ("Publish approved videos (private)", run_week.publish),
    "review": ("Close the week", run_week.review),
}


@dataclass
class Job:
    step: str
    week: int
    started_by: str
    started: float = field(default_factory=time.time)
    lines: list[str] = field(default_factory=list)
    state: str = "running"  # running, done, failed
    result: str = ""
    finished: float | None = None

    def log(self, text: str) -> None:
        for line in str(text).splitlines() or [""]:
            self.lines.append(f"{time.strftime('%H:%M:%S')}  {line}")

    def as_dict(self) -> dict:
        return {"step": self.step, "label": STEPS[self.step][0], "week": self.week, "state": self.state,
                "lines": self.lines[-200:], "result": self.result, "started_by": self.started_by,
                "seconds": round((self.finished or time.time()) - self.started, 1)}


_lock = threading.Lock()
_current: Job | None = None
_history: list[dict] = []


def current() -> dict | None:
    return _current.as_dict() if _current else None


def history() -> list[dict]:
    return list(reversed(_history[-10:]))


def busy() -> bool:
    return _current is not None and _current.state == "running"


def start(step: str, week: int, started_by: str, wait: bool = False) -> Job:
    """Start a step in a background thread. Raises RuntimeError if one is already running."""
    global _current
    if step not in STEPS:
        raise ValueError(f"Unknown step {step}")
    with _lock:
        if busy():
            raise RuntimeError("Another step is still running. Wait for it to finish.")
        job = Job(step=step, week=week, started_by=started_by)
        _current = job
    t = threading.Thread(target=_run, args=(job,), daemon=True)
    t.start()
    if wait:
        t.join()
    return job


def _run(job: Job) -> None:
    fn = STEPS[job.step][1]
    job.log(f"{STEPS[job.step][0]}: week {job.week}, started by {job.started_by}")
    try:
        fn(job.week, log=job.log)
        job.state, job.result = "done", "Finished."
    except PruneBlocked as e:
        job.state, job.result = "failed", f"Stopped cleanly by Prune: {e.code} on {e.agent_id}. Check the Prune dashboard."
    except approval.NotApproved as e:
        job.state, job.result = "failed", f"Upload refused: {e}"
    except Exception as e:  # noqa: BLE001
        job.state, job.result = "failed", f"Error: {e}"
        job.log(traceback.format_exc(limit=3))
    job.finished = time.time()
    job.log(job.result)
    _history.append(job.as_dict())

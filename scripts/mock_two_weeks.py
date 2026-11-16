"""Two full mock weeks, driven entirely through the web app, the way the professor uses it.

It logs in, presses the Run buttons (plan and produce, revise, publish, close the week), and
decides on each video on its video page. In week 1 it also requests a change, revises, and
then approves. Approvals are signed "Scripted test approval" so they are never mistaken for
the professor's. Run:  python scripts/mock_two_weeks.py
"""
import os
import sys
import time
from pathlib import Path

os.environ["YCC_MODE"] = "mock"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ycc.config import load_settings  # noqa: E402

load_settings()  # reads .env
if len(os.getenv("YCC_ADMIN_PASSWORD", "")) < 10:
    os.environ["YCC_ADMIN_PASSWORD"] = "scripted-test-password"  # this process only, never saved

from ycc import approval, jobs  # noqa: E402
from ycc.webapp import app  # noqa: E402

NAME = "Scripted test approval"
c = app.test_client()
r = c.post("/login", data={"name": NAME, "password": os.environ["YCC_ADMIN_PASSWORD"]})
assert r.status_code == 302, "login failed"
with c.session_transaction() as s:
    CSRF = s["csrf"]


def press(step: str, week: int) -> None:
    r = c.post("/run/start", data={"step": step, "week": str(week), "csrf": CSRF})
    assert r.status_code == 302
    shown = 0
    while True:
        job = c.get("/run/status").get_json()["job"]
        for line in job["lines"][shown:]:
            print(line)
        shown = len(job["lines"])
        if job["state"] != "running":
            assert job["state"] == "done", job["result"]
            return
        time.sleep(0.5)


def decide(vid: str, action: str, **extra) -> None:
    v = approval.get(vid)
    data = {"action": action, "csrf": CSRF, "title": v["title"], "description": v["description"],
            "variant": "1" if v["variants"] else "0", "note": "Checked in the scripted test run"}
    if v["variants"]:
        data["title"] = v["variants"][1]["title"]
    data.update(extra)
    assert c.post(f"/video/{vid}/action", data=data).status_code == 302
    print(f"  {vid}: {action} -> {approval.get(vid)['status']}")


for week in (1, 2):
    print(f"\n===== Week {week} =====")
    press("prepare", week)
    if week == 1:
        decide("w01_short3", "changes", changes="Make the hook shorter and add a classroom example.")
        press("revise", 1)
    decide(f"w{week:02d}_long", "approve")
    decide(f"w{week:02d}_short1", "approve")
    decide(f"w{week:02d}_short2", "approve")
    decide(f"w{week:02d}_short3", "reject", note="Too close to Short 2")
    press("publish", week)
    press("review", week)
    print("Statuses:", [(v["id"], v["status"], v["privacy"]) for v in approval.list_week(week)])

assert not jobs.busy()
print("\nDone. Start the web app with Start.cmd (or: python -m ycc.run_week serve) and sign in.")

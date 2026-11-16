"""Prompt 12 check: run two full mock weeks end to end.

Approvals go through the real review page (Flask test client, same form and token as the
professor uses), signed "Scripted test approval" so they are never mistaken for his.
Run:  python scripts/mock_two_weeks.py
"""
import os
import sys
from pathlib import Path

os.environ["YCC_MODE"] = "mock"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ycc import approval, run_week  # noqa: E402
from ycc.webapp import app  # noqa: E402

APPROVER = "Scripted test approval"


def approve_on_page(week: int) -> None:
    c = app.test_client()
    token = app.config["FORM_TOKEN"]
    for v in approval.list_week(week):
        if v["kind"] == "short" and v["id"].endswith("3"):
            c.post(f"/video/{v['id']}/decide", data={"action": "reject", "approver": APPROVER,
                                                    "note": "Too close to Short 2", "token": token})
            continue
        variant = 1 if v["variants"] else 0
        title = v["variants"][variant]["title"] if v["variants"] else v["title"]
        r = c.post(f"/video/{v['id']}/decide", data={
            "action": "approve", "approver": APPROVER, "title": title, "description": v["description"],
            "variant": str(variant), "note": "Checked in the scripted test run", "token": token})
        assert r.status_code == 302, r.data
    r = c.post(f"/week/{week}/publish", data={"token": token})
    assert r.status_code == 302


for week in (1, 2):
    run_week.prepare(week)
    approve_on_page(week)
    print("\nAfter publish:", [(v["id"], v["status"], v["privacy"]) for v in approval.list_week(week)])
    run_week.review(week)

print("\nDone. Open the dashboard with:  python -m ycc.run_week serve")

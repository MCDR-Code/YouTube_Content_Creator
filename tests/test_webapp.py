"""The web app: login, CSRF, the decision buttons, and the Run buttons."""
import time

import pytest

from ycc import approval, jobs, webapp

PW = "correct-horse-battery"


def _video(vid="w01_long", kind="long"):
    return {"id": vid, "week": 1, "kind": kind, "path": "output/week_01/long_video.mp4",
            "thumbnails": ["output/week_01/thumbnail_1.png"],
            "variants": [{"title": "Title A", "thumbnail_text": "A"}, {"title": "Title B", "thumbnail_text": "B"}],
            "title": "Title A", "description": "d", "tags": ["ai"], "ai_disclosure": True, "made_for_kids": False,
            "cost_usd": 0.002}


@pytest.fixture
def client(tmp_db, monkeypatch):
    monkeypatch.setenv("YCC_ADMIN_PASSWORD", PW)
    webapp._fails.clear()
    approval.register_video(_video())
    return webapp.app.test_client()


def login(c, pw=PW, name="Dr. Test"):
    r = c.post("/login", data={"name": name, "password": pw})
    with c.session_transaction() as s:
        return r, s.get("csrf")


def wait_job():
    for _ in range(200):
        if not jobs.busy():
            return jobs.current()
        time.sleep(0.05)
    raise AssertionError("job did not finish")


# ---------- login ----------
@pytest.mark.parametrize("path", ["/queue", "/video/w01_long", "/dashboard", "/reports", "/run",
                                  "/media/output/week_01/thumbnail_1.png"])
def test_every_page_needs_login(client, path):
    r = client.get(path)
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_posts_and_status_need_login(client):
    assert client.post("/video/w01_long/action", data={"action": "approve"}).status_code == 401
    assert client.post("/run/start", data={"step": "publish", "week": "1"}).status_code == 401
    assert client.get("/run/status").status_code == 401
    assert approval.get("w01_long")["status"] == "pending"


def test_wrong_password_is_refused(client):
    r, csrf = login(client, pw="wrong-password-123")
    assert r.status_code == 401 and csrf is None


def test_lockout_after_five_wrong_passwords(client):
    for _ in range(5):
        login(client, pw="nope-nope-nope")
    r, csrf = login(client)  # right password, but locked out
    assert r.status_code == 429 and csrf is None


def test_no_password_in_env_means_no_login(client, monkeypatch):
    monkeypatch.setenv("YCC_ADMIN_PASSWORD", "")
    r, csrf = login(client, pw="")
    assert csrf is None and b"Login is turned off" in r.data


def test_short_password_is_not_accepted(client, monkeypatch):
    monkeypatch.setenv("YCC_ADMIN_PASSWORD", "short")
    r, csrf = login(client, pw="short")
    assert csrf is None


def test_login_works_and_pages_load(client):
    r, csrf = login(client)
    assert r.status_code == 302 and csrf
    for path in ("/queue", "/video/w01_long", "/dashboard", "/reports", "/run"):
        assert client.get(path).status_code == 200, path


def test_open_redirect_is_blocked(client):
    r = client.post("/login?next=//evil.example", data={"name": "x", "password": PW})
    assert r.headers["Location"].endswith("/queue")


def test_logout(client):
    _, csrf = login(client)
    client.post("/logout", data={"csrf": csrf})
    assert client.get("/queue").status_code == 302


# ---------- CSRF and decisions ----------
def test_post_without_csrf_token_is_refused(client):
    login(client)
    r = client.post("/video/w01_long/action", data={"action": "approve", "title": "t", "description": "d"})
    assert r.status_code == 403
    assert approval.get("w01_long")["status"] == "pending"


def test_approve_button_records_the_logged_in_name(client):
    _, csrf = login(client)
    client.post("/video/w01_long/action", data={"action": "approve", "title": "Title B", "description": "d",
                                               "variant": "1", "csrf": csrf})
    v = approval.get("w01_long")
    assert v["status"] == "approved" and v["approved_by"] == "Dr. Test" and v["chosen_variant"] == 1


def test_request_changes_needs_notes_then_saves_them(client):
    _, csrf = login(client)
    client.post("/video/w01_long/action", data={"action": "changes", "changes": "", "csrf": csrf})
    assert approval.get("w01_long")["status"] == "pending"
    client.post("/video/w01_long/action", data={"action": "changes", "changes": "Shorter intro", "csrf": csrf})
    v = approval.get("w01_long")
    assert v["status"] == "changes_requested" and v["changes_note"] == "Shorter intro"
    with pytest.raises(approval.NotApproved):
        approval.require_approved("w01_long")


def test_reject_and_withdraw_buttons(client):
    _, csrf = login(client)
    client.post("/video/w01_long/action", data={"action": "approve", "title": "t", "description": "d",
                                               "variant": "0", "csrf": csrf})
    client.post("/video/w01_long/action", data={"action": "withdraw", "csrf": csrf})
    assert approval.get("w01_long")["status"] == "pending"
    client.post("/video/w01_long/action", data={"action": "reject", "note": "no", "csrf": csrf})
    assert approval.get("w01_long")["status"] == "rejected"


# ---------- Run buttons ----------
def test_publish_button_uploads_only_approved_and_private(client, monkeypatch):
    from ycc import uploader

    calls = []

    class Spy:
        def insert(self, body, media, thumb):
            calls.append(body)
            return "yt1"

    monkeypatch.setattr(uploader, "client", lambda s: Spy())
    approval.register_video(_video("w01_short1", "short"))
    _, csrf = login(client)
    client.post("/video/w01_long/action", data={"action": "approve", "title": "t", "description": "d",
                                               "variant": "0", "csrf": csrf})
    r = client.post("/run/start", data={"step": "publish", "week": "1", "csrf": csrf})
    assert r.status_code == 302
    job = wait_job()
    assert job["state"] == "done", job
    assert len(calls) == 1 and calls[0]["status"]["privacyStatus"] == "private"
    assert approval.get("w01_short1")["status"] == "pending"
    status = client.get("/run/status").get_json()["job"]
    assert any("not uploaded (pending)" in line for line in status["lines"])


def test_run_button_refuses_a_second_step_while_one_runs(client, monkeypatch):
    def slow(week, log=print):
        log("working")
        time.sleep(0.6)

    monkeypatch.setitem(jobs.STEPS, "prepare", ("Plan and produce this week", slow))
    _, csrf = login(client)
    client.post("/run/start", data={"step": "prepare", "week": "2", "csrf": csrf})
    assert jobs.busy()
    client.post("/run/start", data={"step": "publish", "week": "1", "csrf": csrf})
    page = client.get("/run").data
    assert b"Another step is still running" in page
    wait_job()


def test_run_button_rejects_unknown_steps(client):
    _, csrf = login(client)
    client.post("/run/start", data={"step": "delete_everything", "week": "1", "csrf": csrf})
    assert b"Pick a step" in client.get("/run").data


def test_login_works_over_https_with_secure_cookies(client):
    webapp.app.config["SESSION_COOKIE_SECURE"] = True
    try:
        c = webapp.app.test_client()
        r = c.post("/login", data={"name": "Dr. Test", "password": PW}, base_url="https://abc.trycloudflare.com",
                   headers={"X-Forwarded-Proto": "https"})
        assert r.status_code == 302
        assert "Secure" in r.headers["Set-Cookie"] and "HttpOnly" in r.headers["Set-Cookie"]
        page = c.get("/queue", base_url="https://abc.trycloudflare.com", headers={"X-Forwarded-Proto": "https"})
        assert page.status_code == 200 and page.headers.get("Strict-Transport-Security")
    finally:
        webapp.app.config["SESSION_COOKIE_SECURE"] = False

"""The professor's web app: Review queue, video pages, Dashboard, Reports and Run.

Security
  - Login required for every page and file. The password is YCC_ADMIN_PASSWORD in .env
    (at least 10 characters). Without it, nobody can log in.
  - Every form carries a per-session secret token (CSRF), so another website cannot submit
    an approval or start a step through the professor's browser.
  - 5 wrong passwords from one address lock that address out for 10 minutes.
  - Cookies are HttpOnly and SameSite=Lax; Secure when served over HTTPS (Cloudflare tunnel).
  - Approvals are written only here, by a logged-in user, and the uploader re-checks them in
    plain code (approval.require_approved) right before every upload, including from the Run page.
"""
from __future__ import annotations

import hmac
import os
import secrets
import time
from datetime import timedelta

from flask import Flask, abort, jsonify, redirect, request, send_from_directory, session
from werkzeug.middleware.proxy_fix import ProxyFix

from ycc import approval, channel, jobs, money, run_week
from ycc import web_ui as ui
from ycc.config import PROJECT_ROOT, load_settings
from ycc.storage import OUTPUT, load_json, week_dir

load_settings()  # load .env before reading the secret key and HTTPS setting below
e = ui.e
MIN_PASSWORD = 10
MAX_FAILS, LOCK_SECONDS = 5, 600

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(
    SECRET_KEY=os.getenv("YCC_SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("YCC_HTTPS") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    MAX_CONTENT_LENGTH=1_000_000,
)
_fails: dict[str, list[float]] = {}
PUBLIC = {"/login", "/health"}


# ---------------- auth ----------------
def admin_password() -> str:
    load_settings()  # loads .env
    return os.getenv("YCC_ADMIN_PASSWORD", "")


def _ip() -> str:
    return request.remote_addr or "?"


def _locked() -> bool:
    now = time.time()
    _fails[_ip()] = [t for t in _fails.get(_ip(), []) if now - t < LOCK_SECONDS]
    return len(_fails[_ip()]) >= MAX_FAILS


@app.before_request
def require_login():
    if request.path in PUBLIC:
        return None
    if not session.get("user"):
        if request.path.startswith("/run/status"):
            return jsonify({"error": "login required"}), 401
        if request.method == "POST":
            abort(401)
        return redirect("/login?next=" + request.path)
    if request.method == "POST" and not hmac.compare_digest(request.form.get("csrf", ""), session.get("csrf", "")):
        abort(403)
    return None


@app.after_request
def headers(resp):
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data:; media-src 'self'; "
                                               "style-src 'unsafe-inline'; script-src 'unsafe-inline' 'self'; "
                                               "frame-ancestors 'none'; form-action 'self'")
    if request.is_secure:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000"
    return resp


def page(title, body, active="", flash=None):
    s = load_settings()
    return ui.layout(title, body, active, session.get("user"), session.get("csrf", ""), flash or _pop_flash(),
                     "mock mode" if s.mode == "mock" else "real mode")


def _flash(kind, text):
    session["flash"] = [kind, text]


def _pop_flash():
    f = session.pop("flash", None)
    return tuple(f) if f else None


def csrf_field() -> str:
    return f'<input type="hidden" name="csrf" value="{session.get("csrf", "")}">'


@app.get("/health")
def health():
    return {"ok": True}


@app.route("/login", methods=["GET", "POST"])
def login():
    pw = admin_password()
    msg, status = None, 200
    if not pw or len(pw) < MIN_PASSWORD:
        msg = ("err", f"Login is turned off: set YCC_ADMIN_PASSWORD in .env (at least {MIN_PASSWORD} characters), "
                      "then restart the app.")
    elif request.method == "POST":
        if _locked():
            msg, status = ("err", "Too many wrong passwords. Try again in 10 minutes."), 429
        elif hmac.compare_digest(request.form.get("password", "").encode(), pw.encode()):
            name = (request.form.get("name") or "").strip()[:60] or "Professor"
            session.clear()
            session.permanent = True
            session["user"], session["csrf"] = name, secrets.token_urlsafe(24)
            _fails.pop(_ip(), None)
            nxt = request.args.get("next", "/queue")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else "/queue")
        else:
            _fails.setdefault(_ip(), []).append(time.time())
            msg, status = ("err", "Wrong password."), 401
    body = """<div class="login card"><h1>Sign in</h1><p class="sub">Review and approve videos for the channel.</p>
      <form method="post"><label class="f" for="n">Your name</label>
      <input id="n" type="text" name="name" placeholder="Professor" autocomplete="name">
      <label class="f" for="p">Password</label><input id="p" type="password" name="password" autocomplete="current-password" required>
      <div class="actions"><button class="b-ok">Sign in</button></div></form></div>"""
    return ui.layout("Sign in", body, flash=msg), status


@app.post("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.get("/media/<path:rel>")
def media_file(rel):
    full = (PROJECT_ROOT / rel).resolve()
    if OUTPUT.resolve() not in full.parents:
        abort(404)
    return send_from_directory(full.parent, full.name)


def media_url(rel: str | None) -> str:
    return "/media/" + rel.replace("\\", "/") if rel else ""


# ---------------- review queue ----------------
FILTERS = [("review", "Needs review", ("pending", "changes_requested")), ("approved", "Approved", ("approved",)),
           ("uploaded", "Uploaded", ("uploaded",)), ("rejected", "Rejected", ("rejected",)), ("all", "All", None)]


@app.get("/")
def home():
    return redirect("/queue")


@app.get("/queue")
def queue():
    f = request.args.get("f", "review")
    vids = approval.list_all()
    tabs, shown = "", vids
    for key, label, statuses in FILTERS:
        count = len(vids) if statuses is None else sum(1 for v in vids if v["status"] in statuses)
        tabs += f'<a class="{"on" if key == f else ""}" href="/queue?f={key}">{label} ({count})</a>'
        if key == f and statuses is not None:
            shown = [v for v in vids if v["status"] in statuses]
    cards = ""
    for v in shown:
        poster = media_url(v.get("poster") or (v["thumbnails"][0] if v["thumbnails"] else None))
        cards += f"""<a class="vcard" href="/video/{e(v['id'])}">
          <div class="pic {'short' if v['kind'] == 'short' else ''}" style="background-image:url('{poster}')">
          <span class="kind">{'Short' if v['kind'] == 'short' else 'Long video'} · week {v['week']}</span></div>
          <div class="body">{ui.badge(v['status'])}<div class="t">{e(v['title'])}</div>
          <div class="meta"><span>Cost to make {ui.money_fmt(v.get('cost_usd') or 0)}</span>
          <span>{'' if v['fact_check_passed'] else 'Fact-check warning'}</span></div></div></a>"""
    if not cards:
        cards = '<div class="card"><p>Nothing here. Use <a href="/run">Run</a> to plan and produce a week.</p></div>'
    body = (f'<h1>Review queue</h1><p class="sub">Open a video to watch it, read the script and decide.</p>'
            f'<div class="tabs">{tabs}</div><div class="grid">{cards}</div>')
    return page("Review queue", body, "queue")


# ---------------- video page ----------------
def _script_html(v: dict) -> tuple[str, str]:
    wk = week_dir(v["week"])
    scripted = load_json(wk / "2_script.json", {})
    packed = load_json(wk / "3_package.json", {})
    if v["kind"] == "short":
        n = int(v["id"].rsplit("short", 1)[1]) - 1
        shorts = packed.get("shorts", {}).get("shorts") or []
        sh = shorts[n] if n < len(shorts) else {}
        script = (f'<div class="script"><h4>Hook</h4><p>{e(sh.get("hook", ""))}</p><h4>Script</h4>'
                  f'<p>{e(sh.get("script", ""))}</p><p class="muted">From the section "{e(sh.get("source_section", ""))}" '
                  'of the checked long-video script.</p></div>')
    else:
        sc = scripted.get("script", {})
        secs = "".join(f'<h4>{e(s["heading"])}</h4><p>{e(s["narration"])}</p><p class="ins">{e(s["professor_insert"])}</p>'
                       for s in sc.get("sections", []))
        script = (f'<div class="script"><h4>Hook</h4><p>{e(sc.get("hook", ""))}</p>{secs}'
                  f'<h4>Call to action</h4><p>{e(sc.get("call_to_action", ""))}</p></div>')
    rounds = ""
    for r in scripted.get("rounds", []):
        issues = "".join(f'<p><b>{e(i["claim"])}</b><br>{e(i["problem"])}<br><i>Fix: {e(i["fix"])}</i></p>'
                         for i in r["issues"]) or "<p>All claims accurate and sourced.</p>"
        rounds += (f'<div class="fc {"fail" if r["verdict"] == "FAIL" else ""}"><b>Round {r["round"]}: '
                   f'{"Passed" if r["verdict"] == "PASS" else "Failed"}</b>{issues}</div>')
    return script, rounds or '<p class="muted">No fact-check data.</p>'


@app.get("/video/<vid>")
def video(vid):
    v = approval.get(vid) or abort(404)
    script, checks = _script_html(v)
    poster = media_url(v.get("poster") or (v["thumbnails"][0] if v["thumbnails"] else None))
    if v["variants"]:
        chosen = v["chosen_variant"] or 0
        opts = ""
        for i, var in enumerate(v["variants"]):
            img = f'<img src="{media_url(v["thumbnails"][i])}" alt="">' if i < len(v["thumbnails"]) else ""
            opts += (f'<label class="opt">{img}<span><input type="radio" name="variant" value="{i}" '
                     f'{"checked" if i == chosen else ""} data-title="{e(var["title"])}">{e(var["title"])}</span></label>')
        opts = f'<label class="f">Title and thumbnail options</label><div class="opts">{opts}</div>'
    else:
        opts = '<input type="hidden" name="variant" value="0">'
    warn = ("" if v["fact_check_passed"] else
            '<p class="warn">The fact-check did not pass after 2 rounds. Read the notes before approving.</p>')
    note = (f'<p class="note"><b>Your change request:</b> {e(v["changes_note"])}</p>'
            if v.get("changes_note") and v["status"] == "changes_requested" else "")
    if v["status"] == "uploaded":
        actions = (f'<p class="note">Uploaded {e(v["uploaded_at"])} as <b>{e(v["privacy"])}</b>. YouTube id {e(v["youtube_id"])}. '
                   'Make it public yourself in YouTube Studio when you are ready.</p>')
    else:
        is_appr = v["status"] == "approved"
        withdraw_btn = '<button class="b-plain" name="action" value="withdraw">Withdraw approval</button>' if is_appr else ""
        actions = f"""<form method="post" action="/video/{e(vid)}/action">{csrf_field()}
          {opts}
          <label class="f" for="title">Title</label><input id="title" type="text" name="title" maxlength="100" value="{e(v['title'])}">
          <label class="f" for="desc">Description</label><textarea id="desc" name="description" rows="6">{e(v['description'])}</textarea>
          <label class="f" for="note">Note (optional)</label><input id="note" type="text" name="note" value="{e(v['professor_note'] or '')}">
          <div class="actions">
            <button class="b-ok" name="action" value="approve">{'Update approval' if is_appr else 'Approve'}</button>
            <button class="b-chg" type="button" id="chgbtn">Request changes</button>
            <button class="b-no" name="action" value="reject" id="rejbtn">Reject</button>
            {withdraw_btn}
          </div>
          <div id="chg" class="card" hidden style="margin-top:12px"><label class="f" for="chgtext">What should change?</label>
            <textarea id="chgtext" name="changes" rows="4" placeholder="For example: the intro is too long; add a classroom example about grading essays."></textarea>
            <div class="actions"><button class="b-chg" name="action" value="changes">Send change request</button></div>
            <p class="muted">Then press "Revise with my change requests" on the Run page. The Scriptwriter gets your notes, the Fact-Checker checks again, and the videos come back here.</p></div>
          <p class="muted">Approving does not upload. Uploads happen from the Run page, are always private, and are checked again in code first.</p>
        </form>
        <script>
        document.getElementById('chgbtn').onclick=()=>{{const c=document.getElementById('chg');c.hidden=false;document.getElementById('chgtext').focus();}};
        document.getElementById('rejbtn').onclick=(ev)=>{{if(!confirm('Reject this video? It will not be uploaded.'))ev.preventDefault();}};
        document.querySelectorAll('input[name=variant]').forEach(r=>r.addEventListener('change',()=>{{document.getElementById('title').value=r.dataset.title;}}));
        </script>"""
    spots_html = ('<p class="muted">The yellow lines mark where you add your own classroom example.</p>'
                  if v["professor_spots"] else "")
    events = "".join(f'<tr><td>{e(x["time"])}</td><td>{e(x["action"])}</td><td>{e(x["actor"])}</td></tr>'
                     for x in approval.events(vid))
    how = "Shorts Producer cost / 3" if v["kind"] == "short" else "All agent calls for the week except the Shorts Producer"
    body = f"""<p><a href="/queue">← Review queue</a></p>
      <h1>{e(v['title'])}</h1><p class="sub">{'Short' if v['kind'] == 'short' else 'Long video'} · week {v['week']} · {ui.badge(v['status'])}</p>
      {warn}{note}
      <div class="two"><div>
        <div class="card c-video"><video src="{media_url(v['path'])}" poster="{poster}" controls preload="metadata" playsinline></video></div>
        <div class="card c-script"><h2>Script</h2>{script}{spots_html}</div>
      </div><div>
        <div class="card c-decision"><h2>Decision</h2>{actions}</div>
        <div class="card c-other"><h2>Cost</h2><div class="kv"><b>Cost to make</b><span>{ui.money_fmt(v.get('cost_usd') or 0)}</span>
          <b>How</b><span>{how}</span></div></div>
        <div class="card c-other"><h2>Fact-check</h2>{checks}</div>
        <div class="card c-other"><h2>History</h2><table class="t">{events}</table></div>
      </div></div>"""
    return page(v["title"], body, "queue")


@app.post("/video/<vid>/action")
def video_action(vid):
    v = approval.get(vid) or abort(404)
    f, user = request.form, session["user"]
    act = f.get("action")
    try:
        if act == "approve":
            approval.approve(vid, user, f.get("title", v["title"]), f.get("description", v["description"]),
                             int(f.get("variant", 0) or 0), f.get("note", ""))
            _flash("ok", "Approved. Upload it from the Run page when you are ready (always private).")
        elif act == "changes":
            approval.request_changes(vid, user, f.get("changes", ""))
            _flash("ok", "Change request saved. Press 'Revise with my change requests' on the Run page.")
        elif act == "reject":
            approval.reject(vid, user, f.get("note", ""))
            _flash("ok", "Rejected. This video will not be uploaded.")
        elif act == "withdraw":
            approval.withdraw(vid, user)
            _flash("ok", "Approval withdrawn. The video is back in the review queue.")
        else:
            abort(400)
    except (ValueError, approval.NotApproved) as err:
        _flash("err", str(err))
    return redirect(f"/video/{vid}")


# ---------------- run ----------------
STEP_HELP = {
    "prepare": "Monday to Wednesday: the agents plan the week, write and fact-check the script and package it, and "
               "the code renders 1 long video and 3 Shorts. They land in the review queue.",
    "revise": "Sends your change requests to the Scriptwriter, checks the facts again and rebuilds the videos. "
              "Uploaded videos are never touched; the others come back for review.",
    "publish": "Uploads only the videos you approved, always as private. Each one is checked again in plain code "
               "right before upload.",
    "review": "Sunday: reads the week's numbers, writes the profit report and three recommendations for next week.",
}


@app.get("/run")
def run_page():
    nxt, cur = run_week.next_week(), run_week.current_week()
    vids = approval.list_week(cur)
    counts = {k: sum(1 for v in vids if v["status"] == k) for k in ("approved", "changes_requested", "uploaded")}
    default = {"prepare": nxt, "revise": cur, "publish": cur, "review": cur}
    hint = {"prepare": f"Next week to produce: {nxt}",
            "revise": f"Week {cur}: {counts['changes_requested']} change request(s)",
            "publish": f"Week {cur}: {counts['approved']} approved, waiting to upload",
            "review": f"Week {cur}: {counts['uploaded']} uploaded"}
    cards = ""
    for step, (label, _) in jobs.STEPS.items():
        cls = "b-chg" if step == "revise" else "b-ok"
        cards += f"""<form class="card step" method="post" action="/run/start">{csrf_field()}
          <input type="hidden" name="step" value="{step}"><h2>{e(label)}</h2><p>{e(STEP_HELP[step])}</p>
          <p class="muted">{e(hint[step])}</p>
          <label class="f">Week<input type="number" name="week" min="1" value="{default[step]}"></label>
          <button class="{cls} runbtn">{e(label)}</button></form>"""
    hist = "".join(f'<tr><td>{e(h["label"])}</td><td class="n">{h["week"]}</td><td>{e(h["state"])}</td>'
                   f'<td class="n">{h["seconds"]}s</td><td>{e(h["started_by"])}</td></tr>' for h in jobs.history())
    body = f"""<h1>Run</h1><p class="sub">The weekly steps, one button each. One step runs at a time.</p>
      <div class="card" id="status" hidden><h2 id="st-title"></h2><div class="log" id="st-log"></div><p id="st-result"></p></div>
      <div class="steps">{cards}</div>
      <div class="card"><h2>Recent runs</h2><table class="t"><tr><th>Step</th><th class="n">Week</th><th>Result</th>
        <th class="n">Time</th><th>By</th></tr>{hist or '<tr><td colspan=5>None yet</td></tr>'}</table></div>
      <script>
      async function poll(){{
        const r = await fetch('/run/status'); if(!r.ok) return;
        const j = await r.json(); const box = document.getElementById('status');
        const btns = document.querySelectorAll('.runbtn');
        if(!j.job){{ btns.forEach(b=>b.disabled=false); return; }}
        box.hidden = false;
        const running = j.job.state === 'running';
        document.getElementById('st-title').innerHTML = (running ? '<span class="spin" style="border-color:var(--line);border-top-color:var(--s1)"></span>' : '')
          + j.job.label + ' (week ' + j.job.week + ')' + (running ? ': working, ' + j.job.seconds + ' s' : ': ' + (j.job.state === 'done' ? 'finished' : 'stopped'));
        const log = document.getElementById('st-log'); log.textContent = j.job.lines.join('\\n'); log.scrollTop = log.scrollHeight;
        document.getElementById('st-result').textContent = running ? '' : j.job.result;
        btns.forEach(b=>b.disabled=running);
        if(running) setTimeout(poll, 1500);
      }}
      poll();
      </script>"""
    return page("Run", body, "run")


@app.post("/run/start")
def run_start():
    step = request.form.get("step", "")
    try:
        week = int(request.form.get("week") or 0)
        if week < 1 or step not in jobs.STEPS:
            raise ValueError("Pick a step and a week of 1 or more.")
        jobs.start(step, week, session["user"])
        _flash("ok", f"Started: {jobs.STEPS[step][0]} (week {week}). Progress shows below.")
    except (RuntimeError, ValueError) as err:
        _flash("err", str(err))
    return redirect("/run")


@app.get("/run/status")
def run_status():
    return jsonify({"job": jobs.current()})


# ---------------- dashboard ----------------
@app.get("/dashboard")
def dashboard():
    s = load_settings()
    state = channel.load_state()
    ypp = money.partner_program(state)
    profit_items, views_items, revenue_items = [], [], []
    agent_cost: dict[str, float] = {}
    total_profit = total_cost = total_income = 0.0
    for w in approval.list_weeks():
        rv = load_json(week_dir(w) / "6_review.json")
        if not rv:
            continue
        m = rv["money"]
        total_profit += m["profit_usd"]
        total_cost += m["costs_usd"]["total"]
        total_income += m["income_usd"]["total"]
        views_items.append((f"Week {w}", rv["stats"]["views"]))
        revenue_items.append((f"Week {w}", m["income_usd"]["total"]))
        for a, c in m["costs_usd"]["prune_by_agent"].items():
            agent_cost[a] = agent_cost.get(a, 0) + c
        for pv in rv.get("per_video", []):
            n = pv["id"].split("_", 1)[1]
            label = f"Week {w} " + ("long video" if n == "long" else "Short " + n.replace("short", ""))
            profit_items.append((label, pv["profit_usd"]))
    names = {k: a.name for k, a in s.agents.items()}
    cost_items = sorted(((names.get(a, a), c) for a, c in agent_cost.items()), key=lambda x: -x[1])
    waiting = sum(1 for v in approval.list_all() if v["status"] in ("pending", "changes_requested"))
    sim = ('<p class="warn">Mock mode: channel numbers are simulated and model calls go to the local mock Prune. '
           'Income and profit are estimates.</p>') if s.mode == "mock" else ""
    body = f"""<h1>Dashboard</h1><p class="sub">How the channel and the business are doing.</p>{sim}
      <div class="grid">
        <div class="card"><div class="muted">Estimated profit so far</div><div class="stat">{ui.money_fmt(total_profit)}</div>
          <div class="muted">Income {ui.money_fmt(total_income)} · costs {ui.money_fmt(total_cost)}</div></div>
        <div class="card"><div class="muted">Subscribers</div><div class="stat">{state['subscribers']:,}</div>
          <div class="muted">Watch hours (12 months) {state['watch_hours_12mo']:,}</div></div>
        <div class="card"><div class="muted">Videos waiting for review</div><div class="stat">{waiting}</div>
          <div class="muted"><a href="/queue">Open the review queue</a></div></div>
      </div>
      <div class="card"><h2>YouTube Partner Program (ads)</h2>
        {ui.progress('Subscribers', ypp['subscribers'], ypp['bar']['subscribers'])}
        {ui.progress('Watch hours, last 12 months', ypp['watch_hours_12mo'], ypp['bar']['watch_hours_12mo'])}
        {ui.progress('Shorts views, last 90 days', ypp['shorts_views_90d'], ypp['bar']['shorts_views_90d'])}
        <p class="muted">Ads need the subscribers plus either the watch hours or the Shorts views. {e(ypp['bar_note'])}.</p></div>
      <div class="grid2">
        <div class="card"><h2>Profit per video</h2><p class="muted">Estimated income minus the cost to make it. Blue is profit, red is loss.</p>
          {ui.hbar_chart(profit_items, ui.money_fmt, 'Profit', diverging=True)}</div>
        <div class="card"><h2>Cost per agent</h2><p class="muted">Prune spend, all weeks. Each agent has its own key and daily cap.</p>
          {ui.hbar_chart(cost_items, ui.money_fmt, 'Cost')}</div>
        <div class="card"><h2>Views per week</h2>{ui.vbar_chart(views_items, unit_label='Views')}</div>
        <div class="card"><h2>Revenue per week</h2><p class="muted">Estimated affiliate income. No ad income until the channel joins the Partner Program.</p>
          {ui.vbar_chart(revenue_items, ui.money_fmt, 'Revenue')}</div>
      </div>"""
    return page("Dashboard", body, "dashboard")


# ---------------- reports ----------------
@app.get("/reports")
def reports():
    cards = ""
    for w in sorted(approval.list_weeks(), reverse=True):
        prep = load_json(week_dir(w) / "4_prepare_summary.json", {})
        rv = load_json(week_dir(w) / "6_review.json")
        if rv:
            m, st = rv["money"], rv["stats"]
            recs = "".join(f"<li>{e(r)}</li>" for r in rv["money_report"]["recommendations"])
            worked = "".join(f"<li>{e(x)}</li>" for x in rv["analytics_report"]["what_worked"])
            didnt = "".join(f"<li>{e(x)}</li>" for x in rv["analytics_report"]["what_didnt"]) or "<li>Nothing noted</li>"
            detail = f"""<div class="kv"><b>Views</b><span>{st['views']:,}</span><b>New subscribers</b><span>{st['subs_gained']}</span>
              <b>Watch hours</b><span>{st['watch_hours']}</span><b>Best title</b><span>{e(st['best_variant_title'])}</span>
              <b>Income</b><span>{ui.money_fmt(m['income_usd']['total'])}</span><b>Costs</b><span>{ui.money_fmt(m['costs_usd']['total'])}</span>
              <b>Profit</b><span>{ui.money_fmt(m['profit_usd'])}</span></div>
              <p>{e(rv['analytics_report']['summary'])}</p><h3>What worked</h3><ul>{worked}</ul>
              <h3>What didn't</h3><ul>{didnt}</ul>
              <h3>Recommendations for next week</h3><ul>{recs}</ul><p>{e(rv['money_report']['summary'])}</p>"""
        else:
            detail = '<p class="muted">The week is not closed yet. Publish, then press "Close the week" on the Run page.</p>'
        rounds = ", ".join("passed" if r["verdict"] == "PASS" else "failed" for r in prep.get("fact_check_rounds", []))
        cards += f"""<div class="card"><h2>Week {w}: {e(prep.get('topic', ''))}</h2>
          <p class="muted">Fact-check rounds: {e(rounds) or 'none'} · suspicious comments ignored: {prep.get('suspicious_comments', 0)}
          · agent cost to make: {ui.money_fmt(prep.get('costs', {}).get('total_usd', 0))} · revisions: {len(prep.get('revisions', []))}</p>{detail}</div>"""
    body = f'<h1>Reports</h1><p class="sub">One report per week, newest first.</p>{cards or "<div class=card>No weeks yet.</div>"}'
    return page("Reports", body, "reports")


def serve(port: int = 5000):
    pw = admin_password()
    if not pw or len(pw) < MIN_PASSWORD:
        print(f"WARNING: YCC_ADMIN_PASSWORD is missing or shorter than {MIN_PASSWORD} characters in .env. "
              "Nobody can log in until it is set.")
    print(f"Web app: http://127.0.0.1:{port}")
    try:
        from waitress import serve as wserve
        wserve(app, host="127.0.0.1", port=port, threads=8)
    except ImportError:
        app.run(host="127.0.0.1", port=port, debug=False, threaded=True)

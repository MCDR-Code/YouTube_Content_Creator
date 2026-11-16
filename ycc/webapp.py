"""The professor's review page and the business dashboard. Runs only on this PC (127.0.0.1).

  /                 dashboard: Partner Program progress, profit, cost per agent, weeks
  /week/<n>         review: watch each video, edit title and description, pick a thumbnail,
                    add a note, approve or reject; withdraw an approval before upload
  /week/<n>/publish upload the approved videos (always private)

This page is the only place approvals are written. Every form carries a secret token so other
websites cannot submit approvals through the browser.
"""
from __future__ import annotations

import html
import secrets

from flask import Flask, abort, redirect, request, send_from_directory, url_for

from ycc import approval, channel, money, uploader
from ycc.config import PROJECT_ROOT, load_settings
from ycc.storage import OUTPUT, load_json, week_dir

app = Flask(__name__)
app.config["FORM_TOKEN"] = secrets.token_urlsafe(24)

STYLE = """<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f6fa;color:#101c36}
header{background:#101c36;color:#fff;padding:14px 28px;border-bottom:5px solid #00a896}
header a{color:#fff;text-decoration:none;margin-right:18px}
main{padding:20px 28px;max-width:1150px}
.card{background:#fff;border-radius:8px;padding:16px 20px;margin:14px 0;box-shadow:0 1px 3px #0002}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.k{font-size:28px;font-weight:600}.muted{color:#5a6785;font-size:13px}
.bar{background:#e3e8f1;border-radius:6px;height:12px}.bar div{background:#00a896;height:12px;border-radius:6px}
table{border-collapse:collapse;width:100%}td,th{padding:6px 8px;border-bottom:1px solid #e3e8f1;text-align:left;font-size:14px}
.pill{padding:2px 9px;border-radius:10px;font-size:12px;color:#fff}
.pending{background:#c08a00}.approved{background:#1b7f4a}.rejected{background:#a33}.uploaded{background:#2a5bd7}
input[type=text],textarea{width:100%;font:inherit;padding:6px;border:1px solid #c5cddd;border-radius:4px}
button{font:inherit;padding:7px 16px;border:0;border-radius:5px;cursor:pointer;margin-right:8px}
.ok{background:#1b7f4a;color:#fff}.no{background:#a33;color:#fff}.plain{background:#dfe5ef}
.thumbs label{display:inline-block;margin-right:10px;text-align:center;font-size:12px}
.thumbs img{width:220px;border:3px solid transparent;border-radius:4px;display:block}
.warn{background:#fff4d6;border-left:4px solid #c08a00;padding:8px 12px}
</style>"""


def page(title: str, body: str) -> str:
    weeks = approval.list_weeks()
    nav = "".join(f'<a href="{url_for("week", n=w)}">Week {w}</a>' for w in weeks)
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>{STYLE}</head>"
            f"<body><header><a href='{url_for('dashboard')}'><b>YouTube Content Creator</b></a>{nav}</header>"
            f"<main>{body}</main></body></html>")


def _check_token():
    if request.form.get("token") != app.config["FORM_TOKEN"]:
        abort(403)


def _token_field() -> str:
    return f'<input type="hidden" name="token" value="{app.config["FORM_TOKEN"]}">'


@app.get("/media/<path:rel>")
def media_file(rel):
    full = (PROJECT_ROOT / rel).resolve()
    if OUTPUT.resolve() not in full.parents:
        abort(404)
    return send_from_directory(full.parent, full.name)


@app.get("/")
def dashboard():
    s = load_settings()
    state = channel.load_state()
    ypp = money.partner_program(state)
    rows, total_profit, total_prune = "", 0.0, 0.0
    agent_costs: dict[str, float] = {}
    for w in approval.list_weeks():
        rv = load_json(week_dir(w) / "6_review.json")
        prep = load_json(week_dir(w) / "4_prepare_summary.json", {})
        if rv:
            m = rv["money"]
            total_profit += m["profit_usd"]
            total_prune += m["costs_usd"]["prune_total"]
            for a, c in m["costs_usd"]["prune_by_agent"].items():
                agent_costs[a] = agent_costs.get(a, 0) + c
            rows += (f"<tr><td><a href='{url_for('week', n=w)}'>Week {w}</a></td><td>{html.escape(prep.get('topic', ''))}</td>"
                     f"<td>{rv['stats']['views']:,}</td><td>{rv['stats']['subs_gained']}</td>"
                     f"<td>{rv['stats']['watch_hours']}</td><td>${m['income_usd']['total']:.2f}</td>"
                     f"<td>${m['costs_usd']['total']:.4f}</td><td>${m['profit_usd']:.2f}</td></tr>")
        else:
            rows += (f"<tr><td><a href='{url_for('week', n=w)}'>Week {w}</a></td><td>{html.escape(prep.get('topic', ''))}"
                     f"</td><td colspan=6 class=muted>waiting for approval, upload or review</td></tr>")

    def bar(pct):
        return f"<div class=bar><div style='width:{max(pct, 0.5)}%'></div></div>"

    recs = "".join(f"<li>{html.escape(r)}</li>" for r in state.get("last_recommendations", [])) or "<li>None yet</li>"
    costs = "".join(f"<tr><td>{html.escape(s.agents[a].name if a in s.agents else a)}</td><td>${c:.6f}</td></tr>"
                    for a, c in sorted(agent_costs.items(), key=lambda x: -x[1]))
    sim = "<p class=warn>Mode: <b>mock</b>. Channel numbers are simulated and model calls go to the local mock Prune.</p>" \
        if s.mode == "mock" else "<p class=muted>Mode: real. Model calls go through Prune.</p>"
    body = f"""<h1>Channel dashboard</h1>{sim}
    <div class=grid>
      <div class=card><div class=muted>YouTube Partner Program (ads)</div>
        <p>Subscribers {ypp['subscribers']:,} of {ypp['bar']['subscribers']:,}</p>{bar(ypp['subscribers_pct'])}
        <p>Watch hours (12 months) {ypp['watch_hours_12mo']:,} of {ypp['bar']['watch_hours_12mo']:,}</p>{bar(ypp['watch_hours_pct'])}
        <p>Shorts views (90 days) {ypp['shorts_views_90d']:,} of {ypp['bar']['shorts_views_90d']:,}</p>{bar(ypp['shorts_views_pct'])}
        <p class=muted>{html.escape(ypp['bar_note'])}</p></div>
      <div class=card><div class=muted>Profit so far (estimated)</div><div class=k>${total_profit:.2f}</div>
        <p class=muted>Prune spend so far: ${total_prune:.4f}</p>
        <div class=muted>Recommendations for next week</div><ul>{recs}</ul></div>
    </div>
    <div class=card><h3>Weeks</h3><table><tr><th>Week</th><th>Topic</th><th>Views</th><th>New subs</th>
      <th>Watch hours</th><th>Income</th><th>Costs</th><th>Profit</th></tr>{rows}</table></div>
    <div class=card><h3>Prune spend by agent</h3><table>{costs or '<tr><td>No reviews yet</td></tr>'}</table>
      <p class=muted>Each agent has its own Prune key and daily cap. Details: logs/cost_log.jsonl</p></div>"""
    return page("Dashboard", body)


@app.get("/week/<int:n>")
def week(n):
    vids = approval.list_week(n)
    if not vids:
        abort(404)
    prep = load_json(week_dir(n) / "4_prepare_summary.json", {})
    cards = ""
    for v in vids:
        media_url = url_for("media_file", rel=v["path"].replace("\\", "/"))
        status = f"<span class='pill {v['status']}'>{v['status']}</span>"
        warn = "" if v["fact_check_passed"] else "<p class=warn>The fact-check did not pass after 2 rounds. Read the script notes before approving.</p>"
        spots = "".join(f"<li>{html.escape(x)}</li>" for x in v["professor_spots"])
        spots = f"<p class=muted>Spots for your own example:</p><ul>{spots}</ul>" if spots else ""
        thumbs = ""
        if v["thumbnails"]:
            thumbs = "<div class=thumbs><p class=muted>Pick a title and thumbnail (all three can be tested later in YouTube Studio):</p>"
            for i, (t, var) in enumerate(zip(v["thumbnails"], v["variants"])):
                chk = "checked" if (v["chosen_variant"] or 0) == i else ""
                thumbs += (f"<label><img src='{url_for('media_file', rel=t.replace(chr(92), '/'))}'>"
                           f"<input type=radio name=variant value={i} {chk}> {html.escape(var['title'])}</label>")
            thumbs += "</div>"
        else:
            thumbs = "<input type=hidden name=variant value=0>"
        if v["status"] in ("pending", "rejected"):
            form = f"""<form method=post action="{url_for('decide', vid=v['id'])}">{_token_field()}{thumbs}
              <p>Title<input type=text name=title value="{html.escape(v['title'])}" maxlength=100></p>
              <p>Description<textarea name=description rows=6>{html.escape(v['description'])}</textarea></p>
              <p>Your note (optional)<input type=text name=note value="{html.escape(v['professor_note'] or '')}"></p>
              <p>Your name<input type=text name=approver value="" placeholder="Required to approve"></p>
              <button class=ok name=action value=approve>Approve (upload will be private)</button>
              <button class=no name=action value=reject>Reject</button></form>"""
        elif v["status"] == "approved":
            form = f"""<p>Approved by <b>{html.escape(v['approved_by'])}</b> at {v['approved_at']}. Title: {html.escape(v['title'])}</p>
              <form method=post action="{url_for('withdraw', vid=v['id'])}">{_token_field()}
              <input type=hidden name=approver value="{html.escape(v['approved_by'])}">
              <button class=plain>Withdraw approval</button></form>"""
        else:
            form = (f"<p>Uploaded {v['uploaded_at']} as <b>{v['privacy']}</b>. YouTube id: {v['youtube_id']}. "
                    "Make it public yourself in YouTube Studio when ready.</p>")
        poster = (f' poster="{url_for("media_file", rel=v["thumbnails"][0].replace(chr(92), "/"))}"'
                  if v["thumbnails"] else "")
        cards += f"""<div class=card><h3>{html.escape(v['id'])} ({v['kind']}) {status}</h3>{warn}
          <video src="{media_url}" controls preload="metadata"{poster} width="{640 if v['kind'] == 'long' else 300}"></video>{spots}{form}</div>"""
    approved = sum(1 for v in vids if v["status"] == "approved")
    pub = (f"""<form method=post action="{url_for('publish', n=n)}">{_token_field()}
      <button class=ok>Upload the {approved} approved video(s) as private</button></form>""" if approved else
           "<p class=muted>No approved videos waiting to upload.</p>")
    body = (f"<h1>Week {n}: {html.escape(prep.get('topic', ''))}</h1>"
            f"<p class=muted>Fact-check rounds: {len(prep.get('fact_check_rounds', []))}. "
            f"Suspicious comments ignored by the agents: {prep.get('suspicious_comments', 0)}. "
            f"Agent cost this week: ${prep.get('costs', {}).get('total_usd', 0):.6f}</p>{pub}{cards}")
    return page(f"Week {n}", body)


@app.post("/video/<vid>/decide")
def decide(vid):
    _check_token()
    v = approval.get(vid) or abort(404)
    f = request.form
    if f.get("action") == "approve":
        try:
            approval.approve(vid, f.get("approver", ""), f.get("title", ""), f.get("description", ""),
                             int(f.get("variant", 0)), f.get("note", ""))
        except ValueError as e:
            return page("Not approved", f"<p class=warn>{html.escape(str(e))}</p><a href='javascript:history.back()'>Back</a>"), 400
    else:
        approval.reject(vid, f.get("approver") or "professor", f.get("note", ""))
    return redirect(url_for("week", n=v["week"]))


@app.post("/video/<vid>/withdraw")
def withdraw(vid):
    _check_token()
    v = approval.get(vid) or abort(404)
    approval.withdraw(vid, request.form.get("approver", "professor"))
    return redirect(url_for("week", n=v["week"]))


@app.post("/week/<int:n>/publish")
def publish(n):
    _check_token()
    uploader.upload_approved(n, uploader.client(load_settings()))
    return redirect(url_for("week", n=n))


def serve(port: int = 5000):
    print(f"Review page: http://127.0.0.1:{port}  (only reachable from this PC)")
    app.run(host="127.0.0.1", port=port, debug=False)

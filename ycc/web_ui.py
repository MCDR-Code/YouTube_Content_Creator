"""Look and feel of the web app: layout, styles (phone-friendly, light and dark), and SVG charts.

Charts are drawn on the server as SVG, so they work over the tunnel and on a phone with no
extra downloads. Chart colors follow a validated, colorblind-safe palette: one blue for single
series, blue and red (with a gray zero line) for profit versus loss. Every chart has a hover
tooltip on each mark, value labels, and a "Show as table" view.
"""
from __future__ import annotations

import html

e = html.escape

CSS = """
:root{--bg:#f4f6fa;--card:#fff;--ink:#101c36;--ink2:#52607a;--line:#e3e8f1;--brand:#101c36;--accent:#00a896;
--s1:#2a78d6;--neg:#e34948;--zero:#b9bfc9;--good:#0ca30c;--warn:#b07a00;--crit:#d03b3b;--info:#2a78d6;--shadow:0 1px 3px #0001,0 4px 14px #0000000a}
@media (prefers-color-scheme:dark){:root{--bg:#121417;--card:#1c1f24;--ink:#eef1f5;--ink2:#a9b1bd;--line:#2c3139;
--brand:#0b1426;--s1:#3987e5;--neg:#e66767;--zero:#555b64;--good:#0ca30c;--warn:#e0a400;--crit:#e66767;--shadow:none}}
*{box-sizing:border-box}body{margin:0;font-family:"Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;
background:var(--bg);color:var(--ink);font-size:16px;line-height:1.45}
a{color:inherit}
.top{position:sticky;top:0;z-index:5;background:var(--brand);color:#fff;border-bottom:4px solid var(--accent)}
.top .in{max-width:1180px;margin:0 auto;display:flex;align-items:center;gap:6px;padding:0 14px;overflow-x:auto}
.brand{font-weight:700;padding:14px 10px 14px 0;white-space:nowrap}
.nav{display:flex}.nav a{display:inline-block;padding:15px 12px;text-decoration:none;color:#cfd6e4;white-space:nowrap;border-bottom:3px solid transparent;margin-bottom:-4px}
.nav a.on,.nav a:hover{color:#fff;border-bottom-color:var(--accent)}
@media (max-width:700px){.top .in{flex-wrap:wrap;gap:0 8px}.brand{padding:12px 0 4px}.nav{order:3;width:100%;overflow-x:auto}.nav a{padding:10px 12px 12px}.who{padding-top:8px}}
.who{margin-left:auto;display:flex;align-items:center;gap:8px;white-space:nowrap;font-size:14px;color:#cfd6e4}
.who form{margin:0}.who button{background:transparent;color:#cfd6e4;border:1px solid #ffffff40;padding:6px 10px;border-radius:8px;min-height:auto}
main{max-width:1180px;margin:0 auto;padding:18px 14px 60px}
h1{font-size:26px;margin:6px 0 4px}h2{font-size:19px;margin:0 0 10px}h3{font-size:16px;margin:0 0 6px}
.sub{color:var(--ink2);margin:0 0 16px}
.card{background:var(--card);border-radius:14px;box-shadow:var(--shadow);border:1px solid var(--line);padding:16px;margin:0 0 16px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,440px),1fr));gap:16px}
.vcard{display:block;text-decoration:none;background:var(--card);border-radius:14px;overflow:hidden;border:1px solid var(--line);box-shadow:var(--shadow);transition:transform .12s}
.vcard:hover{transform:translateY(-2px)}
.vcard .pic{aspect-ratio:16/9;background:#0b1426 center/cover no-repeat;position:relative}
.vcard .pic.short{background-size:contain}
.vcard .body{padding:12px 14px}
.vcard .t{font-weight:600;margin:6px 0 8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.meta{display:flex;justify-content:space-between;align-items:center;color:var(--ink2);font-size:14px;gap:8px}
.badge{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:600;padding:3px 10px;border-radius:99px;border:1px solid currentColor;white-space:nowrap}
.badge::before{content:"";width:8px;height:8px;border-radius:50%;background:currentColor}
.b-pending{color:var(--warn)}.b-changes_requested{color:var(--info)}.b-approved{color:var(--good)}.b-rejected{color:var(--crit)}.b-uploaded{color:var(--ink2)}
.kind{position:absolute;left:10px;bottom:10px;background:#000a;color:#fff;font-size:12px;padding:2px 8px;border-radius:6px}
.tabs{display:flex;gap:8px;overflow-x:auto;margin:0 0 16px}
.tabs a{padding:8px 14px;border-radius:99px;border:1px solid var(--line);background:var(--card);text-decoration:none;white-space:nowrap;font-size:14px}
.tabs a.on{background:var(--ink);color:var(--card);border-color:var(--ink)}
.btn,button{font:inherit;font-weight:600;border:0;border-radius:12px;padding:12px 18px;min-height:48px;cursor:pointer;background:var(--line);color:var(--ink)}
.btn{display:inline-flex;align-items:center;justify-content:center;text-decoration:none}
.b-ok{background:#1b7f4a;color:#fff}.b-chg{background:var(--s1);color:#fff}.b-no{background:var(--crit);color:#fff}.b-plain{background:var(--line);color:var(--ink)}
button:disabled{opacity:.45;cursor:not-allowed}
.actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:12px}
input[type=text],input[type=password],input[type=number],textarea,select{width:100%;font:inherit;padding:12px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink)}
label.f{display:block;font-weight:600;font-size:14px;margin:12px 0 6px}
.two{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:16px}
@media (max-width:860px){.two{display:flex;flex-direction:column;gap:0}.two>div{display:contents}.c-video{order:1}.c-decision{order:2}.c-script{order:3}.c-other{order:4}}
video{width:100%;border-radius:12px;background:#000;max-height:70vh}
.opts{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px}
.opt{border:2px solid var(--line);border-radius:12px;padding:8px;cursor:pointer;display:block}
.opt img{width:100%;border-radius:8px;display:block}.opt span{display:block;font-size:14px;margin-top:6px}
.opt input{margin-right:6px}.opt:has(input:checked){border-color:var(--s1)}
.kv{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;font-size:15px}.kv b{color:var(--ink2);font-weight:600}
.script h4{margin:14px 0 4px}.script p{margin:0 0 6px}.ins{background:#fff4d6;color:#5a4500;padding:6px 10px;border-radius:8px;font-size:14px}
@media (prefers-color-scheme:dark){.ins{background:#3a3010;color:#ffe08a}}
.fc{border-left:4px solid var(--good);padding:6px 12px;margin:8px 0}.fc.fail{border-color:var(--crit)}
.note{background:var(--bg);border-radius:10px;padding:10px 12px;color:var(--ink2);font-size:14px}
.warn{background:#fff4d6;border-left:4px solid var(--warn);padding:10px 12px;border-radius:8px;color:#5a4500}
@media (prefers-color-scheme:dark){.warn{background:#3a3010;color:#ffe08a}}
.flash{padding:12px 14px;border-radius:10px;margin:0 0 14px;background:#e3f6ec;color:#0d4f2c}.flash.err{background:#fde8e8;color:#7a1b1b}
.stat{font-size:30px;font-weight:700}.muted{color:var(--ink2);font-size:14px}
.prog{height:12px;background:var(--line);border-radius:99px;overflow:hidden}.prog div{height:100%;background:var(--s1);border-radius:99px}
.log{background:#0b1426;color:#d6e2f5;border-radius:12px;padding:12px;font:13px/1.5 Consolas,Menlo,monospace;max-height:420px;overflow:auto;white-space:pre-wrap}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
.step{display:flex;flex-direction:column;gap:8px}.step p{margin:0;color:var(--ink2);font-size:14px;flex:1}
.spin{display:inline-block;width:16px;height:16px;border:3px solid #ffffff55;border-top-color:#fff;border-radius:50%;animation:s 1s linear infinite;vertical-align:-3px;margin-right:8px}
@keyframes s{to{transform:rotate(360deg)}}
table.t{border-collapse:collapse;width:100%;font-size:14px}table.t td,table.t th{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left}
table.t td.n,table.t th.n{text-align:right;font-variant-numeric:tabular-nums}
details summary{cursor:pointer;color:var(--ink2);font-size:14px;margin-top:8px}
.chart svg{width:100%;height:auto;display:block}.chart .bar:hover{opacity:.8}
.login{max-width:420px;margin:8vh auto}
"""

NAV = [("queue", "Review queue"), ("dashboard", "Dashboard"), ("reports", "Reports"), ("run", "Run")]


def layout(title: str, body: str, active: str = "", user: str | None = None, csrf: str = "",
           flash: tuple[str, str] | None = None, mode: str = "") -> str:
    nav = "".join(f'<a class="{"on" if k == active else ""}" href="/{k}">{e(lbl)}</a>' for k, lbl in NAV) if user else ""
    who = (f'<div class="who">{e(user)}{" · " + e(mode) if mode else ""}<form method="post" action="/logout">'
           f'<input type="hidden" name="csrf" value="{csrf}"><button>Log out</button></form></div>') if user else ""
    fl = f'<div class="flash {"err" if flash[0] == "err" else ""}">{e(flash[1])}</div>' if flash else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="color-scheme" content="light dark"><title>{e(title)} · YouTube Content Creator</title>'
            f'<style>{CSS}</style></head><body><div class="top"><div class="in"><div class="brand">YouTube Content Creator</div>'
            f'<nav class="nav">{nav}</nav>{who}</div></div><main>{fl}{body}</main></body></html>')


def badge(status: str) -> str:
    label = {"pending": "Needs review", "changes_requested": "Changes requested", "approved": "Approved",
             "rejected": "Rejected", "uploaded": "Uploaded (private)"}.get(status, status)
    return f'<span class="badge b-{e(status)}">{label}</span>'


def money_fmt(x: float) -> str:
    x = x or 0
    if abs(x) < 0.01 and x != 0:
        return f"${x:.4f}"
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


# ---------------- charts ----------------
def _table(headers: list[str], rows: list[list[str]], numeric_from: int = 1) -> str:
    th = "".join(f'<th class="{"n" if i >= numeric_from else ""}">{e(h)}</th>' for i, h in enumerate(headers))
    trs = "".join("<tr>" + "".join(f'<td class="{"n" if i >= numeric_from else ""}">{e(str(c))}</td>'
                                   for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<details><summary>Show as table</summary><table class="t"><tr>{th}</tr>{trs}</table></details>'


def hbar_chart(items: list[tuple[str, float]], fmt=money_fmt, unit_label: str = "", diverging: bool = False) -> str:
    """Horizontal bars, one row per item. Diverging: positive blue, negative red, gray zero line."""
    if not items:
        return '<p class="muted">No data yet.</p>'
    W, row, left, right = 460, 30, 150, 70
    H = row * len(items) + 16
    lo = min(0.0, min(v for _, v in items))
    hi = max(0.0, max(v for _, v in items)) or 1.0
    span = (hi - lo) or 1.0
    x = lambda v: left + (v - lo) / span * (W - left - right)  # noqa: E731
    zero = x(0)
    parts = [f'<line x1="{zero:.1f}" x2="{zero:.1f}" y1="4" y2="{H - 8}" stroke="var(--zero)" stroke-width="1"/>']
    for i, (label, v) in enumerate(items):
        y = 8 + i * row
        x0, x1 = sorted((zero, x(v)))
        w = max(x1 - x0, 2)
        color = "var(--neg)" if (diverging and v < 0) else "var(--s1)"
        lbl = label if len(label) <= 22 else label[:21] + "…"
        parts.append(f'<text x="{left - 10}" y="{y + 17}" text-anchor="end" font-size="13" fill="var(--ink2)">{e(lbl)}</text>')
        parts.append(f'<rect class="bar" x="{x0:.1f}" y="{y + 4}" width="{w:.1f}" height="{row - 12}" rx="4" fill="{color}">'
                     f'<title>{e(label)}: {e(fmt(v))}</title></rect>')
        tx = (x1 + 6) if v >= 0 else (x0 - 6)
        anchor = "start" if v >= 0 else "end"
        parts.append(f'<text x="{tx:.1f}" y="{y + 17}" text-anchor="{anchor}" font-size="12.5" fill="var(--ink)">{e(fmt(v))}</text>')
    svg = (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="bar chart">{"".join(parts)}</svg>')
    table = _table(["Item", unit_label or "Value"], [[lbl, fmt(v)] for lbl, v in items])
    return f'<div class="chart">{svg}{table}</div>'


def vbar_chart(items: list[tuple[str, float]], fmt=lambda v: f"{v:,.0f}", unit_label: str = "") -> str:
    """Vertical bars over time (one series)."""
    if not items:
        return '<p class="muted">No data yet.</p>'
    W, H, left, bottom, top_ = 460, 220, 12, 30, 24
    n = len(items)
    hi = max(v for _, v in items) or 1.0
    slot = (W - 2 * left) / n
    bw = min(64, slot * 0.6)
    parts = [f'<line x1="{left}" x2="{W - left}" y1="{H - bottom}" y2="{H - bottom}" stroke="var(--zero)"/>']
    for i, (label, v) in enumerate(items):
        cx = left + slot * (i + 0.5)
        h = (v / hi) * (H - bottom - top_)
        y = H - bottom - h
        parts.append(f'<rect class="bar" x="{cx - bw / 2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(h, 2):.1f}" rx="4" '
                     f'fill="var(--s1)"><title>{e(label)}: {e(fmt(v))}</title></rect>')
        parts.append(f'<text x="{cx:.1f}" y="{y - 7:.1f}" text-anchor="middle" font-size="12.5" fill="var(--ink)">{e(fmt(v))}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{H - 12}" text-anchor="middle" font-size="13" fill="var(--ink2)">{e(label)}</text>')
    svg = f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="bar chart">{"".join(parts)}</svg>'
    return f'<div class="chart">{svg}{_table(["Week", unit_label or "Value"], [[l, fmt(v)] for l, v in items])}</div>'


def progress(label: str, have: float, need: float, fmt=lambda v: f"{v:,.0f}") -> str:
    pct = 0 if not need else min(100.0, 100.0 * have / need)
    return (f'<div style="margin:10px 0"><div class="meta"><span>{e(label)}</span><span>{fmt(have)} of {fmt(need)} '
            f'({pct:.1f}%)</span></div><div class="prog" role="progressbar" aria-valuenow="{pct:.1f}" aria-valuemin="0" '
            f'aria-valuemax="100"><div style="width:{max(pct, 0.6):.2f}%"></div></div></div>')

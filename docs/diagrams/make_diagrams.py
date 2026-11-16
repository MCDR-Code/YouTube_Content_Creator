"""Builds the four design diagrams as SVG files in this folder. Run: python docs/diagrams/make_diagrams.py
PNG copies are made from the SVGs with any browser or converter (see README in this folder)."""
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
NAVY, TEAL, AMBER, RED, GREY, INK, LIGHT = "#101c36", "#00a896", "#c08a00", "#b03a3a", "#5a6785", "#101c36", "#eef3f8"


class SVG:
    def __init__(self, w, h, title):
        self.w, self.h, self.parts = w, h, []
        self.parts.append(f'<rect width="{w}" height="{h}" fill="white"/>')
        self.text(24, 38, title, 22, 700)

    def text(self, x, y, s, size=14, weight=400, fill=INK, anchor="start"):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
                          f'text-anchor="{anchor}">{escape(s)}</text>')

    def box(self, x, y, w, h, title, lines=(), stroke=NAVY, fill="white", title_fill=INK, dash=False):
        d = ' stroke-dasharray="6 4"' if dash else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" '
                          f'stroke="{stroke}" stroke-width="2"{d}/>')
        self.text(x + 14, y + 26, title, 15, 700, title_fill)
        for i, ln in enumerate(lines):
            self.text(x + 14, y + 48 + 19 * i, ln, 13, 400, GREY if fill == "white" else INK)

    def group(self, x, y, w, h, label, color=TEAL, right=False):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{color}" fill-opacity="0.07" '
                          f'stroke="{color}" stroke-width="1.5"/>')
        if right:
            self.text(x + w - 14, y + 24, label, 14, 700, color, "end")
        else:
            self.text(x + 14, y + 24, label, 14, 700, color)

    def arrow(self, pts, label=None, color=NAVY, lx=None, ly=None, dash=False):
        d = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(pts))
        da = ' stroke-dasharray="6 4"' if dash else ""
        mid = f"a{abs(hash(color)) % 9999}"
        self.parts.append(f'<defs><marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
                          f'markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{color}"/>'
                          f'</marker></defs><path d="{d}" fill="none" stroke="{color}" stroke-width="1.8"{da} '
                          f'marker-end="url(#{mid})"/>')
        if label:
            (x1, y1), (x2, y2) = pts[0], pts[-1]
            self.text(lx if lx is not None else (x1 + x2) / 2 + 6, ly if ly is not None else (y1 + y2) / 2 - 6,
                      label, 12, 400, GREY)

    def save(self, name):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" '
               f'height="{self.h}" font-family="Segoe UI, Arial, sans-serif">' + "".join(self.parts) + "</svg>")
        (HERE / f"{name}.svg").write_text(svg, encoding="utf-8")


def architecture():
    s = SVG(1180, 660, "System architecture: ten Swarms agents, one Prune gateway, plain code at the edges")
    s.group(24, 64, 560, 400, "Swarms agents (each with its own Prune key and daily cap)")
    s.box(44, 104, 250, 108, "Plan: HierarchicalSwarm", ["Channel Director gives orders to", "Trend Scout, Audience Analyst,", "Monetization Manager"])
    s.box(314, 104, 250, 108, "Script: SequentialWorkflow", ["Scriptwriter, then Fact-Checker", "loop in code, max 2 rounds"])
    s.box(44, 232, 250, 108, "Package: ConcurrentWorkflow", ["Visual Designer, Packaging & SEO,", "Shorts Producer at the same time"])
    s.box(314, 232, 250, 108, "Review: SequentialWorkflow", ["Analytics Analyst, then", "Monetization Manager"])
    s.text(44, 372, "Every agent: JSON output checked against a fixed shape.", 13, 400, GREY)
    s.text(44, 392, "No agent has a tool that reaches approvals, files or YouTube.", 13, 400, GREY)
    s.text(44, 412, "Numbers come from code; agents only interpret them.", 13, 400, GREY)
    s.text(44, 432, "Viewer comments are data inside <comments>, never instructions.", 13, 400, GREY)

    s.box(670, 104, 220, 150, "Prune gateway", ["api.withprune.com/v1", "per-key daily spend caps", "run budget per week", "Shield, signed receipts"], stroke=TEAL)
    s.box(940, 104, 210, 110, "Model provider", ["OpenAI (key kept in", "Prune's vault, never", "in our code)"])
    s.box(670, 290, 220, 110, "Mock Prune (mock mode)", ["local, free, same format", "fake costs and receipts"], dash=True)
    s.arrow([(584, 160), (670, 160)], "all calls", lx=596, ly=150)
    s.arrow([(890, 159), (940, 159)])
    s.arrow([(584, 330), (670, 340)], "mock mode", lx=592, ly=362, dash=True)

    s.group(24, 490, 1126, 150, "Plain code (no language model)", NAVY, right=True)
    s.box(44, 524, 200, 96, "Video maker", ["slides, voice, captions,", "MP4s, 3 thumbnails"])
    s.box(264, 524, 200, 96, "Review page", ["professor approves or", "rejects (127.0.0.1)"], stroke=AMBER)
    s.box(484, 524, 200, 96, "Approval gate", ["status + event log", "in SQLite"], stroke=AMBER)
    s.box(704, 524, 200, 96, "Uploader", ["approved only,", "always private"], stroke=AMBER)
    s.box(924, 524, 206, 96, "Cost log + money", ["cost per agent, profit;", "feeds the Sunday review"])
    s.arrow([(169, 464), (144, 524)])
    s.arrow([(244, 572), (264, 572)])
    s.arrow([(464, 572), (484, 572)])
    s.arrow([(684, 572), (704, 572)])
    s.box(940, 290, 210, 110, "YouTube", ["private uploads only;", "professor makes public", "in YouTube Studio"], stroke=RED)
    s.arrow([(804, 524), (804, 470), (1045, 470), (1045, 400)], "private upload", lx=880, ly=462)
    s.save("1_architecture")


def weekly_cycle():
    s = SVG(1060, 470, "Weekly cycle: four Swarms patterns do the work, plain code guards YouTube")
    W, H = 300, 120
    xs, ya, yb = (40, 380, 720), 70, 280
    s.box(xs[0], ya, W, H, "1 Plan (Monday)", ["HierarchicalSwarm", "Director gives orders to 3 helpers,", "then writes the week's plan"])
    s.box(xs[1], ya, W, H, "2 Script (Tuesday)", ["SequentialWorkflow", "Scriptwriter, then Fact-Checker,", "loop in code, max 2 rounds"])
    s.box(xs[2], ya, W, H, "3 Package (Wednesday)", ["ConcurrentWorkflow", "Visual, Packaging & SEO, Shorts;", "then code renders the videos"])
    s.box(xs[2], yb, W, H, "4 Approve (Thursday)", ["Plain code, no agent", "Professor watches, edits, picks a", "thumbnail, approves or rejects"], stroke=AMBER, fill="#fff6e0")
    s.box(xs[1], yb, W, H, "5 Publish (Friday)", ["Plain code, no agent", "Uploads approved videos only,", "always private, AI disclosure set"], stroke=AMBER, fill="#fff6e0")
    s.box(xs[0], yb, W, H, "6 Review (Sunday)", ["SequentialWorkflow", "Analytics Analyst, then Monetization", "Manager: profit report, 3 next steps"])
    s.arrow([(340, 130), (380, 130)])
    s.arrow([(680, 130), (720, 130)])
    s.arrow([(870, 190), (870, 280)])
    s.arrow([(720, 340), (680, 340)])
    s.arrow([(380, 340), (340, 340)])
    s.arrow([(190, 280), (190, 190)], "next week's plan reads the 3 recommendations", lx=200, ly=240)
    s.text(40, 445, "Shaded boxes are plain code: only the professor's approval lets a video reach YouTube, and always as private.", 13, 400, GREY)
    s.save("2_weekly_cycle")


def prune_call_path():
    s = SVG(1180, 430, "One model call: from an agent, through Prune with its own key, to the cost log")
    y = 90
    s.box(24, y, 210, 150, "Swarms Agent", ["e.g. Scriptwriter", "own key PRUNE_KEY_...", "model openai/gpt-4o-mini", "headers: run ID, budget,", "feature tag"])
    s.box(274, y, 170, 150, "LiteLLM", ["inside Swarms", "chat/completions", "to llm_base_url"])
    s.box(484, y, 260, 150, "Prune checks first", ["1 key valid", "2 daily spend cap for this key", "3 run budget for this week", "4 Shield (injection, loops,", "   model allowlist)"], stroke=TEAL)
    s.box(784, y, 170, 150, "Provider", ["OpenAI, using the key", "in Prune's vault"])
    s.box(994, y, 160, 150, "Reply", ["JSON answer +", "prune_metadata:", "cost, cache hit,", "signed receipt"])
    s.box(784, 290, 370, 110, "Blocked: HTTP 429 (spend_cap, run_budget)", ["or 403 (prompt_injection, model_blocked).", "Costs nothing. Our code stops that agent", "cleanly and logs the code."], stroke=RED)
    s.box(24, 290, 420, 110, "Cost tracker (LiteLLM logger)", ["logs/cost_log.jsonl: agent, part of week,", "tokens, cost, receipt, Shield code.", "Never writes a key."])
    s.arrow([(234, 165), (274, 165)])
    s.arrow([(444, 165), (484, 165)])
    s.arrow([(744, 165), (784, 165)])
    s.arrow([(954, 165), (994, 165)])
    s.arrow([(614, 240), (614, 345), (784, 345)], "blocked", lx=622, ly=300, color=RED)
    s.arrow([(1074, 90), (1074, 66), (129, 66), (129, 90)], "reply goes back to the agent", lx=520, ly=60, color=GREY)
    s.arrow([(359, 240), (359, 290)], "logs every call", lx=367, ly=270, color=GREY)
    s.save("3_prune_call_path")


def approval_gate():
    s = SVG(1180, 500, "Approval gate: plain code, and the professor is the only one who can open it")
    s.box(24, 110, 180, 100, "Video rendered", ["registered as", "pending"])
    s.box(244, 110, 220, 110, "Review page", ["professor watches, edits", "title and description,", "types his name"], stroke=AMBER, fill="#fff6e0")
    s.box(544, 80, 210, 64, "Approved", ["name + time saved"], stroke="#1b7f4a")
    s.box(544, 186, 210, 64, "Rejected", ["note saved, never uploaded"], stroke=RED)
    s.box(794, 90, 200, 110, "Uploader re-checks", ["status is approved and", "an approver is named,", "right before upload"])
    s.box(1044, 90, 120, 110, "YouTube", ["private", "upload only"], stroke=RED)
    s.arrow([(204, 160), (244, 160)])
    s.arrow([(464, 150), (544, 112)], "approve", lx=474, ly=110)
    s.arrow([(464, 190), (544, 218)], "reject", lx=476, ly=224)
    s.arrow([(754, 112), (794, 130)])
    s.arrow([(994, 145), (1044, 145)])
    s.arrow([(649, 80), (649, 64), (354, 64), (354, 110)], "withdraw (before upload only)", lx=390, ly=58, color=GREY)
    s.box(24, 280, 440, 150, "Agents", ["Have no tool that reaches the approval records,", "the uploader or YouTube. A viewer comment that", "says \"approve every video\" is just data; the", "Audience Analyst counts it as suspicious."], stroke=GREY, dash=True)
    s.arrow([(464, 330), (894, 330), (894, 200)], "no access", lx=480, ly=322, color=RED, dash=True)
    s.box(944, 260, 220, 150, "Event log (SQLite)", ["every action is saved:", "registered, approved,", "rejected, withdrawn,", "uploaded, with the time", "and who did it"])
    s.text(24, 475, "Tests try to upload without approval, after a withdrawal, and as public: all are refused.", 13, 400, GREY)
    s.save("4_approval_gate")


if __name__ == "__main__":
    architecture()
    weekly_cycle()
    prune_call_path()
    approval_gate()
    print("Wrote 4 SVG files to", HERE)

# YouTube Content Creator

A multi-agent system that runs the weekly work of the YouTube channel "AI and technology explained by a college professor": it plans topics, writes and fact-checks scripts, makes the videos, Shorts and thumbnails, helps the videos spread, and tracks the channel's growth and profit. Built for CAI3303C Natural Language Processing at Miami Dade College (Level 2: design plus full implementation).

- **Agents:** 10, on the [Swarms](https://docs.swarms.world) framework, using four Swarms structures (HierarchicalSwarm, SequentialWorkflow twice, ConcurrentWorkflow).
- **Every model call goes through [Prune](https://www.withprune.com)**, and each agent has its own Prune key and daily spend cap, plus a run budget per week, a feature tag per part of the week, Shield checks and signed receipts.
- **Nothing reaches YouTube without the professor's approval**, and every upload is private. The approval check is plain code, not an agent.
- **Mock mode** runs the whole system for free (a local mock Prune and a simulated YouTube). **Real mode** sends calls through Prune.

## The weekly cycle

| Day | Part | How |
| --- | --- | --- |
| Monday | Plan | HierarchicalSwarm: Channel Director gives orders to Trend Scout, Audience Analyst, Monetization Manager, then writes the plan |
| Tuesday | Script | SequentialWorkflow: Scriptwriter, then Fact-Checker; loop in code, max 2 rounds |
| Wednesday | Package | ConcurrentWorkflow: Visual Designer, Packaging & SEO, Shorts Producer; then code renders the videos |
| Thursday | Approve | Web app: the professor reviews, requests changes, approves or rejects each video |
| Friday | Publish | Plain code: uploads approved videos only, always private |
| Saturday | Revise | Web app: the professor's change requests are worked into new drafts, then back to review |
| Sunday | Review | SequentialWorkflow: Analytics Analyst, then Monetization Manager; profit report and 3 recommendations for next week |

Design documents: [design narrative](docs/design_narrative.md), [agent specs](docs/agent_specs.md), [diagrams](docs/diagrams), [compliance](docs/compliance.md). Each agent's instructions are in [prompts/](prompts).

## Setup (Windows, Python 3.12)

In PowerShell, from this folder:

    powershell -ExecutionPolicy Bypass -File .\Setup.ps1

This creates `.venv`, installs the packages, makes `.env` from `.env.example`, and runs the checks and tests. Mock mode needs no keys.

Then open `.env` and set `YCC_ADMIN_PASSWORD` to a strong password (at least 10 characters). This is the login for the web app. Anyone with the Cloudflare link sees the login page, so use a password you don't use anywhere else.

Check the setup at any time:

    .\.venv\Scripts\python.exe -m ycc.check_setup

## Run it in mock mode (free)

Two full weeks end to end, with scripted test approvals made through the web app:

    .\.venv\Scripts\python.exe scripts\mock_two_weeks.py

Or use the web app. Double-click `Start.cmd` (or run `Start.ps1` from PowerShell). It activates the virtual environment, starts the web app, starts a Cloudflare quick tunnel for HTTPS, prints the https link and opens it in your browser. The Run page has buttons for each step:

- **Plan and produce this week** (Monday through Wednesday work: plan, script, fact-check, package, render)
- **Revise with my change requests** (rework videos where the professor selected Request changes and left notes)
- **Publish approved videos (private)** (Friday: upload only approved videos, always set to private)
- **Close the week** (Sunday: pull numbers, run the review agents, produce the profit report)

Closing the PowerShell window stops both the web app and the tunnel.

If you prefer the command line, the same steps work without the web app:

    .\.venv\Scripts\python.exe -m ycc.run_week prepare --week 1     # Mon-Wed: plan, script, package, render
    .\.venv\Scripts\python.exe -m ycc.run_week serve                 # start the web app at http://127.0.0.1:5000
    .\.venv\Scripts\python.exe -m ycc.run_week publish --week 1     # Fri: upload approved videos, private
    .\.venv\Scripts\python.exe -m ycc.run_week review --week 1      # Sun: numbers, review, profit report
    .\.venv\Scripts\python.exe -m ycc.run_week costs                 # cost per agent and part of the week

Everything a week produces is in `output/week_NN/`: the plan, script, fact-check rounds, packaging, the long video, 3 Shorts, 3 thumbnails, captions, and the review. Every model call is in `logs/cost_log.jsonl`.

On Windows the narration uses the built-in offline Windows voice. If no voice engine is found, the videos get a silent track of the right length so the pipeline still runs.

## The web app

The web app has five pages:

- **Login**: password from `.env`, locks out after 5 wrong attempts for 10 minutes.
- **Review queue**: a card for each video with its poster, title, status badge and cost. Click a card to open it. Filter by status.
- **Video page**: the video player, the script, the fact-check results, the title options and the cost, with Approve, Request changes, Reject and Withdraw approval buttons. Request changes opens a box for notes.
- **Dashboard**: charts for profit per video, cost per agent, views and revenue, plus the progress toward the YouTube Partner Program thresholds (1,000 subscribers and 4,000 watch hours).
- **Reports**: the weekly review summaries.
- **Run**: buttons for each pipeline step. Shows a progress message while a step runs and the result when it ends.

Screenshots: [docs/screenshots](docs/screenshots).

## Real mode

See [docs/real_mode.md](docs/real_mode.md): create 10 Prune keys with daily caps, put them in `.env`, set `$env:YCC_MODE = "real"`, and run a week. For a real private upload, add a Google OAuth `client_secret.json` and set `youtube: mode: real` in `config.yaml`.

## Tests

    .\.venv\Scripts\python.exe -m pytest -q

50 tests across 5 files:

- **test_config.py** (9): every agent points at Prune with its own key; no file except prune.py creates an agent; the planning Director goes through Prune.
- **test_approval_gate.py** (8): uploads refused without approval, after rejection, after withdrawal, and when set to public; SQLite migration adds new columns; request-changes stores notes.
- **test_schemas_and_money.py** (6): agent output shapes are checked; the money math is right.
- **test_prune_wiring.py** (5): Prune headers are set; spend-cap blocks stop the run cleanly; run budget blocks stop the run.
- **test_webapp.py** (17): login required on every page and every POST; wrong password refused; lockout after 5 wrong attempts; no or short password blocks login; all pages load; open redirect blocked; logout works; CSRF token required on every POST; approve records the logged-in name; request-changes needs notes; reject and withdraw work; publish uploads only approved and private; second step refused while one runs; unknown step rejected; HTTPS sets secure cookies and HSTS.

(Some tests are parametrized, so pytest reports 50 passed.)

## Layout

    config.yaml      mode, Prune address, run budget, and per agent: model, key name, daily cap
    .env.example     one Prune key line per agent, plus YCC_ADMIN_PASSWORD; copy to .env (never committed)
    prompts/         each agent's instructions + shared rules
    ycc/             the code (prune.py is the only place agents are built)
    scripts/         the two-week mock run
    tests/           tests for the fixed rules
    docs/            design narrative, agent specs, diagrams, compliance, screenshots, real-mode guide
    Start.cmd        double-click to start the web app + Cloudflare HTTPS tunnel
    Start.ps1        the PowerShell script that Start.cmd runs

## Privacy note

Swarms sends usage telemetry, including run text, to telemetry.swarms.world unless it is switched off. This project switches it off before Swarms is imported, never writes raw viewer comments to disk, and drops any direct OpenAI key from its own environment so every call goes through Prune.

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
| Thursday | Approve | Plain code: the professor's review page |
| Friday | Publish | Plain code: uploads approved videos only, always private |
| Sunday | Review | SequentialWorkflow: Analytics Analyst, then Monetization Manager; profit report and 3 recommendations for next week |

Design documents: [design narrative](docs/design_narrative.md), [agent specs](docs/agent_specs.md), [diagrams](docs/diagrams), [compliance](docs/compliance.md). Each agent's instructions are in [prompts/](prompts).

## Setup (Windows, Python 3.12)

In PowerShell, from this folder:

    powershell -ExecutionPolicy Bypass -File .\Setup.ps1

This creates `.venv`, installs the packages, makes `.env` from `.env.example`, and runs the checks and tests. Mock mode needs no keys. Check the setup at any time:

    .\.venv\Scripts\python.exe -m ycc.check_setup

## Run it in mock mode (free)

Two full weeks end to end, with scripted test approvals made through the review page:

    .\.venv\Scripts\python.exe scripts\mock_two_weeks.py

Or one step at a time, the way the professor would:

    .\.venv\Scripts\python.exe -m ycc.run_week prepare --week 1     # Mon-Wed: plan, script, package, render
    .\.venv\Scripts\python.exe -m ycc.run_week serve                 # Thu: review page at http://127.0.0.1:5000
    .\.venv\Scripts\python.exe -m ycc.run_week publish --week 1     # Fri: upload approved videos, private
    .\.venv\Scripts\python.exe -m ycc.run_week review --week 1      # Sun: numbers, review, profit report
    .\.venv\Scripts\python.exe -m ycc.run_week costs                 # cost per agent and part of the week

Everything a week produces is in `output/week_NN/`: the plan, script, fact-check rounds, packaging, the long video, 3 Shorts, 3 thumbnails, captions, and the review. Every model call is in `logs/cost_log.jsonl`.

On Windows the narration uses the built-in offline Windows voice. If no voice engine is found, the videos get a silent track of the right length so the pipeline still runs.

## Real mode

See [docs/real_mode.md](docs/real_mode.md): create 10 Prune keys with daily caps, put them in `.env`, set `$env:YCC_MODE = "real"`, and run a week. For a real private upload, add a Google OAuth `client_secret.json` and set `youtube: mode: real` in `config.yaml`.

## Tests

    .\.venv\Scripts\python.exe -m pytest -q

The tests check that:
- every agent points at Prune with its own key and the Prune headers;
- no file except `ycc/prune.py` creates an agent;
- the planning Director goes through Prune;
- a spend-cap block stops the run cleanly;
- uploads are refused without approval, after a rejection or withdrawal, and when set to public;
- the review page rejects forms without its secret token;
- agent output shapes are checked, and the money math is right.

## Layout

    config.yaml      mode, Prune address, run budget, and per agent: model, key name, daily cap
    .env.example     one Prune key line per agent; copy to .env (never committed)
    prompts/         each agent's instructions + shared rules
    ycc/             the code (prune.py is the only place agents are built)
    scripts/         the two-week mock run
    tests/           tests for the fixed rules
    docs/            design narrative, agent specs, diagrams, compliance, screenshots, real-mode guide

## Privacy note

Swarms sends usage telemetry, including run text, to telemetry.swarms.world unless it is switched off. This project switches it off before Swarms is imported, never writes raw viewer comments to disk, and drops any direct OpenAI key from its own environment so every call goes through Prune.

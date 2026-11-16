# YouTube Content Creator

A multi-agent system that runs the weekly cycle for the YouTube channel "AI and technology explained by a college professor": it plans topics, writes and fact-checks scripts, makes the videos and Shorts, prepares titles and thumbnails for testing, and reports on growth and profit. Built for CAI3303C Natural Language Processing at Miami Dade College.

The agents run on the Swarms framework. Every model call goes through the Prune gateway (withprune.com), and each of the 10 agents has its own Prune key and daily spend cap. Nothing is uploaded to YouTube without the professor's approval, every upload is private, and that check is plain code, not an agent.

Status: project setup (Prompt 1 of 15). The full README comes with Prompt 15.

## Setup (Windows, Python 3.12)

In PowerShell, from this folder:

    powershell -ExecutionPolicy Bypass -File .\Setup.ps1

This creates the .venv, installs the packages, makes .env from .env.example, runs the checks and tests, and makes the first git commit. Mock mode needs no keys.

Check the setup at any time:

    .\.venv\Scripts\python.exe -m ycc.check_setup

## Layout

    config.yaml      mode (mock or real), Prune address, one entry per agent (model, key name, daily cap)
    .env.example     one Prune key line per agent; copy to .env (never committed)
    prompts/         each agent's instructions (Prompt 6)
    docs/            design narrative, agent specs, diagrams, compliance (Prompts 2 to 5)
    ycc/             the code
    tests/           tests for the fixed rules

## Privacy note

Swarms sends usage telemetry, including run text, to telemetry.swarms.world unless it is switched off. This project switches it off (SWARMS_TELEMETRY_ON=false) before Swarms is imported.

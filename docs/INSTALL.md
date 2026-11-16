# Installing and running YouTube Content Creator on a new computer

This guide walks you through setting up the project from scratch on a Windows PC and running the web app with a Cloudflare HTTPS tunnel so the professor can review videos from his phone.


## What you need before you start

1. Windows 10 or 11.

2. Python 3.12 from python.org. During the installer, check "Add python.exe to PATH" and "Use py launcher." You can confirm it's installed by opening PowerShell and typing:

       py -3.12 --version

3. Git from git-scm.com. The default installer options are fine.

4. cloudflared.exe, Cloudflare's tunnel client. Download the latest Windows release from https://github.com/cloudflare/cloudflared/releases (the file called cloudflared-windows-amd64.exe). Rename it to cloudflared.exe and put it somewhere you'll remember, for example G:\Tools\cloudflared.exe. No Cloudflare account is needed for a quick tunnel.

5. A code editor if you want to look at the source (VS Code, Notepad++, or anything you like). Not required just to run it.


## Step 1. Clone the repo

Open PowerShell and go to the folder where you want the project, then:

    git clone https://github.com/MCDR-Code/YouTube_Content_Creator.git
    cd YouTube_Content_Creator


## Step 2. Run the setup script

    powershell -ExecutionPolicy Bypass -File .\Setup.ps1

This does five things for you: creates a Python virtual environment (.venv), installs all the packages (Swarms, Flask, Waitress, Pillow and the rest), copies .env.example to .env, runs the setup check, and runs the tests. It takes a few minutes the first time because Swarms pulls in a lot of dependencies.

When it finishes you should see something like "50 passed" from the tests.

If Setup.ps1 fails on the Python step, make sure you installed Python 3.12 specifically (not 3.11 or 3.13) and that the py launcher is on your PATH.


## Step 3. Set the web app password

Open the .env file in any text editor. Find the line that says:

    YCC_ADMIN_PASSWORD=

Type a strong password after the equals sign, at least 10 characters. This is the login for the web app. Anyone with the Cloudflare link will see the login page, so pick something you don't use anywhere else. For example:

    YCC_ADMIN_PASSWORD=MyStr0ngP4ssword!

Save the file. The .env file is in .gitignore, so it never gets pushed to GitHub.


## Step 4. Tell Start.ps1 where cloudflared lives

Open Start.ps1 in a text editor. Near the top you'll see:

    $Cloudflared = "G:\Tools\cloudflared.exe"

Change that path to wherever you put cloudflared.exe on this computer. Save the file.


## Step 5. Start the app

Double-click Start.cmd.

A PowerShell window opens and does the following:
- Activates the Python virtual environment.
- Starts the web app on port 5000 (listening only on this PC, not the network).
- Starts a Cloudflare quick tunnel that gives you a temporary https link.
- Prints the link and opens it in your default browser.

The link looks like https://something-random.trycloudflare.com. It changes every time you start the tunnel. Copy it and send it to the professor so he can review from his phone.

Log in with the password you set in .env.

To stop everything, close the PowerShell window or press Ctrl+C inside it.


## Step 6. Try the mock run

Before spending money on real Prune calls, run the whole system for free in mock mode. With the app stopped (close the PowerShell window if it's open), run:

    .\.venv\Scripts\python.exe scripts\mock_two_weeks.py

This drives two full weeks of content through the pipeline and the web app automatically: plans topics, writes scripts, fact-checks them, makes videos, approves and rejects through the web app, publishes approved videos (to a fake YouTube), and runs the weekly review. It takes about a minute.

After it finishes, start the app again (double-click Start.cmd) and explore: the Review queue will have videos from both weeks, the Dashboard will show charts, and the Reports page will have the weekly summaries.


## What each page does

- Login: type the password from .env. After 5 wrong tries it locks you out for 10 minutes.
- Review queue: shows a card for each video with its poster image, title, a colored status badge, and cost. Click a card to open it. Use the filter at the top to show only pending, approved, uploaded, or rejected videos.
- Video page: the video player, the full script, fact-check results, the title options the SEO agent picked, and the cost. Four buttons at the bottom: Approve, Request changes (opens a box where you type notes about what to fix), Reject, and Withdraw approval (if you approved but changed your mind before it was uploaded).
- Run: a button for each pipeline step. Click one, it shows a progress message while the step runs, and the result when it finishes. Only one step can run at a time. The steps are:
  - Plan and produce this week: the Monday-through-Wednesday work.
  - Revise with my change requests: reworks videos where you clicked Request changes and left notes.
  - Publish approved videos (private): uploads only approved videos, always set to private.
  - Close the week: pulls analytics numbers and runs the review agents.
- Dashboard: charts for profit per video, cost per agent, views and revenue, and a progress bar toward the YouTube Partner Program thresholds (1,000 subscribers and 4,000 watch hours).
- Reports: the weekly review summaries the Analytics Analyst and Monetization Manager produce.


## Switching to real mode

Mock mode is the default. To use real Prune keys and real AI models:

1. Create 10 API keys in the Prune dashboard (withprune.com, under Connect > API Keys), one per agent. Set a daily spend cap on each one (the amounts in config.yaml are a starting point).

2. Paste each key into the matching line in .env:

       PRUNE_KEY_DIRECTOR=prune_abc123...
       PRUNE_KEY_TREND_SCOUT=prune_def456...

   and so on for all 10 agents.

3. Open config.yaml and change the first line from:

       mode: mock

   to:

       mode: real

4. Run the app normally (Start.cmd or the Run page). The agents now call real models through Prune instead of the local fake server.

See docs/real_mode.md for the full details, including how to set up a real YouTube upload with the Google API.


## If something goes wrong

- "No .venv found": you need to run Setup.ps1 first.
- "cloudflared.exe was not found": edit Start.ps1 and fix the $Cloudflared path.
- "Set YCC_ADMIN_PASSWORD in .env": open .env and add a password of at least 10 characters.
- "Port 5000 is already in use": close the other copy of the app first (close the other PowerShell window).
- "The web app did not start": check logs\webapp.err.log for the error.
- "Cloudflare did not give a link": check logs\cloudflared.log. Make sure your internet is working and cloudflared.exe is not blocked by your firewall or antivirus.
- Tests fail after a fresh clone: make sure you're using Python 3.12 (not 3.11 or 3.13) and that pip install finished without errors.
- The Cloudflare link stopped working: quick tunnel links are temporary. Close the window and start again to get a new one.


## Layout of the project

    Start.cmd          double-click to start the web app + Cloudflare tunnel
    Start.ps1          the PowerShell script Start.cmd runs
    Setup.ps1          one-time setup (venv, packages, .env, tests, git)
    config.yaml        mode (mock/real), Prune settings, agent models and spend caps
    .env               your passwords and Prune keys (never committed to git)
    .env.example       template for .env
    requirements.txt   Python packages
    ycc/               the application code
    prompts/           each agent's instructions
    scripts/           the two-week mock run script
    tests/             50 automated tests
    docs/              design narrative, agent specs, diagrams, compliance, screenshots
    output/            created at runtime: each week's videos, scripts, and reports
    logs/              created at runtime: cost logs, app logs, tunnel logs

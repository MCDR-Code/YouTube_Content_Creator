Real mode: what to set up (Prompts 13 and 14)

Real mode sends every model call through Prune and costs a few cents per week. YouTube can stay mocked (Prompt 13) or be real (Prompt 14). Nothing here changes the approval rule: uploads are always private and only after the professor approves.


Prompt 13: one real week through Prune

1. Sign in at withprune.com. Under Connect > Providers, save the OpenAI key in Prune's vault. It never goes in our .env.

2. Under Connect > API Keys, create 10 Prune keys, one per agent. Name them so they are easy to tell apart in the dashboard: ycc-director, ycc-trend-scout, ycc-audience, ycc-monetization, ycc-scriptwriter, ycc-fact-checker, ycc-visual, ycc-packaging, ycc-shorts, ycc-analytics. Copy each key when it is shown; Prune shows it only once.

3. For each key, set a daily spend cap in Shield: $1.00 for the Scriptwriter, $0.50 for the Director and Fact-Checker, $0.25 for the others (the same numbers as config.yaml). If the dashboard lets you, also allow only the model in config.yaml (gpt-4o-mini), so a key cannot be used for a more expensive model.

4. Put each key on its line in .env (PRUNE_KEY_DIRECTOR=prune_..., and so on). Check with:
   .\.venv\Scripts\python.exe -m ycc.check_setup
   with YCC_MODE set to real for that shell:  $env:YCC_MODE = "real"

5. Run one real week, with YouTube still mocked:
   $env:YCC_MODE = "real"
   .\.venv\Scripts\python.exe -m ycc.run_week prepare --week 1
   then approve on the review page (python -m ycc.run_week serve), then
   .\.venv\Scripts\python.exe -m ycc.run_week publish --week 1
   .\.venv\Scripts\python.exe -m ycc.run_week review --week 1

6. Save the proof in docs/proof/:
   logs/cost_log.jsonl (every call with agent, part of the week, cost and Prune's receipt; never a key),
   output/week_01/4_prepare_summary.json and 6_review.json,
   and screenshots of Prune's Requests page and spend per key. Prune's receipts can be checked at withprune.com/verify.

If a key hits its cap, the run stops cleanly with a message like "Prune blocked scriptwriter: spend_cap". Raise the cap in the dashboard only if the work was legitimate.


Prompt 14: one real private upload

1. In Google Cloud Console, create a project, enable "YouTube Data API v3", and create an OAuth client ID of type "Desktop app". Download it and save it as client_secret.json in the project folder (it is git-ignored).

2. In config.yaml set youtube: mode: real. Keep privacy_status: private.

3. Run publish for a week whose videos the professor approved. A browser window opens for the professor to sign in to his own Google account and allow uploads. The token is saved in tokens/ (git-ignored).

4. Check in YouTube Studio that the video is private. Uploads from a new, unverified Google Cloud project are locked to private by YouTube anyway, which matches our rule. Take a screenshot for docs/proof/.

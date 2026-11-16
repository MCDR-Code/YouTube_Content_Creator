"""Run the weekly cycle. Each step is also a button on the web app's Run page.

  python -m ycc.run_week prepare --week 1   Mon-Wed: plan, script + fact-check, package, render, wait for approval
  python -m ycc.run_week revise --week 1    redo script, packaging and videos with the professor's change requests
  python -m ycc.run_week serve              the web app at http://127.0.0.1:5000 (login required)
  python -m ycc.run_week publish --week 1   Fri: upload approved videos, always private
  python -m ycc.run_week review --week 1    Sun: close the week: numbers, review agents, profit report
  python -m ycc.run_week costs              cost per agent and per part of the week

Mode (mock or real) comes from config.yaml, or set YCC_MODE=real for one run.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from typing import Callable

import ycc  # noqa: F401
from ycc import approval, channel, media, mock_prune, money, schemas, uploader, workflows
from ycc.config import PROJECT_ROOT, Settings, load_settings
from ycc.prune import TRACKER, PruneBlocked, RunContext
from ycc.storage import load_json, save_json, week_dir

Log = Callable[[str], None]


def _start(s: Settings, week: int) -> RunContext:
    if s.mode == "mock":
        mock_prune.start(port=int(s.prune_mock_base_url.rsplit(":", 1)[1].split("/")[0]))
    ctx = RunContext(week=week)
    TRACKER.ctx = ctx
    return ctx


def _cost_summary(run_id: str) -> dict:
    TRACKER.flush()
    by_agent, by_phase, calls = collections.defaultdict(float), collections.defaultdict(float), 0
    flagged = 0
    for r in TRACKER.records:
        if r.get("run_id") != run_id:
            continue
        calls += 1
        by_agent[r["agent"]] += r.get("cost_usd") or 0
        by_phase[r["phase"]] += r.get("cost_usd") or 0
        flagged += 1 if r.get("shield_code") else 0
    return {"run_id": run_id, "calls": calls, "by_agent": {k: round(v, 6) for k, v in by_agent.items()},
            "by_phase": {k: round(v, 6) for k, v in by_phase.items()},
            "total_usd": round(sum(by_agent.values()), 6), "shield_flags": flagged}


def next_week() -> int:
    weeks = approval.list_weeks()
    return (max(weeks) + 1) if weeks else 1


def current_week() -> int:
    weeks = approval.list_weeks()
    return max(weeks) if weeks else 1


def _produce(s: Settings, ctx: RunContext, week: int, plan: schemas.WeeklyPlan, log: Log,
             professor_notes: list[str] | None = None) -> dict:
    """Script + fact-check, package, render, register videos. Shared by prepare and revise."""
    out = week_dir(week)
    log("Writing and fact-checking the script (SequentialWorkflow, max 2 rounds)...")
    scripted = workflows.write_script(s, ctx, plan, professor_notes)
    save_json(out / "2_script.json", scripted)
    rounds = ", ".join(r["verdict"] for r in scripted["rounds"])
    log(f"Fact-check rounds: {rounds}")

    log("Packaging: visuals, titles and Shorts at the same time (ConcurrentWorkflow)...")
    packed = workflows.package(s, ctx, plan, scripted["script"])
    save_json(out / "3_package.json", packed)

    log("Rendering the long video, 3 Shorts and 3 thumbnails (plain code)...")
    script, visual = scripted["script"].model_dump(), packed["visual"].model_dump()
    pk, shorts = packed["packaging"].model_dump(), packed["shorts"].model_dump()
    long_r = media.render_long(script, visual, out)
    thumbs = [str(media.draw_thumbnail(v["thumbnail_text"], out / f"thumbnail_{i + 1}.png", i)
                  .relative_to(PROJECT_ROOT)) for i, v in enumerate(pk["variants"])]
    chapters = media.chapter_lines(long_r["chapters"])
    description = pk["description"] + (("\n\nChapters\n" + chapters) if chapters else "")
    spots = [sec["professor_insert"] for sec in script["sections"]]
    return {"scripted": scripted, "packed": packed, "long": long_r, "thumbs": thumbs, "pk": pk,
            "shorts": shorts, "description": description, "spots": spots}


def _register(week: int, made: dict, costs: dict, log: Log) -> int:
    """Register the week's videos as pending. Each video carries its share of the agent cost."""
    out = week_dir(week)
    by_agent = costs.get("by_agent", {})
    shorts_cost = by_agent.get("shorts_producer", 0.0)
    long_cost = round(sum(by_agent.values()) - shorts_cost, 6)
    pk, passed = made["pk"], made["scripted"]["passed"]
    n = 0
    n += approval.register_video({
        "id": f"w{week:02d}_long", "week": week, "kind": "long",
        "path": str(made["long"]["path"].relative_to(PROJECT_ROOT)), "thumbnails": made["thumbs"],
        "variants": pk["variants"], "title": pk["variants"][0]["title"], "description": made["description"],
        "tags": pk["tags"], "ai_disclosure": pk["ai_disclosure"], "made_for_kids": pk["made_for_kids"],
        "professor_spots": made["spots"], "fact_check_passed": passed,
        "poster": made["thumbs"][0], "cost_usd": long_cost})
    for i, sh in enumerate(made["shorts"]["shorts"], 1):
        r = media.render_short(sh, out, i)
        n += approval.register_video({
            "id": f"w{week:02d}_short{i}", "week": week, "kind": "short",
            "path": str(r["path"].relative_to(PROJECT_ROOT)), "thumbnails": [], "variants": [],
            "title": sh["title"], "description": sh["hook"] + "\n\nFull video on the channel. #Shorts",
            "tags": pk["tags"][:5], "ai_disclosure": pk["ai_disclosure"], "made_for_kids": False,
            "professor_spots": [], "fact_check_passed": passed,
            "poster": str(r["poster"].relative_to(PROJECT_ROOT)), "cost_usd": round(shorts_cost / 3, 6)})
    log(f"{n} video(s) are waiting for the professor's review.")
    return n


def prepare(week: int, s: Settings | None = None, log: Log = print) -> dict:
    s = s or load_settings()
    ctx = _start(s, week)
    out = week_dir(week)
    state = channel.load_state()
    comments = channel.comments_for_week(week, state)
    inputs = {"week": week, "covered_topics": state["covered_topics"],
              "last_week_recommendations": state.get("last_recommendations", []),
              "last_week_numbers": state["weeks"].get(str(week - 1), {})}
    log(f"[{s.mode}] Week {week}: planning (HierarchicalSwarm)...")
    planned = workflows.plan_week(s, ctx, inputs, comments)
    save_json(out / "1_plan.json", planned)
    log(f"Topic: {planned['plan'].long_video.topic}")

    made = _produce(s, ctx, week, planned["plan"], log)
    costs = _cost_summary(ctx.run_id)
    _register(week, made, costs, log)
    summary = {"week": week, "mode": s.mode, "topic": planned["plan"].long_video.topic,
               "fact_check_rounds": made["scripted"]["rounds"], "fact_check_passed": made["scripted"]["passed"],
               "long_video_seconds": made["long"]["seconds"], "voice_engine": made["long"]["voice"],
               "videos_waiting_for_approval": sum(1 for v in approval.list_week(week) if v["status"] == "pending"),
               "suspicious_comments": planned["audience"].suspicious_comments, "costs": costs, "revisions": []}
    save_json(out / "4_prepare_summary.json", summary)
    log(f"Done. Agent cost this run: ${costs['total_usd']:.4f} over {costs['calls']} calls.")
    return summary


def revise(week: int, s: Settings | None = None, log: Log = print) -> dict:
    """Redo the week's script, packaging and videos using the professor's change requests.
    Videos already uploaded are never touched. Every other video goes back to pending."""
    s = s or load_settings()
    vids = approval.list_week(week)
    notes = [f"{v['id']}: {v['changes_note']}" for v in vids if v["status"] == "changes_requested" and v["changes_note"]]
    if not notes:
        log(f"Week {week} has no change requests. Nothing to revise.")
        return {"week": week, "revised": False}
    ctx = _start(s, week)
    out = week_dir(week)
    planned = load_json(out / "1_plan.json")
    plan = schemas.WeeklyPlan(**planned["plan"])
    log(f"[{s.mode}] Week {week}: revising with {len(notes)} change request(s) from the professor...")
    made = _produce(s, ctx, week, plan, log, professor_notes=notes)
    costs = _cost_summary(ctx.run_id)
    _register(week, made, costs, log)
    summary = load_json(out / "4_prepare_summary.json", {})
    prev = summary.get("costs", {"by_agent": {}, "by_phase": {}, "total_usd": 0, "calls": 0})
    for k, v in costs["by_agent"].items():
        prev["by_agent"][k] = round(prev["by_agent"].get(k, 0) + v, 6)
    prev["total_usd"] = round(prev.get("total_usd", 0) + costs["total_usd"], 6)
    prev["calls"] = prev.get("calls", 0) + costs["calls"]
    summary.update({"costs": prev, "fact_check_rounds": made["scripted"]["rounds"],
                    "fact_check_passed": made["scripted"]["passed"]})
    summary.setdefault("revisions", []).append({"notes": notes, "cost_usd": costs["total_usd"]})
    save_json(out / "4_prepare_summary.json", summary)
    log(f"Done. Revision cost: ${costs['total_usd']:.4f}. The videos are back in the review queue.")
    return {"week": week, "revised": True, "notes": notes, "costs": costs}


def publish(week: int, s: Settings | None = None, log: Log = print) -> list[dict]:
    """Uploads approved videos only, always private. The approval check is uploader.upload -> approval.require_approved."""
    s = s or load_settings()
    log(f"Week {week}: uploading approved videos as private...")
    results = uploader.upload_approved(week, uploader.client(s))
    save_json(week_dir(week) / "5_publish.json", results)
    for r in results:
        log(f"  {r['id']}: " + (f"uploaded, private, YouTube id {r['youtube_id']}" if "youtube_id" in r
                                 else f"not uploaded ({r['skipped']})"))
    return results


def review(week: int, s: Settings | None = None, log: Log = print) -> dict:
    s = s or load_settings()
    ctx = _start(s, week)
    out = week_dir(week)
    planned = load_json(out / "1_plan.json")
    uploads = []
    for v in approval.list_week(week):
        if v["status"] == "uploaded":
            uploads.append({"id": v["id"], "kind": v["kind"], "variants": v["variants"], "title": v["title"]})
    if not uploads:
        log(f"Week {week} has no uploaded videos yet. Publish first, then close the week.")
        return {"week": week, "closed": False}
    state = channel.load_state()
    stats = channel.simulate_week(week, uploads, planned["plan"], planned["trends"], planned["audience"])
    state = channel.apply_week(state, stats, planned["plan"]["long_video"]["topic"])

    prep = load_json(out / "4_prepare_summary.json", {})
    week_costs = dict(prep.get("costs", {}).get("by_agent", {}))
    log(f"[{s.mode}] Week {week}: closing the week (SequentialWorkflow: Analytics, then Monetization)...")
    numbers_before = money.weekly_money(stats, week_costs, state=state)
    reviewed = workflows.review_week(s, ctx, stats, numbers_before)
    review_costs = _cost_summary(ctx.run_id)
    for agent, c in review_costs["by_agent"].items():
        week_costs[agent] = round(week_costs.get(agent, 0) + c, 6)
    numbers = money.weekly_money(stats, week_costs, state=state)
    per_video = money.per_video(stats, uploads, {v["id"]: v.get("cost_usd") or 0 for v in approval.list_week(week)})

    state["last_recommendations"] = reviewed["money"].recommendations
    channel.save_state(state)
    report = {"week": week, "stats": stats, "money": numbers, "per_video": per_video,
              "analytics_report": reviewed["analytics"], "money_report": reviewed["money"],
              "review_costs": review_costs}
    save_json(out / "6_review.json", report)
    log(f"Views {stats['views']:,}, new subscribers {stats['subs_gained']}, "
        f"estimated profit ${numbers['profit_usd']:.2f} (simulated numbers in mock mode).")
    for r in reviewed["money"].recommendations:
        log(f"  Next week: {r}")
    return report


def costs() -> dict:
    path = PROJECT_ROOT / "logs" / "cost_log.jsonl"
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    agg = collections.defaultdict(lambda: {"calls": 0, "cost_usd": 0.0})
    for r in rows:
        k = f"{r.get('week')}|{r.get('phase')}|{r.get('agent')}"
        agg[k]["calls"] += 1
        agg[k]["cost_usd"] = round(agg[k]["cost_usd"] + (r.get("cost_usd") or 0), 6)
    for k, v in sorted(agg.items()):
        print(f"{k:<45} {v['calls']:>3} calls  ${v['cost_usd']:.6f}")
    return agg


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m ycc.run_week")
    p.add_argument("step", choices=["prepare", "revise", "publish", "review", "serve", "costs"])
    p.add_argument("--week", type=int, default=None)
    p.add_argument("--port", type=int, default=5000)
    a = p.parse_args(argv)
    try:
        if a.step == "prepare":
            prepare(a.week or next_week())
        elif a.step == "revise":
            revise(a.week or current_week())
        elif a.step == "publish":
            publish(a.week or current_week())
        elif a.step == "review":
            review(a.week or current_week())
        elif a.step == "costs":
            costs()
        else:
            from ycc.webapp import serve
            serve(a.port)
    except PruneBlocked as e:
        print(f"\nStopped cleanly: {e}\nCheck the Prune dashboard (Activity) and raise the cap if the work was legitimate.")
        return 2
    except approval.NotApproved as e:
        print(f"\nUpload refused: {e}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

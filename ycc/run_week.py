"""Run the weekly cycle.

  python -m ycc.run_week prepare --week 1   Mon-Wed: plan, script + fact-check, package, render, wait for approval
  python -m ycc.run_week serve              Thu: open the review page at http://127.0.0.1:5000
  python -m ycc.run_week publish --week 1   Fri: upload approved videos, always private
  python -m ycc.run_week review --week 1    Sun: numbers, review agents, profit report
  python -m ycc.run_week costs              cost per agent and per part of the week

Mode (mock or real) comes from config.yaml, or set YCC_MODE=real for one run.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys

import ycc  # noqa: F401
from ycc import approval, channel, media, mock_prune, money, uploader, workflows
from ycc.config import PROJECT_ROOT, Settings, load_settings
from ycc.prune import TRACKER, PruneBlocked, RunContext
from ycc.storage import load_json, save_json, week_dir


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


def prepare(week: int, s: Settings | None = None) -> dict:
    s = s or load_settings()
    ctx = _start(s, week)
    out = week_dir(week)
    state = channel.load_state()
    comments = channel.comments_for_week(week, state)
    inputs = {"week": week, "covered_topics": state["covered_topics"],
              "last_week_recommendations": state.get("last_recommendations", []),
              "last_week_numbers": state["weeks"].get(str(week - 1), {})}
    print(f"[{s.mode}] Week {week}: planning (HierarchicalSwarm)...")
    planned = workflows.plan_week(s, ctx, inputs, comments)
    save_json(out / "1_plan.json", planned)

    print("Writing and fact-checking the script (SequentialWorkflow, max 2 rounds)...")
    scripted = workflows.write_script(s, ctx, planned["plan"])
    save_json(out / "2_script.json", scripted)

    print("Packaging (ConcurrentWorkflow)...")
    packed = workflows.package(s, ctx, planned["plan"], scripted["script"])
    save_json(out / "3_package.json", packed)

    print("Rendering video files (plain code)...")
    script, visual = scripted["script"].model_dump(), packed["visual"].model_dump()
    pk, shorts = packed["packaging"].model_dump(), packed["shorts"].model_dump()
    long_r = media.render_long(script, visual, out)
    thumbs = [str(media.draw_thumbnail(v["thumbnail_text"], out / f"thumbnail_{i + 1}.png", i)
                  .relative_to(PROJECT_ROOT)) for i, v in enumerate(pk["variants"])]
    chapters = media.chapter_lines(long_r["chapters"])
    description = pk["description"] + (("\n\nChapters\n" + chapters) if chapters else "")
    spots = [sec["professor_insert"] for sec in script["sections"]]
    approval.register_video({
        "id": f"w{week:02d}_long", "week": week, "kind": "long",
        "path": str(long_r["path"].relative_to(PROJECT_ROOT)), "thumbnails": thumbs, "variants": pk["variants"],
        "title": pk["variants"][0]["title"], "description": description, "tags": pk["tags"],
        "ai_disclosure": pk["ai_disclosure"], "made_for_kids": pk["made_for_kids"], "professor_spots": spots,
        "fact_check_passed": scripted["passed"]})
    for i, sh in enumerate(shorts["shorts"], 1):
        r = media.render_short(sh, out, i)
        approval.register_video({
            "id": f"w{week:02d}_short{i}", "week": week, "kind": "short",
            "path": str(r["path"].relative_to(PROJECT_ROOT)), "thumbnails": [], "variants": [],
            "title": sh["title"], "description": sh["hook"] + "\n\nFull video on the channel. #Shorts",
            "tags": pk["tags"][:5], "ai_disclosure": pk["ai_disclosure"], "made_for_kids": False,
            "professor_spots": [], "fact_check_passed": scripted["passed"]})

    costs = _cost_summary(ctx.run_id)
    summary = {"week": week, "mode": s.mode, "topic": planned["plan"].long_video.topic,
               "fact_check_rounds": scripted["rounds"], "fact_check_passed": scripted["passed"],
               "long_video_seconds": long_r["seconds"], "voice_engine": long_r["voice"],
               "videos_waiting_for_approval": len(approval.list_week(week)),
               "suspicious_comments": planned["audience"].suspicious_comments, "costs": costs}
    save_json(out / "4_prepare_summary.json", summary)
    print(json.dumps(summary, indent=2))
    print("\nNext: the professor reviews and approves on the review page:  python -m ycc.run_week serve")
    return summary


def publish(week: int, s: Settings | None = None) -> list[dict]:
    s = s or load_settings()
    results = uploader.upload_approved(week, uploader.client(s))
    save_json(week_dir(week) / "5_publish.json", results)
    print(json.dumps(results, indent=2))
    return results


def review(week: int, s: Settings | None = None) -> dict:
    s = s or load_settings()
    ctx = _start(s, week)
    out = week_dir(week)
    planned = load_json(out / "1_plan.json")
    uploads = []
    for v in approval.list_week(week):
        if v["status"] == "uploaded":
            uploads.append({"kind": v["kind"], "variants": v["variants"], "title": v["title"]})
    state = channel.load_state()
    stats = channel.simulate_week(week, uploads, planned["plan"], planned["trends"], planned["audience"])
    state = channel.apply_week(state, stats, planned["plan"]["long_video"]["topic"])

    prep = load_json(out / "4_prepare_summary.json", {})
    week_costs = dict(prep.get("costs", {}).get("by_agent", {}))
    print(f"[{s.mode}] Week {week}: review (SequentialWorkflow)...")
    numbers_before = money.weekly_money(stats, week_costs, state=state)
    reviewed = workflows.review_week(s, ctx, stats, numbers_before)
    review_costs = _cost_summary(ctx.run_id)
    for agent, c in review_costs["by_agent"].items():
        week_costs[agent] = round(week_costs.get(agent, 0) + c, 6)
    numbers = money.weekly_money(stats, week_costs, state=state)

    state["last_recommendations"] = reviewed["money"].recommendations
    channel.save_state(state)
    report = {"week": week, "stats": stats, "money": numbers, "analytics_report": reviewed["analytics"],
              "money_report": reviewed["money"], "review_costs": review_costs}
    save_json(out / "6_review.json", report)
    print(json.dumps({"views": stats["views"], "subs_gained": stats["subs_gained"],
                      "profit_usd": numbers["profit_usd"], "prune_cost_usd": numbers["costs_usd"]["prune_total"],
                      "recommendations": reviewed["money"].recommendations}, indent=2))
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
    p.add_argument("step", choices=["prepare", "publish", "review", "serve", "costs"])
    p.add_argument("--week", type=int, default=1)
    a = p.parse_args(argv)
    try:
        if a.step == "prepare":
            prepare(a.week)
        elif a.step == "publish":
            publish(a.week)
        elif a.step == "review":
            review(a.week)
        elif a.step == "costs":
            costs()
        else:
            from ycc.webapp import serve
            serve()
    except PruneBlocked as e:
        print(f"\nStopped cleanly: {e}\nCheck the Prune dashboard (Activity) and raise the cap if the work was legitimate.")
        return 2
    except approval.NotApproved as e:
        print(f"\nUpload refused: {e}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

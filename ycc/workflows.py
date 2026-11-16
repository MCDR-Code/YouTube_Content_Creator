"""The four agent parts of the week, each built on a Swarms structure.

  Plan    (Monday)    HierarchicalSwarm: Director gives orders to 3 helpers, then writes the plan
  Script  (Tuesday)   SequentialWorkflow: Scriptwriter -> Fact-Checker, at most 2 rounds (loop in code)
  Package (Wednesday) ConcurrentWorkflow: Visual Designer, Packaging & SEO, Shorts Producer at once
  Review  (Sunday)    SequentialWorkflow: Analytics Analyst -> Monetization Manager

Approve (Thursday) and Publish (Friday) are plain code in approval.py and uploader.py.
"""
from __future__ import annotations

from swarms import ConcurrentWorkflow, HierarchicalSwarm, SequentialWorkflow

from ycc import schemas
from ycc.agents import (BadAgentOutput, check, make, outputs_by_role, run_checked, run_structure,
                        system_prompt, wrap_input)
from ycc.config import Settings
from ycc.prune import RunContext, check_agent_uses_prune, prune_settings, reset_async_logger

MAX_SCRIPT_ROUNDS = 2


def _checked_or_rerun(raw: str | None, agent, task: str, schema):
    """Use the structure's output if it matches the shape; otherwise run that agent alone (one retry)."""
    if raw:
        try:
            return check(raw, schema, agent.agent_name)
        except BadAgentOutput:
            pass
    return run_checked(agent, task, schema)


# ---------------- Monday: plan ----------------
def plan_week(s: Settings, ctx: RunContext, inputs: dict, comments: list[str]) -> dict:
    ctx.phase = "plan"
    trend = make(s, "trend_scout", ctx)
    audience = make(s, "audience_analyst", ctx)
    money = make(s, "monetization_manager", ctx)

    director_cfg = prune_settings(s, "director", ctx)
    swarm = HierarchicalSwarm(
        name="Weekly planning",
        description="The Channel Director gives orders to the research helpers.",
        agents=[trend, audience, money],
        director_name="Channel Director",
        director_model_name=director_cfg.pop("model_name"),
        director_system_prompt=system_prompt(s, "director"),
        director_settings=director_cfg,
        max_loops=1,
        planning_enabled=False,      # would create an extra helper agent outside Prune
        director_feedback_on=False,  # same
        output_type="dict",
        autosave=False,              # never write the conversation (it holds viewer comments) to disk
    )
    check_agent_uses_prune(swarm.director, s)
    for a in (trend, audience, money):
        check_agent_uses_prune(a, s)

    task = (f"Plan week {ctx.week} for the channel. Each helper: use the data below.\n"
            + wrap_input(inputs, comments))
    convo = run_structure(swarm, task)
    out = outputs_by_role(convo if isinstance(convo, list) else [])

    reports = {
        "trends": _checked_or_rerun(out.get(trend.agent_name), trend, task, schemas.TrendReport),
        "audience": _checked_or_rerun(out.get(audience.agent_name), audience, task, schemas.AudienceReport),
        "money_ideas": _checked_or_rerun(out.get(money.agent_name), money, task, schemas.MonetizationIdeas),
    }

    planner = make(s, "director", ctx, suffix=" (plan writer)")
    plan_input = {"week": ctx.week, "last_week_recommendations": inputs.get("last_week_recommendations", []),
                  "covered_topics": inputs.get("covered_topics", []),
                  **{k: v.model_dump() for k, v in reports.items()}}
    plan = run_checked(planner, f"Job B: write the plan for week {ctx.week}.\n" + wrap_input(plan_input),
                       schemas.WeeklyPlan)
    if plan.week != ctx.week:
        plan = plan.model_copy(update={"week": ctx.week})
    return {"plan": plan, **reports}


# ---------------- Tuesday: script ----------------
def write_script(s: Settings, ctx: RunContext, plan: schemas.WeeklyPlan) -> dict:
    ctx.phase = "script"
    rounds = []
    fixes: list[dict] = []
    script = check_result = None
    for rnd in range(1, MAX_SCRIPT_ROUNDS + 1):
        writer = make(s, "scriptwriter", ctx)
        checker = make(s, "fact_checker", ctx)
        flow = SequentialWorkflow(name="Script and fact-check", agents=[writer, checker],
                                  max_loops=1, output_type="dict")
        task = (f"Round {rnd}. Write the script for this plan"
                + (", applying every fix listed" if fixes else "") + ". The Fact-Checker then checks it.\n"
                + wrap_input({"plan": plan.model_dump(), "fixes": fixes, "round": rnd}))
        out = outputs_by_role(run_structure(flow, task))
        script = _checked_or_rerun(out.get(writer.agent_name), writer, task, schemas.Script)
        check_task = "Check this script.\n" + wrap_input({"script": script.model_dump()})
        check_result = _checked_or_rerun(out.get(checker.agent_name), checker, check_task, schemas.FactCheck)
        rounds.append({"round": rnd, "verdict": check_result.verdict,
                       "issues": [i.model_dump() for i in check_result.issues]})
        if check_result.verdict == "PASS":
            break
        fixes = [i.model_dump() for i in check_result.issues]
    return {"script": script, "fact_check": check_result, "rounds": rounds,
            "passed": check_result.verdict == "PASS"}


# ---------------- Wednesday: package ----------------
def package(s: Settings, ctx: RunContext, plan: schemas.WeeklyPlan, script: schemas.Script) -> dict:
    ctx.phase = "package"
    visual = make(s, "visual_designer", ctx)
    packer = make(s, "packaging_seo", ctx)
    shorts = make(s, "shorts_producer", ctx)
    reset_async_logger()
    flow = ConcurrentWorkflow(name="Packaging", agents=[visual, packer, shorts], output_type="dict")
    task = ("Prepare this checked script for publishing. Each agent does its own job.\n"
            + wrap_input({"plan": plan.model_dump(), "script": script.model_dump()}))
    out = outputs_by_role(run_structure(flow, task))
    return {
        "visual": _checked_or_rerun(out.get(visual.agent_name), visual, task, schemas.VisualPlan),
        "packaging": _checked_or_rerun(out.get(packer.agent_name), packer, task, schemas.Packaging),
        "shorts": _checked_or_rerun(out.get(shorts.agent_name), shorts, task, schemas.ShortsPlan),
    }


# ---------------- Sunday: review ----------------
def review_week(s: Settings, ctx: RunContext, stats: dict, money_numbers: dict) -> dict:
    ctx.phase = "review"
    analyst = make(s, "analytics_analyst", ctx)
    money = make(s, "monetization_manager", ctx, suffix=" (review)")
    flow = SequentialWorkflow(name="Weekly review", agents=[analyst, money], max_loops=1, output_type="dict")
    task = ("Weekly review. Analytics Analyst first, then Monetization Manager (Job B). "
            "All numbers below were calculated by code.\n"
            + wrap_input({"week": ctx.week, "stats": stats, "money": money_numbers}))
    out = outputs_by_role(run_structure(flow, task))
    analytics = _checked_or_rerun(out.get(analyst.agent_name), analyst, task, schemas.AnalyticsReport)
    money_task = task + "\n" + wrap_input({"analytics_report": analytics.model_dump()})
    report = _checked_or_rerun(out.get(money.agent_name), money, money_task, schemas.MoneyReport)
    return {"analytics": analytics, "money": report}

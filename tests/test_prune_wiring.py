"""Every model call goes through Prune, with the agent's own key, the right headers, and clean stops on blocks."""
import re
from pathlib import Path

import pytest

from ycc import mock_prune, schemas, workflows
from ycc.agents import make
from ycc.prune import PruneBlocked, RunContext, check_agent_uses_prune

ROOT = Path(__file__).resolve().parent.parent


def test_every_agent_points_at_prune_with_its_own_key(mock_settings):
    ctx = RunContext(week=99)
    keys = set()
    for agent_id in mock_settings.agents:
        a = make(mock_settings, agent_id, ctx)
        check_agent_uses_prune(a, mock_settings)
        assert a.llm_args["extra_headers"]["X-Prune-Run-Id"] == ctx.run_id
        assert "X-Prune-Run-Budget-Usd" in a.llm_args["extra_headers"]
        assert a.llm_args["extra_headers"]["X-Prune-Feature-Id"] == ctx.phase
        assert not a.tools, f"{a.agent_name} must have no tools (it cannot touch approvals or uploads)"
        keys.add(a.llm_api_key)
    assert len(keys) == len(mock_settings.agents)


def test_agents_are_only_built_in_prune_py():
    """No other module may create a Swarms Agent directly (that could skip Prune)."""
    for py in (ROOT / "ycc").glob("*.py"):
        if py.name == "prune.py":
            continue
        assert not re.search(r"\bAgent\(", py.read_text(encoding="utf-8")), f"{py.name} builds an Agent"


def test_planning_swarm_director_goes_through_prune(mock_settings):
    mock_prune.REQUESTS.clear()
    ctx = RunContext(week=2)
    out = workflows.plan_week(mock_settings, ctx, {"covered_topics": []},
                              ["Why does the chatbot forget what I said earlier?"])
    assert isinstance(out["plan"], schemas.WeeklyPlan) and out["plan"].week == 2
    agents = {r["agent"] for r in mock_prune.REQUESTS}
    assert agents == {"director", "trend_scout", "audience_analyst", "monetization_manager"}
    assert any(r["agent"] == "director" and r["has_tools"] for r in mock_prune.REQUESTS), "director gave orders"
    assert all(r["phase"] == "plan" and r["run_id"] == ctx.run_id for r in mock_prune.REQUESTS)


def test_spend_cap_stops_cleanly(mock_settings, monkeypatch):
    monkeypatch.setenv("YCC_MOCK_BLOCK", "scriptwriter:spend_cap")
    plan = schemas.WeeklyPlan(week=1, long_video=schemas.LongVideoPlan(
        topic="What is a context window?", angle="a", viewer_question="q", target_minutes=6, hook="h"),
        shorts=[schemas.ShortPlan(idea="i", hook="h")] * 3, money_notes="m", reasons="r")
    with pytest.raises(PruneBlocked) as e:
        workflows.write_script(mock_settings, RunContext(week=1), plan)
    assert e.value.code == "spend_cap"


def test_mock_prune_refuses_calls_without_prune_headers(mock_settings):
    import json
    import urllib.request
    req = urllib.request.Request(mock_settings.base_url + "/chat/completions",
                                 data=json.dumps({"model": "x", "messages": []}).encode(),
                                 headers={"Authorization": "Bearer prune_mock_scriptwriter",
                                          "Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 400

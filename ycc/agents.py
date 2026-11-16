"""Loads each agent's instructions from prompts/ and turns agent replies into checked data."""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from ycc.config import PROJECT_ROOT, Settings
from ycc.prune import PruneBlocked, RunContext, build_agent, find_block_code

SHARED_RULES = PROJECT_ROOT / "prompts" / "_shared_rules.md"


def system_prompt(settings: Settings, agent_id: str) -> str:
    own = (PROJECT_ROOT / settings.agents[agent_id].prompt).read_text(encoding="utf-8")
    return own.strip() + "\n\n" + SHARED_RULES.read_text(encoding="utf-8").strip()


def make(settings: Settings, agent_id: str, ctx: RunContext, suffix: str = "", **kw):
    return build_agent(settings, agent_id, ctx, system_prompt(settings, agent_id), suffix=suffix, **kw)


def wrap_input(data: dict, comments: list[str] | None = None) -> str:
    """Our standard way to hand data to an agent: JSON inside <input>, viewer text inside <comments>."""
    text = "<input>\n" + json.dumps(data, ensure_ascii=False) + "\n</input>"
    if comments is not None:
        safe = [re.sub(r"https?://\S+", "[link removed]", c)[:500] for c in comments]
        text += "\n<comments>\n" + "\n".join(f"- {c}" for c in safe) + "\n</comments>"
    return text


def parse_json(text: str) -> dict:
    """Find the JSON object in an agent reply (tolerates code fences or stray words)."""
    if isinstance(text, dict):
        return text
    text = str(text).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def check(raw, schema: type[BaseModel], agent_name: str) -> BaseModel:
    try:
        return schema.model_validate(parse_json(raw))
    except (ValidationError, json.JSONDecodeError, ValueError) as e:
        raise BadAgentOutput(agent_name, str(e)[:500], str(raw)[:500]) from e


class BadAgentOutput(RuntimeError):
    def __init__(self, agent_name: str, problem: str, raw: str):
        super().__init__(f"{agent_name} returned output that does not match its JSON shape: {problem}")
        self.agent_name, self.problem, self.raw = agent_name, problem, raw


def run_checked(agent, task: str, schema: type[BaseModel]) -> BaseModel:
    """Run one agent, check its JSON. One retry with the error message if the shape is wrong."""
    raw = _run(agent, task)
    try:
        return check(raw, schema, agent.agent_name)
    except BadAgentOutput as e:
        retry = (task + "\n\nYour last reply did not match the required JSON shape. Problem: "
                 + e.problem + "\nReply again with only the corrected JSON object.")
        return check(_run(agent, retry), schema, agent.agent_name)


def _run(agent, task: str):
    try:
        out = agent.run(task)
    except Exception as e:  # noqa: BLE001
        code = find_block_code(e)
        if code:
            raise PruneBlocked(getattr(agent, "ycc_agent_id", agent.agent_name), code, str(e)[:200]) from e
        raise
    code = find_block_code(out) if isinstance(out, str) and "error" in out.lower()[:200] else None
    if code:
        raise PruneBlocked(getattr(agent, "ycc_agent_id", agent.agent_name), code, str(out)[:200])
    return out


def run_structure(flow, task: str):
    """Run a Swarms structure; turn a Prune block anywhere inside it into a clean PruneBlocked."""
    try:
        return flow.run(task)
    except Exception as e:  # noqa: BLE001
        code = find_block_code(e)
        if code:
            m = re.search(r"Agent '([^']+)'", str(e))
            raise PruneBlocked(m.group(1) if m else "an agent", code, str(e)[:200]) from e
        raise


def outputs_by_role(conversation_dicts: list[dict]) -> dict[str, str]:
    """Last message per agent from a Swarms conversation in dict form."""
    out: dict[str, str] = {}
    for m in conversation_dicts:
        out[m.get("role", "")] = m.get("content", "")
    return out

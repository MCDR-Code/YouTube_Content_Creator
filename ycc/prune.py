"""Every Swarms agent is built here, and only here, so every model call goes through Prune.

Each agent gets:
  - llm_base_url = Prune (or the local mock Prune in mock mode)
  - llm_api_key  = that agent's own Prune key (own daily spend cap)
  - an openai/ model name (Prune speaks the OpenAI chat/completions format)
  - Prune headers: run ID + run budget for the week, and a feature tag for the part of the week

A LiteLLM callback records every call (agent, part of week, tokens, cost, Prune receipt and
Shield code) in logs/cost_log.jsonl. Keys are never written to the log.
"""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import ycc  # noqa: F401  (telemetry off + direct provider keys removed before Swarms loads)
from ycc.config import PROJECT_ROOT, Settings

PHASES = ("plan", "script", "package", "review")
BLOCK_CODES = (
    "spend_cap", "run_budget", "run_budget_missing_run_id", "rate_limit", "plan_limit", "free_trial_ended",
    "anomaly_spike", "token_budget", "agent_loop", "loop_detected", "agent_step_budget",
    "prompt_injection", "model_blocked", "provider_blocked", "tool_policy", "canary_leak",
)


class PruneBlocked(RuntimeError):
    """Prune refused a call (spend cap, run budget, Shield block...). Nothing was charged."""

    def __init__(self, agent_id: str, code: str, message: str):
        super().__init__(f"Prune blocked {agent_id}: {code}. {message}")
        self.agent_id = agent_id
        self.code = code


def find_block_code(error: BaseException | str) -> str | None:
    text = str(error)
    for code in BLOCK_CODES:
        if re.search(rf"\b{code}\b", text):
            return code
    return None


@dataclass
class RunContext:
    """One weekly run. The run ID and budget go to Prune on every call."""
    week: int
    run_id: str = ""
    phase: str = "plan"
    log_path: Path = field(default_factory=lambda: PROJECT_ROOT / "logs" / "cost_log.jsonl")

    def __post_init__(self):
        if not self.run_id:
            self.run_id = f"week-{self.week:02d}-{time.strftime('%Y%m%d-%H%M%S')}"


class CostTracker:
    """Collects one record per model call from LiteLLM's success/failure callbacks."""

    def __init__(self):
        self._lock = threading.Lock()
        self._key_to_agent: dict[str, str] = {}
        self.ctx: RunContext | None = None
        self.records: list[dict] = []
        self.started = 0
        self._installed = False

    def register(self, key: str, agent_id: str) -> None:
        self._key_to_agent[key] = agent_id

    def install(self) -> None:
        """Hook into LiteLLM for both normal and async calls (ConcurrentWorkflow uses async)."""
        if self._installed:
            return
        import litellm
        from litellm.integrations.custom_logger import CustomLogger

        tracker = self

        class _Logger(CustomLogger):
            def log_pre_api_call(self, model, messages, kwargs):
                tracker._on_start()

            def log_success_event(self, kwargs, response_obj, start_time, end_time):
                tracker._on_success(kwargs, response_obj, start_time, end_time)

            def log_failure_event(self, kwargs, response_obj, start_time, end_time):
                tracker._on_failure(kwargs, response_obj, start_time, end_time)

            async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
                tracker._on_success(kwargs, response_obj, start_time, end_time)

            async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
                tracker._on_failure(kwargs, response_obj, start_time, end_time)

        self._logger = _Logger()
        litellm.callbacks = [c for c in litellm.callbacks if not isinstance(c, CustomLogger)
                             or c.__class__.__name__ != "_Logger"] + [self._logger]
        self._installed = True

    def _on_start(self, *args, **kwargs):
        with self._lock:
            self.started += 1

    def flush(self, timeout: float = 15.0) -> None:
        """LiteLLM logs calls in the background. Wait until every started call has a record."""
        end = time.time() + timeout
        while time.time() < end:
            with self._lock:
                if len(self.records) >= self.started:
                    return
            time.sleep(0.1)

    def _base(self, kwargs) -> dict:
        key = kwargs.get("api_key") or (kwargs.get("litellm_params") or {}).get("api_key") or ""
        ctx = self.ctx
        return {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "run_id": ctx.run_id if ctx else None,
            "week": ctx.week if ctx else None,
            "phase": ctx.phase if ctx else None,
            "agent": self._key_to_agent.get(key, "UNKNOWN"),
            "model": kwargs.get("model"),
        }

    def _write(self, rec: dict) -> None:
        with self._lock:
            self.records.append(rec)
            path = self.ctx.log_path if self.ctx else PROJECT_ROOT / "logs" / "cost_log.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")

    def _on_success(self, kwargs, response, start, end):
        rec = self._base(kwargs)
        data = response.model_dump(warnings=False) if hasattr(response, "model_dump") else {}
        usage = data.get("usage") or {}
        meta = data.get("prune_metadata") or {}
        headers = {k.lower(): v for k, v in (kwargs.get("response_headers") or {}).items()} if isinstance(
            kwargs.get("response_headers"), dict) else {}
        rec.update({
            "ok": True,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "cost_usd": meta.get("cost_usd", meta.get("cost")),
            "cache_hit": meta.get("cache_hit"),
            "receipt": meta.get("receipt") or meta.get("signed_receipt"),
            "prune_metadata": meta,  # kept whole: it is the proof for the real run
            "shield_code": headers.get("x-prune-shield-code"),
            "provider": headers.get("x-prune-provider"),
            "seconds": round((end - start).total_seconds(), 2) if hasattr(end, "__sub__") else None,
        })
        self._write(rec)

    def _on_failure(self, kwargs, response, start, end):
        rec = self._base(kwargs)
        err = kwargs.get("exception") or response
        rec.update({"ok": False, "cost_usd": 0.0, "block_code": find_block_code(err), "error": str(err)[:300]})
        self._write(rec)

    def total_cost(self, run_id: str | None = None) -> float:
        return round(sum((r.get("cost_usd") or 0) for r in self.records
                         if run_id is None or r.get("run_id") == run_id), 6)


TRACKER = CostTracker()


def reset_async_logger() -> None:
    """LiteLLM's background logger stays tied to the first async event loop. ConcurrentWorkflow starts a
    new loop each run, so reset it first (avoids harmless but alarming 'different event loop' errors)."""
    try:
        from litellm.litellm_core_utils import logging_worker
        w = logging_worker.GLOBAL_LOGGING_WORKER
        w._queue, w._worker_task = None, None
    except Exception:  # noqa: BLE001
        pass


def prune_settings(settings: Settings, agent_id: str, ctx: RunContext) -> dict:
    """The Swarms Agent settings that route an agent's calls through Prune with its own key."""
    a = settings.agents[agent_id]
    key = settings.prune_key(agent_id)
    TRACKER.register(key, agent_id)
    TRACKER.install()
    TRACKER.ctx = ctx
    return {
        "model_name": a.model,
        "llm_base_url": settings.base_url,
        "llm_api_key": key,
        "llm_args": {"extra_headers": {
            "X-Prune-Run-Id": ctx.run_id,
            "X-Prune-Run-Budget-Usd": f"{settings.weekly_run_budget_usd:.2f}",
            "X-Prune-Feature-Id": ctx.phase,
            "X-Prune-Workload": "youtube-content-creator",
        }},
        "retry_attempts": 1,
        "print_on": False,
        "verbose": False,
    }


def build_agent(settings: Settings, agent_id: str, ctx: RunContext, system_prompt: str,
                suffix: str = "", **agent_kwargs):
    """Create a Swarms Agent wired to Prune with the agent's own key. The only place agents are made."""
    from swarms import Agent

    a = settings.agents[agent_id]
    agent = Agent(
        agent_name=a.name + suffix,
        agent_description=a.name,
        system_prompt=system_prompt,
        max_loops=1,
        temperature=0.4,
        output_type="final",
        autosave=False,
        **prune_settings(settings, agent_id, ctx),
        **agent_kwargs,
    )
    agent.ycc_agent_id = agent_id  # used by tests to prove where each agent points
    return agent


def check_agent_uses_prune(agent, settings: Settings) -> None:
    """Raise if an agent is not pointed at Prune with its own Prune key."""
    if agent.llm_base_url != settings.base_url:
        raise AssertionError(f"{agent.agent_name} is not pointed at Prune")
    if not str(agent.llm_api_key or "").startswith("prune_"):
        raise AssertionError(f"{agent.agent_name} has no Prune key")
    if not str(agent.model_name).startswith("openai/"):
        raise AssertionError(f"{agent.agent_name} model must use the openai/ route to Prune")

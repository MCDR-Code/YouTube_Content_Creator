"""Loads config.yaml and .env and answers: which mode, which agents, which Prune key and URL."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VALID_MODES = ("mock", "real")


@dataclass(frozen=True)
class AgentSettings:
    agent_id: str
    name: str
    key_env: str
    model: str
    daily_cap_usd: float
    prompt: str


@dataclass(frozen=True)
class Settings:
    mode: str
    prune_base_url: str
    prune_mock_base_url: str
    weekly_run_budget_usd: float
    youtube_mode: str
    privacy_status: str
    agents: dict[str, AgentSettings]

    @property
    def base_url(self) -> str:
        """The Prune address every agent uses in the current mode."""
        return self.prune_mock_base_url if self.mode == "mock" else self.prune_base_url

    def prune_key(self, agent_id: str) -> str:
        """The agent's own Prune key. Mock mode uses a fake key named after the agent."""
        agent = self.agents[agent_id]
        if self.mode == "mock":
            return f"prune_mock_{agent_id}"
        key = os.getenv(agent.key_env, "").strip()
        if not key:
            raise RuntimeError(f"{agent.key_env} is empty in .env (needed for {agent.name} in real mode).")
        if not key.startswith("prune_"):
            raise RuntimeError(f"{agent.key_env} does not look like a Prune key (it should start with prune_).")
        return key

    def missing_keys(self) -> list[str]:
        """Names of .env lines that are still empty (only matters in real mode)."""
        return [a.key_env for a in self.agents.values() if not os.getenv(a.key_env, "").strip()]


def load_settings(config_path: Path | str | None = None, env_path: Path | str | None = None) -> Settings:
    config_path = Path(config_path or PROJECT_ROOT / "config.yaml")
    load_dotenv(env_path or PROJECT_ROOT / ".env", override=False)
    os.environ["SWARMS_TELEMETRY_ON"] = "false"

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    mode = os.getenv("YCC_MODE", raw.get("mode", "mock")).strip().lower()
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, not {mode!r}")

    privacy = raw["youtube"]["privacy_status"]
    if privacy != "private":
        raise ValueError("youtube.privacy_status must be 'private'. Uploads are never public.")

    agents = {
        agent_id: AgentSettings(
            agent_id=agent_id,
            name=a["name"],
            key_env=a["key_env"],
            model=a["model"],
            daily_cap_usd=float(a["daily_cap_usd"]),
            prompt=a["prompt"],
        )
        for agent_id, a in raw["agents"].items()
    }
    return Settings(
        mode=mode,
        prune_base_url=raw["prune"]["base_url"],
        prune_mock_base_url=raw["prune"]["mock_base_url"],
        weekly_run_budget_usd=float(raw["prune"]["weekly_run_budget_usd"]),
        youtube_mode=raw["youtube"]["mode"],
        privacy_status=privacy,
        agents=agents,
    )

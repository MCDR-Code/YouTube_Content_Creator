"""Quick health check: python -m ycc.check_setup

Shows the Python and Swarms versions, the mode, and each agent's Prune key status
(set or empty, never the key itself).
"""
import os
import platform
import sys

import ycc  # noqa: F401  (switches Swarms telemetry off first)
from ycc.config import load_settings


def main() -> int:
    s = load_settings()
    print(f"Python      {platform.python_version()} ({sys.executable})")
    try:
        from importlib.metadata import version
        print(f"Swarms      {version('swarms')}")
    except Exception:
        print("Swarms      NOT INSTALLED")
    print(f"Mode        {s.mode}   (YouTube: {s.youtube_mode}, uploads: {s.privacy_status})")
    print(f"Prune URL   {s.base_url}")
    print(f"Telemetry   SWARMS_TELEMETRY_ON={os.environ.get('SWARMS_TELEMETRY_ON')}")
    print(f"Run budget  ${s.weekly_run_budget_usd:.2f} per weekly run")
    print("Agents:")
    for a in s.agents.values():
        status = "set" if os.getenv(a.key_env, "").strip() else "empty"
        print(f"  {a.name:<22} {a.key_env:<24} key {status:<6} cap ${a.daily_cap_usd:.2f}/day  {a.model}")
    if os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY is set. Calls must go through Prune, so remove it from this shell.")
    if s.mode == "real" and s.missing_keys():
        print("Real mode needs these .env lines filled in: " + ", ".join(s.missing_keys()))
        return 1
    print("Setup OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

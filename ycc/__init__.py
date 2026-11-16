"""YouTube Content Creator: a Swarms multi-agent system for a professor's YouTube channel.

Importing this package does two safety steps before Swarms is ever imported:
1. Switches off Swarms telemetry, which otherwise sends run text to telemetry.swarms.world.
2. Removes direct provider keys (OPENAI_API_KEY and similar) from this program's environment,
   so no model call can skip Prune by falling back to them. The Windows setting is not changed.
"""
import os

os.environ["SWARMS_TELEMETRY_ON"] = "false"

DIRECT_PROVIDER_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
)
REMOVED_PROVIDER_KEYS = [k for k in DIRECT_PROVIDER_KEYS if os.environ.pop(k, None) is not None]

__version__ = "0.1.0"

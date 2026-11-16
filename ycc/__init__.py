"""YouTube Content Creator: a Swarms multi-agent system for a professor's YouTube channel.

Importing this package switches off Swarms telemetry before Swarms itself is imported,
because Swarms sends run text to telemetry.swarms.world unless told not to.
"""
import os

os.environ["SWARMS_TELEMETRY_ON"] = "false"

__version__ = "0.1.0"

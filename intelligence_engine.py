"""
Intelligence Engine — Backward-Compatible Shim
================================================
This file has been refactored into the `intelligence/` package.
All public names are re-exported here so that existing imports
like `from intelligence_engine import SelfHealingLoop` continue to work.
"""

from intelligence import *  # noqa: F401, F403

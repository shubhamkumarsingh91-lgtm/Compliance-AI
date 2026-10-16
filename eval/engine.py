"""Thin re-export so the evaluation scripts keep working. The engine itself lives in compliance_agent/engine.py."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from compliance_agent.engine import *            # noqa: F401,F403
from compliance_agent.engine import run_engine, diff_policy, affected_sops, draft_sop   # noqa: F401

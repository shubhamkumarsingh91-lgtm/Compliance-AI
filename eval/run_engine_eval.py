"""Runs the rule-based engine on every case. Needs no GPU:  python3 run_engine_eval.py
Runs the 10 development cases (cases/) and the 8 blind cases (blind/, written after the rules were first built)."""
import pathlib
from score import run_eval, print_report
import engine
for name in ("cases", "blind"):
    print(f"\n===== {name} =====")
    out = run_eval(engine.run_engine, cases_dir=pathlib.Path(__file__).parent / name, repeats=1)
    print_report(out); print(out["summary"])

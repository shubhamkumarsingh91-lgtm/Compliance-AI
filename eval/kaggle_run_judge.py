"""Measures the language-model check with the REAL model on generated cases. Run in a Kaggle cell AFTER the model is loaded
(the notebooks define `model` and `tokenizer`):

    N = 300; SEED = 7; RUN_LABEL = "judge1"
    %run -i /kaggle/working/repo/eval/kaggle_run_judge.py

It prints pass rates by case type WITHOUT the judge (rules only) and WITH it, so the benefit (or harm) is visible, then saves
every judge answer so you can read what the model decided. The judge changes only flags, never text; 'unsure' changes nothing.
"""
import sys, json, pathlib
REPO = pathlib.Path("/kaggle/working/repo")
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "eval"))
for m in [k for k in sys.modules if k.startswith(("compliance_agent", "generate_cases", "score", "engine"))]:
    sys.modules.pop(m, None)                         # same stale-module protection as kaggle_run_eval.py
import generate_cases as gc
from compliance_agent.judge import HFJudge

N = globals().get("N", 300); SEED = globals().get("SEED", 7); RUN_LABEL = globals().get("RUN_LABEL", "judge")
judge = HFJudge(model=model, tokenizer=tokenizer, max_calls=100000)       # reuse the model already in memory
KINDS = {"added", "reword", "unrelated", "number", "removed"}

print("=== rules only ===");  base = gc.run(N, SEED, show=0, kinds=KINDS)
print("\n=== rules + language-model check ===")
withj = gc.run(N, SEED, show=6, judge_factory=lambda case: judge, kinds=KINDS)
print(f"\nPassed: rules only {base[0]}/{base[1]}   with judge {withj[0]}/{withj[1]}   (judge calls: {judge.calls})")
out = pathlib.Path(f"/kaggle/working/judge_answers_{RUN_LABEL}.json")
out.write_text(json.dumps(judge.log, indent=1))
print(f"Saved {len(judge.log)} judge answers to {out}. Download it and send it over.")

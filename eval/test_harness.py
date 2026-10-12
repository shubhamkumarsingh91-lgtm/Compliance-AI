"""Run: python3 test_harness.py   (checks that the scorer itself behaves)"""
from score import run_eval
from mock_pipelines import null_pipeline, flag_everything_pipeline, oracle_pipeline

o = run_eval(oracle_pipeline)["summary"]
assert o["passed"] == o["cases"] and o["avg_change_recall"] == 1 and o["errors"] == 0, o
n = run_eval(null_pipeline)
assert n["summary"]["passed"] == 1, n["summary"]            # only the no-change control passes
assert [r["case_id"] for r in n["cases"] if r["passed"]] == ["control_01_wording_only"]
f = run_eval(flag_everything_pipeline)
assert f["summary"]["passed"] == 0, f["summary"]            # over-flagging must fail every case
print("Scorer self-test passed: oracle 100%, 'do nothing' passes only the control, 'flag everything' fails all.")

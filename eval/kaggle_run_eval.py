# Disclaimer: Independent personal project. Public documents and synthetic data only.
# PASTE-IN CELL for Kaggle. Run AFTER your pipeline cells (starter, phase 3, phase 4, and both patches)
# so that detect_changes, run_full_compliance_check and new_clause_flags already exist.
# First, in its own cell:  !git clone https://github.com/shubhamkumarsingh91-lgtm/compliance-ai /kaggle/working/repo
# Runs every case twice: (A) whole-document comparison, (B) section-by-section comparison. Compare the two.
import sys, json
REPEATS = globals().get("REPEATS", 3)           # synthetic cases run this many times each (the model samples, so one run can be luck)
RUN_LABEL = globals().get("RUN_LABEL", "run")   # set RUN_LABEL = "v2" in a cell above to keep results from different runs apart
sys.path.insert(0, "/kaggle/working/repo/eval")
from score import run_eval, print_report
from sectioned import make_sectioned_detector

def real_pipeline(old_doc, new_doc, sops):
    result = run_full_compliance_check(old_doc, new_doc, sops)
    for d in result["drafted_updates"]:
        d["review_flags"] = new_clause_flags(d["original_text"], d["draft_text"])
    return result

_whole_doc_detect = detect_changes            # keep the original so we can restore it

# The real case cannot run whole-document (out of memory, seen twice), so it only runs in section mode below.
print("=== A) whole-document comparison ===")
out_a = run_eval(real_pipeline, out_path=f"/kaggle/working/eval_results_whole_{RUN_LABEL}.json", repeats=REPEATS)
print_report(out_a)

print("\n=== B) section-by-section comparison ===")
detect_changes = make_sectioned_detector(_whole_doc_detect)
try:
    out_b = run_eval(real_pipeline, out_path=f"/kaggle/working/eval_results_sectioned_{RUN_LABEL}.json", repeats=REPEATS)
finally:
    detect_changes = _whole_doc_detect         # always restore
print_report(out_b)

print("\nSUMMARY  whole-doc:", out_a["summary"])
print("SUMMARY  sectioned:", out_b["summary"])
print(f"Download eval_results_whole_{RUN_LABEL}.json and eval_results_sectioned_{RUN_LABEL}.json from /kaggle/working and send them over.")

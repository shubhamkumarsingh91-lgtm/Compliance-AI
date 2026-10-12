# Disclaimer: Independent personal project. Public documents and synthetic data only.
# PASTE-IN CELL for Kaggle. Run AFTER your pipeline cells (starter, phase 3, phase 4, and both patches)
# so that detect_changes, run_full_compliance_check and new_clause_flags already exist.
# Upload or clone this repo's eval/ folder first, e.g.:
#   !git clone https://github.com/shubhamkumarsingh91-lgtm/compliance-ai /kaggle/working/repo
import sys, json
sys.path.insert(0, "/kaggle/working/repo/eval")
from score import run_eval, print_report

def real_pipeline(old_doc, new_doc, sops):
    result = run_full_compliance_check(old_doc, new_doc, sops)
    for d in result["drafted_updates"]:
        d["review_flags"] = new_clause_flags(d["original_text"], d["draft_text"])
    return result

out = run_eval(real_pipeline, out_path="/kaggle/working/eval_results.json")
print_report(out)

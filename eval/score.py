"""Scoring harness for the compliance pipeline. No GPU needed.

A pipeline is any function: pipeline(old_doc, new_doc, sops) -> dict with
  changes_summary (str), affected_sop_ids (list), drafted_updates (list of
  {sop_id, draft_text, review_flags}).  That is what run_full_compliance_check returns.
"""
import json, re, pathlib

CASES_DIR = pathlib.Path(__file__).parent / "cases"


def _has(text, term):
    """term is a string, or a list meaning 'any of these'. Numbers match whole numbers only."""
    if isinstance(term, list):
        return any(_has(text, t) for t in term)
    pat = re.escape(term)
    if term.replace(".", "").isdigit():
        pat = r"(?<![\d.])" + pat + r"(?![\d])"
    return re.search(pat, text, re.I) is not None


def load_case(case_dir):
    d = pathlib.Path(case_dir)
    meta = json.loads((d / "case.json").read_text())
    mk = lambda name, ver, eff, cur: {
        "id": f"{meta['case_id']}_v{ver}", "title": f"{meta['policy_family']} v{ver}",
        "text": (d / name).read_text(),
        "metadata": {"policy_family": meta["policy_family"], "version": ver,
                     "effective_date": eff, "is_current": cur}}
    return dict(
        meta=meta,
        old=mk("old.txt", 1, meta["old_effective"], False),
        new=mk("new.txt", 2, meta["new_effective"], True),
        sops=json.loads((d / "sops.json").read_text()),
        key=json.loads((d / "answer_key.json").read_text()))


def score_case(case, result):
    key = case["key"]
    summary = result.get("changes_summary", "") or ""
    affected = set(result.get("affected_sop_ids", []))
    drafts = {d["sop_id"]: d for d in result.get("drafted_updates", result.get("drafts", []))}

    found = [c["id"] for c in key["changes"] if all(_has(summary, t) for t in c["key_terms"])]
    missed = [c["id"] for c in key["changes"] if c["id"] not in found]
    change_recall = len(found) / len(key["changes"]) if key["changes"] else 1.0

    truth = set(key["affected"])
    tp = len(affected & truth)
    impact_precision = tp / len(affected) if affected else (1.0 if not truth else 0.0)
    impact_recall = tp / len(truth) if truth else 1.0
    wrongly_flagged = sorted(affected - truth)
    not_flagged = sorted(truth - affected)

    edit_failures = []
    for sid, rule in key["edits"].items():
        txt = drafts.get(sid, {}).get("draft_text", "")
        if not txt:
            edit_failures.append(f"{sid}: no draft produced"); continue
        for t in rule["must_contain"]:
            if not _has(txt, t): edit_failures.append(f"{sid}: missing {t!r}")
        for t in rule["must_not_contain"]:
            if _has(txt, t): edit_failures.append(f"{sid}: still contains {t!r}")
    drafts_for_unaffected = sorted(set(drafts) - truth)
    invented = sum(len(d.get("review_flags") or []) for d in drafts.values())

    passed = (change_recall == 1.0 and not wrongly_flagged and not not_flagged
              and not edit_failures and not drafts_for_unaffected)
    return dict(case_id=case["meta"]["case_id"], category=case["meta"]["category"], passed=passed,
                change_recall=change_recall, missed_changes=missed,
                impact_precision=impact_precision, impact_recall=impact_recall,
                wrongly_flagged=wrongly_flagged, not_flagged=not_flagged,
                edit_failures=edit_failures, drafts_for_unaffected=drafts_for_unaffected,
                flagged_new_clauses=invented)


def run_eval(pipeline, cases_dir=CASES_DIR, out_path=None):
    rows = []
    for d in sorted(pathlib.Path(cases_dir).iterdir()):
        if not (d / "case.json").exists(): continue
        case = load_case(d)
        try:
            result = pipeline(case["old"], case["new"], case["sops"])
            row = score_case(case, result)
            row["draft_texts"] = {x["sop_id"]: x["draft_text"] for x in result.get("drafted_updates", [])}
            row["changes_summary"] = result.get("changes_summary", "")
        except Exception as e:  # a crash is a failed case, not a stopped run
            try:  # free GPU memory so one out-of-memory case does not break the next
                import gc, torch; gc.collect(); torch.cuda.empty_cache()
            except Exception:
                pass
            row = dict(case_id=case["meta"]["case_id"], category=case["meta"]["category"], passed=False, error=repr(e))
        rows.append(row)
    n = len(rows); ok = [r for r in rows if "error" not in r]
    avg = lambda k: round(sum(r[k] for r in ok) / len(ok), 3) if ok else 0
    summary = dict(cases=n, passed=sum(r["passed"] for r in rows),
                   avg_change_recall=avg("change_recall"), avg_impact_precision=avg("impact_precision"),
                   avg_impact_recall=avg("impact_recall"),
                   total_flagged_new_clauses=sum(r.get("flagged_new_clauses", 0) for r in ok),
                   errors=n - len(ok))
    out = dict(summary=summary, cases=rows)
    if out_path: pathlib.Path(out_path).write_text(json.dumps(out, indent=2))
    return out


def print_report(out):
    s = out["summary"]
    print(f"\nPASSED {s['passed']}/{s['cases']} cases | change recall {s['avg_change_recall']} | "
          f"impact precision {s['avg_impact_precision']} | impact recall {s['avg_impact_recall']} | "
          f"flagged new clauses {s['total_flagged_new_clauses']} | errors {s['errors']}\n")
    for r in out["cases"]:
        print(("PASS " if r["passed"] else "FAIL ") + f"{r['case_id']} [{r['category']}]")
        if "error" in r: print("   error:", r["error"]); continue
        for k in ("missed_changes", "wrongly_flagged", "not_flagged", "edit_failures", "drafts_for_unaffected"):
            if r[k]: print(f"   {k}: {r[k]}")

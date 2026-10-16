"""Scan a workspace: find policy versions, compare each new version to the one before it, map changes to SOPs, write
a report, draft files and patches, and log everything. It never edits an original file."""
import difflib, json, pathlib, datetime
from . import store
from .engine import run_engine


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def log_event(out_dir, event, **kw):
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    with open(out / "audit.jsonl", "a") as f:
        f.write(json.dumps(dict(time=now(), event=event, **kw)) + "\n")


def compare(old_doc, new_doc, sops):
    """One old/new pair against a list of SOPs. Returns a plain dict (JSON friendly)."""
    r = run_engine(old_doc, new_doc, sops)
    by_id = {s["id"]: s for s in sops}
    updates = []
    for d in r["drafted_updates"]:
        orig, draft = d["original_text"], d["draft_text"]
        diff = "".join(difflib.unified_diff(orig.splitlines(True), draft.splitlines(True),
                                            f"{d['sop_id']} (current)", f"{d['sop_id']} (suggested)"))
        updates.append(dict(sop_id=d["sop_id"], sop_path=by_id[d["sop_id"]].get("path"), why=d["reasons"],
                            review_flags=d["review_flags"], draft_text=draft, diff=diff))
    return dict(changes=r["changes_summary"], affected_sops=r["affected_sop_ids"], updates=updates,
                needs_review=r.get("needs_review", []))


def _md(pair):
    L = [f"## {pair['family']}: {pair['old_file']} -> {pair['new_file']}", "", "### What changed", "", "```", pair["changes"], "```", ""]
    if not pair["updates"]:
        L += ["No SOP needs an update from this change.", ""]
    for u in pair["updates"]:
        L += [f"### Suggested update: `{u['sop_id']}`", "", f"Why: {'; '.join(u['why'])}", ""]
        L += ["Review flags:"] + [f"- {f}" for f in u["review_flags"]] + [""]
        L += ["```diff", u["diff"].rstrip(), "```", ""]
    if pair["needs_review"]:
        L += ["### Needs a person to look at", ""]
        L += [f"- was: {x['old']}\n  now: {x['new']}" for x in pair["needs_review"]] + [""]
    return "\n".join(L)


def scan_workspace(policies_dir, sops_dir, out_dir, force=False):
    out = pathlib.Path(out_dir); (out / "drafts").mkdir(parents=True, exist_ok=True)
    state_path = out / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    sops = store.load_sops(sops_dir)
    versions = store.list_versions(policies_dir)
    pairs, skipped = [], 0
    for fam, paths in versions.items():
        for a, b in zip(paths, paths[1:]):
            od, nd = store.as_doc(a, fam, 1), store.as_doc(b, fam, 2)
            key = f"{fam}:{od['metadata']['sha']}:{nd['metadata']['sha']}:" + ",".join(sorted(s["id"] + store.sha(s["text"]) for s in sops))
            if state.get(key) and not force:
                skipped += 1; continue
            res = compare(od, nd, sops)
            res.update(family=fam, old_file=a.name, new_file=b.name)
            for u in res["updates"]:
                (out / "drafts" / f"{u['sop_id']}.{b.stem}.draft.txt").write_text(u["draft_text"])
                (out / "drafts" / f"{u['sop_id']}.{b.stem}.patch").write_text(u["diff"])
            state[key] = now(); pairs.append(res)
            log_event(out, "compared", family=fam, old=a.name, new=b.name, affected=res["affected_sops"])
    state_path.write_text(json.dumps(state, indent=1))
    rj = out / "report.json"                           # keep earlier results: the report is cumulative
    earlier = json.loads(rj.read_text()) if rj.exists() else []
    seen = {(p["family"], p["old_file"], p["new_file"]) for p in pairs}
    all_pairs = [p for p in earlier if (p["family"], p["old_file"], p["new_file"]) not in seen] + pairs
    new_count = len(pairs)
    pairs = all_pairs
    report = ["# Compliance scan report", "", f"Generated {now()}. Suggestions only: nothing was changed in your files.", "",
              f"Policy version pairs in this report: {len(pairs)} ({new_count} new in this scan, {skipped} already done).", ""] + [_md(p) for p in pairs]
    (out / "report.md").write_text("\n".join(report))
    (out / "report.json").write_text(json.dumps(pairs, indent=1, default=str))
    return dict(compared=new_count, already_done=skipped, report=str(out / "report.md"),
                summary=[dict(family=p["family"], old=p["old_file"], new=p["new_file"], affected_sops=p["affected_sops"],
                              needs_review=len(p["needs_review"])) for p in pairs])


def apply_draft(sop_path, draft_path, approved_by, out_dir):
    """Writes a draft over an SOP, only when a named person approved it. Keeps a .bak copy and logs it."""
    if not approved_by or not approved_by.strip():
        raise ValueError("approved_by is required: a person must approve every change")
    sop, draft = pathlib.Path(sop_path), pathlib.Path(draft_path)
    if not sop.exists() or not draft.exists(): raise FileNotFoundError("sop or draft file not found")
    bak = sop.with_suffix(sop.suffix + ".bak"); bak.write_text(sop.read_text())
    before = store.sha(sop.read_text()); sop.write_text(draft.read_text())
    log_event(out_dir, "applied", sop=str(sop), draft=str(draft), approved_by=approved_by, before=before,
              after=store.sha(sop.read_text()), backup=str(bak))
    return dict(applied=str(sop), backup=str(bak))

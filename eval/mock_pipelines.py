"""Fake pipelines used ONLY to test the scorer itself. They say nothing about the AI."""
import json, pathlib
from score import CASES_DIR

def _key_for(old_doc):
    cid = old_doc["id"].rsplit("_v", 1)[0]
    return json.loads((CASES_DIR / cid / "answer_key.json").read_text())

def null_pipeline(old, new, sops):
    return dict(changes_summary="No substantive changes.", affected_sop_ids=[], drafted_updates=[])

def flag_everything_pipeline(old, new, sops):
    return dict(changes_summary="Changed.", affected_sop_ids=[s["id"] for s in sops],
                drafted_updates=[dict(sop_id=s["id"], draft_text=s["text"], review_flags=[]) for s in sops])

def oracle_pipeline(old, new, sops):
    """Cheats by reading the answer key; must score 100%."""
    key = _key_for(old)
    terms = " ".join(t if isinstance(t, str) else t[0] for c in key["changes"] for t in c["key_terms"])
    drafts = []
    for sid, rule in key["edits"].items():
        txt = " ".join(t if isinstance(t, str) else t[0] for t in rule["must_contain"])
        drafts.append(dict(sop_id=sid, draft_text=txt, review_flags=[]))
    return dict(changes_summary=terms, affected_sop_ids=list(key["affected"]), drafted_updates=drafts)

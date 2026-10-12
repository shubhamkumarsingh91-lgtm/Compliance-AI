# Disclaimer: Independent personal project. Not affiliated with any employer, agency or vendor.
# Public documents and synthetic data only. No internal, confidential or personal data.

# =====================================================================
# CELL 1 - paste as a new code cell AFTER your Phase 4 cells, then run
# Replaces the "string match" logic that wrongly flagged sop_003.
# =====================================================================
import json, re

NEGATION_PATTERNS = re.compile(
    r"\b(not affected|unaffected|is not impacted|not impacted|no (?:change|update|impact)|"
    r"does not (?:directly )?(?:involve|affect|apply|require)|not relevant|no action)\b",
    re.IGNORECASE,
)

def parse_affected_fallback(impact_text, sops):
    """Used only if the model's JSON can't be parsed. Splits the text into one
    block per SOP id and skips any block containing 'not affected' language."""
    ids = [s["id"] for s in sops]
    positions = sorted((impact_text.find(i), i) for i in ids if impact_text.find(i) != -1)
    affected = []
    for n, (start, sop_id) in enumerate(positions):
        end = positions[n + 1][0] if n + 1 < len(positions) else len(impact_text)
        if not NEGATION_PATTERNS.search(impact_text[start:end]):
            affected.append(sop_id)
    return affected

def extract_json(text):
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None

def build_impact_prompt(change_summary, sops):
    sop_list = "\n\n".join(f"[{s['id']}] {s['title']}: {s['text']}" for s in sops)
    return f"""Given this policy change:
{change_summary}

And these internal procedures:
{sop_list}

For EACH procedure, decide whether the policy change requires its text to be updated.
Only mark a procedure as affected if the change alters a number, deadline, threshold or
rule that the procedure's text actually mentions. If the procedure is about something
unrelated, it is NOT affected.

Respond with ONLY a JSON object, no other text, in exactly this shape:
{{"procedures": [{{"id": "sop_001", "affected": true, "reason": "one sentence"}}, ...]}}
Include every procedure id exactly once."""

def resolve_impact(raw_text, sops):
    valid_ids = {s["id"] for s in sops}
    data = extract_json(raw_text)
    if data and isinstance(data.get("procedures"), list):
        affected, reasons = [], {}
        for item in data["procedures"]:
            sid = item.get("id")
            if sid in valid_ids:
                reasons[sid] = item.get("reason", "")
                if item.get("affected") is True:
                    affected.append(sid)
        return affected, reasons, "json"
    return parse_affected_fallback(raw_text, sops), {}, "fallback"

def find_affected_sops_structured(change_summary, sops, max_new_tokens=350):
    prompt = build_impact_prompt(change_summary, sops)
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=max_new_tokens,
                                 temperature=0.1, do_sample=True)
    raw = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    affected, reasons, method = resolve_impact(raw, sops)
    return {"affected_ids": affected, "reasons": reasons, "method": method, "raw": raw}

print("Structured impact analysis ready.")


# =====================================================================
# CELL 2 - paste as a new code cell right after Cell 1, then run
# Redefines the pipeline to use the fixed logic, reruns it, re-exports JSON.
# =====================================================================
def run_full_compliance_check(old_doc, new_doc, sops):
    changes = detect_changes(old_doc, new_doc)

    impact = find_affected_sops_structured(changes, sops)
    affected_ids = impact["affected_ids"]
    impact_text = "\n".join(
        f"[{sid}] {'AFFECTED' if sid in affected_ids else 'not affected'}: "
        f"{impact['reasons'].get(sid, '')}"
        for sid in [s["id"] for s in sops]
    ) if impact["reasons"] else impact["raw"]

    drafts = []
    for sop in sops:
        if sop["id"] in affected_ids:
            drafts.append({
                "sop_id": sop["id"],
                "sop_title": sop["title"],
                "original_text": sop["text"],
                "draft_text": generate_sop_draft(sop, changes, new_doc),
            })

    return {
        "policy_family": new_doc["metadata"]["policy_family"],
        "old_version": {"title": old_doc["title"], "effective_date": old_doc["metadata"]["effective_date"]},
        "new_version": {"title": new_doc["title"], "effective_date": new_doc["metadata"]["effective_date"]},
        "changes_summary": changes,
        "impact_analysis": impact_text,
        "impact_parse_method": impact["method"],   # "json" = clean, "fallback" = review by hand
        "affected_sop_ids": affected_ids,
        "drafted_updates": drafts,
        "status": "drafts_ready_for_review",
    }

full_results = []
for old, new in pairs:
    result = run_full_compliance_check(old, new, SAMPLE_INTERNAL_SOPS)
    full_results.append(result)
    print(f"Parse method : {result['impact_parse_method']}")
    print(f"Affected SOPs: {result['affected_sop_ids']}")
    print(f"Drafts made  : {[d['sop_id'] for d in result['drafted_updates']]}")

# Safety check: the telehealth SOP must NOT be flagged for a prior-auth change
assert "sop_003" not in full_results[0]["affected_sop_ids"], "sop_003 was flagged again - rerun or tell Claude"
print("\nCheck passed: sop_003 (telehealth) is not flagged.")

with open("/kaggle/working/compliance_results.json", "w") as f:
    json.dump(full_results, f, indent=2)
print("Saved /kaggle/working/compliance_results.json")

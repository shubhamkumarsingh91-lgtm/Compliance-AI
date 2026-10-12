# =====================================================================
# CELL 1 - paste as a new code cell at the BOTTOM of the notebook, run it
# Tightens the drafting prompt + adds a "new clause" check for human review.
# =====================================================================
import re

def clean_draft(txt):
    """Drops the markdown header/citation lines the model adds and strips ** bold."""
    parts = [p for p in txt.split("\n\n")
             if not p.strip().startswith("**Procedure [") and not p.strip().startswith("**Citation")]
    return " ".join(parts).replace("**", "").strip()

def _words(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))

def new_clause_flags(original, draft, threshold=0.8):
    """Returns draft sentences that are mostly NOT in the original procedure (new clauses).
    A plain number swap (12 -> 20) is not flagged; an added rule is."""
    orig_words = _words(original)
    flags = []
    for sent in re.split(r"(?<=[.!?])\s+", draft):
        w = _words(sent)
        if w and len(w & orig_words) / len(w) < threshold:
            flags.append(sent.strip())
    return flags

def generate_sop_draft(sop, change_summary, new_doc, max_new_tokens=300):
    """Redefines the Phase 4 function with a stricter prompt."""
    prompt = f"""You are a Medicaid compliance analyst updating an internal procedure.

RULES - follow all of them:
1. Change ONLY the numbers, thresholds and deadlines that the policy change affects.
2. Keep every other word of the original procedure exactly as written.
3. Do NOT add any new sentence, step, condition or requirement that is not already in the
   original procedure.
4. Output ONLY the rewritten procedure text. No title, no markdown, no citation line.

ORIGINAL PROCEDURE [{sop['id']}] {sop['title']}:
{sop['text']}

POLICY CHANGE:
{change_summary}

Rewritten procedure:"""
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=max_new_tokens,
                                 temperature=0.1, do_sample=True)
    raw = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return clean_draft(raw)

print("Stricter drafting ready.")


# =====================================================================
# CELL 2 - paste right after Cell 1, run it
# Reruns the pipeline, attaches review flags, saves the JSON.
# (Needs the sop003 fix cells from earlier to have been run first.)
# =====================================================================
full_results = []
for old, new in pairs:
    result = run_full_compliance_check(old, new, SAMPLE_INTERNAL_SOPS)
    for d in result["drafted_updates"]:
        d["review_flags"] = new_clause_flags(d["original_text"], d["draft_text"])
    full_results.append(result)

for d in full_results[0]["drafted_updates"]:
    print(f"[{d['sop_id']}] {d['draft_text']}")
    print(f"   new clauses to verify: {d['review_flags'] or 'none'}\n")

assert "sop_003" not in full_results[0]["affected_sop_ids"], "sop_003 flagged again"

with open("/kaggle/working/compliance_results.json", "w") as f:
    json.dump(full_results, f, indent=2)
print("Saved /kaggle/working/compliance_results.json")

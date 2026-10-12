# Disclaimer: Independent personal project. Not affiliated with any employer, agency or vendor.
# Public documents and synthetic data only. No internal, confidential or personal data.
#
# PASTE-IN CELL (v2). Run AFTER the earlier patch cells (sop003 fix, draft prompt fix).
# Why: the first evaluation run showed two prompt-design flaws, not just model weakness:
#   - the impact prompt only flagged SOPs that already mention the changed item, so a newly ADDED
#     requirement never reached the SOP that performs that activity;
#   - the draft prompt said "change ONLY numbers" and "add NO new sentence", so it could not REMOVE
#     a requirement the policy dropped, or ADD one the policy introduced.
# These prompts let the model add or remove a requirement ONLY when the policy change states it.
# Any added sentence is still flagged for human review by new_clause_flags.

def build_impact_prompt(change_summary, sops):
    sop_list = "\n\n".join(f"[{s['id']}] {s['title']}: {s['text']}" for s in sops)
    return f"""Given this policy change:
{change_summary}

And these internal procedures:
{sop_list}

For EACH procedure, decide whether the policy change requires its text to be updated.
Mark a procedure as affected if EITHER:
  (a) the change alters a number, deadline, threshold or rule that the procedure's text mentions, OR
  (b) the change adds or removes a requirement for the same activity the procedure performs,
      even if the procedure's text does not yet mention that requirement.
If the procedure covers a different activity, it is NOT affected.

Respond with ONLY a JSON object, no other text, in exactly this shape:
{{"procedures": [{{"id": "sop_001", "affected": true, "reason": "one sentence"}}, ...]}}
Include every procedure id exactly once."""


def generate_sop_draft(sop, change_summary, new_doc, max_new_tokens=300):
    prompt = f"""You are a Medicaid compliance analyst updating an internal procedure.

RULES - follow all of them:
1. Change the numbers, thresholds and deadlines that the policy change affects.
2. If the policy change REMOVES a requirement that this procedure states, delete that requirement
   from the procedure.
3. If the policy change ADDS a requirement for the activity this procedure covers, add exactly ONE
   short sentence stating it, using the policy's own numbers and wording.
4. Keep every other word of the original procedure exactly as written.
5. Do NOT add anything the policy change does not state.
6. Output ONLY the rewritten procedure text. No title, no markdown, no citation line.

ORIGINAL PROCEDURE [{sop['id']}] {sop['title']}:
{sop['text']}

POLICY CHANGE:
{change_summary}

Rewritten procedure:"""
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=max_new_tokens, temperature=0.1, do_sample=True)
    raw = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return clean_draft(raw)

print("Prompt fix v2 loaded (impact + drafting).")

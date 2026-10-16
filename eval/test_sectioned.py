"""Run: python3 test_sectioned.py   (no GPU; checks the chunk pairing on the real MITA documents)"""
from score import load_case
from sectioned import candidate_pairs, split_chunks

c = load_case("cases/real_mita_intro_2_0_to_3_0")
old, new = c["old"]["text"], c["new"]["text"]
print("chunks:", len(split_chunks(old)), "old,", len(split_chunks(new)), "new")
pairs = candidate_pairs(old, new)
print("candidate pairs (focus on numbers/obligations):", len(pairs))
hit = [p for p in pairs if "eight business areas" in p[0].lower() and "ten (10) business areas" in p[1].lower()]
print("pair containing the real 8 -> 10 change:", len(hit))
assert len(hit) >= 1, "the real change was not paired - tune chunking"
print("model calls needed:", len(pairs))
# synthetic cases: the changed numbers must survive the filter; the wording-only control must produce nothing
for cid, expect in [("cert_01_checklist_deadlines", True), ("policy_01_prior_auth_threshold", True),
                    ("control_01_wording_only", False)]:
    k = load_case(f"cases/{cid}")
    p = candidate_pairs(k["old"]["text"], k["new"]["text"])
    assert bool(p) == expect, (cid, p)
# merged summary must stay small even when the model is verbose on every pair, and must keep the real finding
from sectioned import make_sectioned_detector
def verbose_model(o, n):
    real = "eight" in o["text"].lower() and "ten (10)" in n["text"].lower()
    filler = " The wording was reorganised and several sentences were rephrased to clarify the section. " * 6
    return ("Business areas changed from eight to ten (10)." if real else "The text says must within 30 days instead of after 10 days.") + filler
detect = make_sectioned_detector(verbose_model, verbose=False)
merged = detect(c["old"], c["new"])
print("merged summary chars:", len(merged))
assert len(merged) <= 3500 + 10, "summary not capped"
assert "eight to ten" in merged, "real finding lost"
print("OK")

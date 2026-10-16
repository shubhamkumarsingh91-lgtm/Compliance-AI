"""Makes thousands of labeled old/new policy cases automatically, each with a known right answer.

Why: 10 hand-written cases cannot show reliability. A generator can make 1,000+ cases in seconds, each built from a
known edit, so the answer key is exact by construction. Use it to find bugs and measure rates by change type.

What it does NOT prove: accuracy on real policy writing. The generator is templates written by me, so very high scores
here mean "robust on this family of changes". The real-world number comes from real document pairs (see real/).

Usage:  python3 generate_cases.py 1000 [seed]
"""
import random, sys, json, collections
from score import score_case
import engine

THINGS = ["claim forms", "appeal letters", "incident reports", "consent forms", "enrollment packets", "audit responses",
          "referral requests", "cost reports", "discharge summaries", "complaint logs", "eligibility files", "transport requests"]
EVENTS = ["discharge", "the date of service", "the denial notice", "the enrollment date", "the incident", "the audit notice"]
MONTHS = ["January", "February", "March", "April", "June", "July", "August", "September", "October", "November", "December"]

# (policy form A, policy form B (same meaning, different words), SOP text). Slots: {t} thing, {e} event, {n} number.
NUM_TEMPLATES = [
    ("Providers must submit {t} within {n} days of {e}.", "{T} must be submitted by providers within {n} days after {e}.",
     "Send {t} no later than {n} days after {e} and keep proof of delivery."),
    ("{T} must be retained for {n} years.", "Providers shall keep {t} for {n} years.", "Keep {t} on file for {n} years, then archive them."),
    ("Prior authorization is required after {n} visits in a benefit year.", "After {n} visits in a benefit year, prior authorization is required.",
     "Check the visit count against the {n}-visit prior authorization threshold before scheduling."),
    ("Audio-only visits are reimbursed at {n}% of the standard rate.", "The standard rate is reduced to {n}% for audio-only visits.",
     "Bill audio-only visits at {n}% of the standard rate."),
    ("Purchases above ${n} require written approval from the director.", "Written director approval is required for purchases above ${n}.",
     "Get written director approval for any purchase above ${n}."),
    ("{T} are due {n} days after the quarter ends.", "Quarter-end {t} must be filed {n} days after quarter end.",
     "File {t} {n} days after the quarter ends."),
    ("Staff must receive {n} hours of annual compliance training.", "Each staff member shall complete {n} hours of compliance training every year.",
     "Schedule {n} hours of compliance training for each staff member every year."),
]
MONTH_TEMPLATES = [
    ("Annual {t} must be completed by {m}.", "{T} for the year are to be completed no later than {m}.", "Finish the annual {t} by {m} each year."),
    ("The reporting period begins in {m}.", "Each reporting period starts in {m}.", "Open the new reporting period in {m}."),
]
# (new requirement sentence, SOP text for the same activity, overlap: words shared with the SOP)
ADD_PAIRS = [
    ("Providers must also record interpreter use at each patient visit.", "Complete the interpreter log for each patient visit before closing the chart.", "high"),
    ("Providers must also post the current fee schedule in the waiting room.", "Update the fee schedule posted in the waiting room each quarter.", "high"),
    ("Facilities shall verify patient identity before any procedure.", "Before any procedure, check the photo ID of the patient at the bedside.", "low"),
    ("Providers must also submit proof of active liability insurance with each revalidation.", "Send the revalidation packet to each provider 90 days before the revalidation date.", "high"),
    ("Staff must also complete a fire drill every six months.", "Walk every floor each spring and test the alarms.", "none"),
    ("The report must include a current risk register.", "Prepare the monthly project report and archive a copy.", "low"),
    ("Pharmacies must also log every controlled substance count.", "Count controlled substances at close and sign the count sheet.", "high"),
]
REMOVE_PAIRS = [
    ("Providers must also mail a paper copy of each {t}.", "Mail a paper copy of each {t} to the agency and upload the electronic file.", "A paper copy of each {t} is no longer required."),
    ("Providers must also notify the agency of any audit request.", "Retain records and notify the agency of any audit request.", "Notification of audit requests is no longer required."),
    ("Pharmacies must obtain a physician signature on each refill request.", "Obtain a physician signature on each refill request and dispense the refill.", "A physician signature on each refill request is not required."),
]
FILLER = ["Providers must follow the program manual.", "This policy applies to all enrolled facilities.",
          "Questions may be sent to the program office.", "Records are subject to review."]
DISTRACT = ["Mail patient statements on the first business day of each month.", "Replace lobby signs every spring.",
            "Give each new employee a badge and a login on the first day.", "Track supply orders in the shared spreadsheet.",
            "Lock the medication room at close and record the time.", "Clean the waiting room chairs every evening."]


def cap(s): return s[0].upper() + s[1:]


def fill(tpl, **kw):
    kw = dict(kw); kw["T"] = cap(kw["t"]) if "t" in kw else ""
    return tpl.format(**kw)


def make(i, rng):
    kind = rng.choices(["number", "month", "added", "removed", "silent_removed", "reword", "unrelated", "multi"],
                       [26, 8, 14, 10, 8, 14, 10, 10])[0]
    t1, t2 = rng.sample(THINGS, 2); e = rng.choice(EVENTS)
    sops, changes, affected, edits, notes = [], [], [], {}, ""
    old, new = [], []
    expect_none = False

    def num_pair(idx):
        a, b, sop = rng.choice(NUM_TEMPLATES)
        n1 = rng.choice([5, 7, 10, 12, 15, 20, 30, 45, 60, 90]); n2 = rng.choice([x for x in (3, 5, 8, 10, 14, 20, 25, 30, 40, 75, 120) if x != n1])
        t = rng.choice(THINGS); return a, b, sop, n1, n2, t
    if kind in ("number", "multi", "unrelated"):
        a, b, sop, n1, n2, t = num_pair(0)
        old.append(fill(a, t=t, e=e, n=n1)); new.append(fill(a, t=t, e=e, n=n2))
        if kind != "unrelated":
            sid = "s1"; sops.append(dict(id=sid, title="SOP " + sid, text=fill(sop, t=t, e=e, n=n1)))
            affected.append(sid)
            changes.append(dict(id="k1", desc="number", key_terms=[str(n1), str(n2)]))
            edits[sid] = dict(must_contain=[str(n2)], must_not_contain=[str(n1)] if str(n1) not in str(n2) else [])
        else:
            changes.append(dict(id="k1", desc="number, no SOP", key_terms=[str(n1), str(n2)]))
        if kind == "multi":
            m_t, m_s = rng.choice(ADD_PAIRS)[:2] if False else (None, None)
            a2, b2, sop2, m1, m2, tb = num_pair(1)
            while sop2 == sop or tb == t: a2, b2, sop2, m1, m2, tb = num_pair(1)
            old.append(fill(a2, t=tb, e=e, n=m1)); new.append(fill(a2, t=tb, e=e, n=m2))
            sops.append(dict(id="s2", title="SOP s2", text=fill(sop2, t=tb, e=e, n=m1))); affected.append("s2")
            changes.append(dict(id="k2", desc="number 2", key_terms=[str(m1), str(m2)]))
            edits["s2"] = dict(must_contain=[str(m2)], must_not_contain=[str(m1)] if str(m1) not in str(m2) else [])
    elif kind == "month":
        a, b, sop = rng.choice(MONTH_TEMPLATES); t = rng.choice(THINGS)
        m1, m2 = rng.sample(MONTHS, 2)
        old.append(fill(a, t=t, m=m1)); new.append(fill(a, t=t, m=m2))
        sops.append(dict(id="s1", title="SOP s1", text=fill(sop, t=t, m=m1))); affected.append("s1")
        changes.append(dict(id="k1", desc="month", key_terms=[m1.lower(), m2.lower()]))
        edits["s1"] = dict(must_contain=[m2], must_not_contain=[m1])
    elif kind == "added":
        sent, sop, ov = rng.choice(ADD_PAIRS)
        a, b, s0, n1, _, t = num_pair(0)
        old.append(fill(a, t=t, e=e, n=n1)); new.append(fill(a, t=t, e=e, n=n1)); new.append(sent)
        sops.append(dict(id="s1", title="SOP s1", text=sop)); affected.append("s1"); notes = f"overlap={ov}"
        key = sent.rstrip(".").split("must also ")[-1].split("shall ")[-1].split("must ")[-1]
        changes.append(dict(id="k1", desc="requirement added", key_terms=[key.split()[-2] + " " + key.split()[-1]]))
        edits["s1"] = dict(must_contain=[key.split()[-1]], must_not_contain=[])
    elif kind in ("removed", "silent_removed"):
        req, sop, notice = rng.choice(REMOVE_PAIRS); t = rng.choice(THINGS)
        a, b, s0, n1, _, t0 = num_pair(0)
        base = fill(a, t=t0, e=e, n=n1)
        old.append(base); old.append(fill(req, t=t)); new.append(base)
        if kind == "removed": new.append(fill(notice, t=t))
        sop_txt = fill(sop, t=t)
        sops.append(dict(id="s1", title="SOP s1", text=sop_txt)); affected.append("s1")
        words = fill(req, t=t).rstrip(".").split()
        changes.append(dict(id="k1", desc="requirement removed", key_terms=[words[-2] if kind == "silent_removed" else words[-1]]))
        gone = {"mail a paper copy": "paper copy", "notify the agency": "notify the agency", "obtain a physician signature": "physician signature"}
        phrase = [v for k, v in gone.items() if k in sop_txt.lower()][0]
        edits["s1"] = dict(must_contain=[], must_not_contain=[phrase])
    elif kind == "reword":
        a, b, sop, n1, _, t = num_pair(0)
        old.append(fill(a, t=t, e=e, n=n1)); new.append(fill(b, t=t, e=e, n=n1))
        sops.append(dict(id="s1", title="SOP s1", text=fill(sop, t=t, e=e, n=n1)))
        expect_none = True
    # common filler + distractors
    if rng.random() < .6:
        f = rng.choice(FILLER); old.append(f); new.append(f)
    for j, d in enumerate(rng.sample(DISTRACT, rng.choice([1, 2, 3]))):
        sops.append(dict(id=f"d{j}", title=f"Distractor {j}", text=d))
    rng.shuffle(sops)
    if expect_none: changes, affected, edits = [], [], {}
    hdr = "SYNTHETIC EXAMPLE - generated for testing, not real policy text.\n\nSample Policy (v%d)\n\n"
    key = dict(changes=changes, affected=affected, edits=edits)
    if expect_none: key["expect_no_change"] = True
    mk = lambda txt, v: dict(id=f"gen{i}_v{v}", title=f"gen{i} v{v}", text=hdr % v + " ".join(txt),
                             metadata=dict(policy_family=f"gen{i}", version=v, is_current=v == 2))
    return dict(meta=dict(case_id=f"gen_{i:04d}", category=kind + ("" if notes == "" else " " + notes)),
                old=mk(old, 1), new=mk(new, 2), sops=sops, key=key)


def oracle_judge_for(case):
    """A judge that knows the answer key. Used only to test that the judge plumbing works (not a model)."""
    from compliance_agent.judge import FakeJudge
    truth = {s["text"] for s in case["sops"] if s["id"] in case["key"]["affected"]}
    reword = case["meta"]["category"].startswith("reword")
    def rule(kind, a, b):
        if kind == "same_requirement": return "yes" if reword else "no"
        return "yes" if b in truth else "no"
    return FakeJudge(rule)


def run(n=1000, seed=7, show=8, judge_factory=None, kinds=None):
    """judge_factory(case) -> judge or None. kinds: only run these case types (e.g. {'added', 'reword'})."""
    rng = random.Random(seed)
    by = collections.defaultdict(lambda: [0, 0]); fails = []
    for i in range(n):
        c = make(i, rng)
        if kinds and c["meta"]["category"].split(" ")[0] not in kinds: continue
        r = score_case(c, engine.run_engine(c["old"], c["new"], c["sops"], judge=judge_factory(c) if judge_factory else None))
        k = c["meta"]["category"].split(" ")[0] + (" (" + c["meta"]["category"].split("overlap=")[1] + " overlap)" if "overlap=" in c["meta"]["category"] else "")
        by[k][1] += 1; by[k][0] += r["passed"]
        if not r["passed"]: fails.append((c, r))
    tot = sum(v[1] for v in by.values()); ok = sum(v[0] for v in by.values())
    print(f"seed {seed}: {ok}/{tot} passed ({100*ok/tot:.1f}%)")
    for k, (p, t) in sorted(by.items()): print(f"  {k:32s} {p:4d}/{t:<4d} {100*p/t:5.1f}%")
    for c, r in fails[:show]:
        print("\nFAIL", c["meta"]["case_id"], c["meta"]["category"])
        print("  OLD:", c["old"]["text"].split("\n\n", 2)[2][:230]); print("  NEW:", c["new"]["text"].split("\n\n", 2)[2][:230])
        for s in c["sops"][:3]: print("  SOP", s["id"], s["text"][:110])
        print("  ", {k: v for k, v in r.items() if k in ("missed_changes", "wrongly_flagged", "not_flagged", "edit_failures", "drafts_for_unaffected") and v})
    return ok, tot


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run(int(args[0]) if args else 1000, int(args[1]) if len(args) > 1 else 7,
        judge_factory=oracle_judge_for if "--oracle-judge" in sys.argv else None)

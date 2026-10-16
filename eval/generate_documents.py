"""Makes whole synthetic policy MANUALS (sections, headings, bullets, page headers) in the agent's folder layout, with an
exact answer key, then checks what the real folder scan reports.

Why: generate_cases.py makes tiny 2-sentence cases. Real documents are long, have headings, bullets and running page
headers, and have many SOPs. This tests the agent end to end on that shape: policies/<family>/v1,v2 files and sops/*.txt.

Usage:  python3 generate_documents.py 200 [seed]      (writes to a temp folder, prints results by change type)
"""
import json, pathlib, random, sys, tempfile, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import generate_cases as g
from compliance_agent import scan

HEADINGS = ["Scope and Applicability", "Submission Requirements", "Timelines and Deadlines", "Records and Reporting",
            "Reimbursement", "Staff and Training", "Facilities and Equipment", "Review and Appeals"]


def build_family(fid, rng, add_semantic=False):
    """Returns (v1_sentences, v2_sentences, sops, expectations). Sentences are (text, section) pairs."""
    used_tpl = rng.sample(range(len(g.NUM_TEMPLATES)), rng.randint(4, len(g.NUM_TEMPLATES)))
    facts, sops = [], []
    for k, ti in enumerate(used_tpl):
        a, b, sop = g.NUM_TEMPLATES[ti]
        t = g.THINGS[(k * 3 + fid) % len(g.THINGS)]; e = rng.choice(g.EVENTS)
        n = rng.choice([5, 7, 10, 12, 15, 20, 30, 45, 60, 90])
        facts.append(dict(id=f"f{k}", a=a, b=b, t=t, e=e, n=n, form="a"))
        sops.append(dict(id=f"{fid}_sop{k}", title=f"sop{k}", text=g.fill(sop, t=t, e=e, n=n) + " Keep a note in the file."))
    months = rng.sample(g.MONTH_TEMPLATES, 1)
    mfacts = []
    for a, b, sop in months:
        t = rng.choice(g.THINGS); m = rng.choice(g.MONTHS)
        mfacts.append(dict(id="m0", a=a, b=b, t=t, m=m, form="a"))
        sops.append(dict(id=f"{fid}_sopm", title="month", text=g.fill(sop, t=t, m=m)))
    # removable requirement (present in v1)
    req, rsop, notice = rng.choice(g.REMOVE_PAIRS); rt = rng.choice(g.THINGS)
    sops.append(dict(id=f"{fid}_sopr", title="removable", text=g.fill(rsop, t=rt)))
    # requirement that will be added in v2 (its SOP exists from the start)
    pool = [p for p in g.ADD_PAIRS if add_semantic or p[2] != "none"]
    addsent, addsop, ov = rng.choice(pool)
    sops.append(dict(id=f"{fid}_sopa", title="addable", text=addsop))
    for j, d in enumerate(rng.sample(g.DISTRACT, 4)):
        sops.append(dict(id=f"{fid}_d{j}", title=f"dist{j}", text=d))

    def render(fs, ms, remove_req, notice_on, add_on, forms):
        out = []
        for f in fs: out.append(g.fill(f["a"] if forms.get(f["id"], "a") == "a" else f["b"], t=f["t"], e=f["e"], n=f["n"]))
        for m in ms: out.append(g.fill(m["a"], t=m["t"], m=m["m"]))
        if not remove_req: out.append(g.fill(req, t=rt))
        if notice_on: out.append(g.fill(notice, t=rt))
        if add_on: out.append(addsent)
        return out

    # ---- v1 and v2, with a random set of mutations and the matching expectations ----
    exp = []                                             # (type, sop_id, must_contain, must_not_contain)
    v1 = render(facts, mfacts, False, False, False, {})
    f2 = [dict(f) for f in facts]; m2 = [dict(m) for m in mfacts]; forms = {}
    muts = rng.sample(["num", "num", "month", "reword", "reword", "remove", "silent_remove", "add"], rng.randint(2, 5))
    remove_req = notice_on = add_on = False
    for mu in muts:
        if mu == "num":
            cand = [f for f in f2 if f["n"] == facts[f2.index(f)]["n"]]
            if not cand: continue
            f = rng.choice(cand); i = f2.index(f); old = f["n"]
            f["n"] = rng.choice([x for x in (3, 8, 14, 25, 40, 75, 120) if x != old])
            exp.append(("number", f"{fid}_sop{i}", [str(f["n"])], [str(old)] if str(old) not in str(f["n"]) else []))
        elif mu == "month" and m2 and m2[0]["m"] == mfacts[0]["m"]:
            old = m2[0]["m"]; m2[0]["m"] = rng.choice([x for x in g.MONTHS if x != old])
            exp.append(("month", f"{fid}_sopm", [m2[0]["m"]], [old]))
        elif mu == "reword":
            f = rng.choice(f2); forms[f["id"]] = "b"
        elif mu in ("remove", "silent_remove") and not remove_req:
            remove_req = True; notice_on = mu == "remove"
            gone = {"mail a paper copy": "paper copy", "notify the agency": "notify the agency", "obtain a physician signature": "physician signature"}
            ph = [v for k, v in gone.items() if k in g.fill(rsop, t=rt).lower()][0]
            exp.append((mu, f"{fid}_sopr", [], [ph]))
        elif mu == "add" and not add_on:
            add_on = True; exp.append((f"added ({ov} overlap)", f"{fid}_sopa", [addsent.rstrip('.')], []))
    v2 = render(f2, m2, remove_req, notice_on, add_on, forms)
    return v1, v2, sops, exp


def layout(sentences, rng, title, version):
    """Turns sentences into a manual: headings, paragraphs, bullets, and a running page header."""
    secs = rng.sample(HEADINGS, rng.randint(3, 5)); rng.shuffle(sentences)
    lines = [f"{title} (v{version})", ""]
    chunks = [sentences[i::len(secs)] for i in range(len(secs))]
    page = 1
    for k, (h, ch) in enumerate(zip(secs, chunks), 1):
        lines += [f"Section {k}. {h}", ""]
        for s in ch:
            lines.append(("- " if rng.random() < .25 else "") + s)
            if rng.random() < .3: lines.append("")
        if k % 2 == 0:
            page += 1; lines += ["", f"Sample Policy Manual - Page {page}", ""]
    return "\n".join(lines) + "\n"


def generate_workspace(out, fid, seed=3, add_semantic=False):
    """One organisation: one manual (v1, v2) and its own SOP library, in its own folder."""
    rng = random.Random(seed * 100003 + fid); out = pathlib.Path(out)
    (out / "sops").mkdir(parents=True, exist_ok=True)
    v1, v2, sops, exp = build_family(fid, rng, add_semantic)
    d = out / "policies" / "manual"; d.mkdir(parents=True, exist_ok=True)
    (d / "manual_v1_2023-01-01.txt").write_text(layout(list(v1), random.Random(fid), "Sample Policy Manual", 1))
    (d / "manual_v2_2026-01-01.txt").write_text(layout(list(v2), random.Random(fid), "Sample Policy Manual", 2))
    for s in sops: (out / "sops" / f"{s['id']}.txt").write_text(s["text"] + "\n")
    return dict(prefix=f"{fid}_", exp=exp)


def score_one(key, report, by, fails, label):
    """Every expected SOP must be flagged with the right edit; any other flagged SOP is a false alarm."""
    p = report[0]; got = {u["sop_id"]: u for u in p["updates"]}
    want = {sid: (t, mc, mn) for t, sid, mc, mn in key["exp"]}
    for sid, (t, mc, mn) in want.items():
        why = []
        if sid in got:
            txt = got[sid]["draft_text"]
            why += [f"missing {x!r}" for x in mc if x.lower() not in txt.lower()]
            why += [f"still has {x!r}" for x in mn if x.lower() in txt.lower()]
        else: why = ["not flagged"]
        by[t][1] += 1
        if not why: by[t][0] += 1
        else: fails.append((label, sid, t, why))
    extra = set(got) - set(want)
    by["no false alarms (per manual)"][1] += 1
    if extra: fails.append((label, ",".join(sorted(extra)), "false alarm", ["flagged without a change"]))
    else: by["no false alarms (per manual)"][0] += 1


def run(n=200, seed=3, judge=None, add_semantic=False, show=8):
    root = pathlib.Path(tempfile.mkdtemp()); by = collections.defaultdict(lambda: [0, 0]); fails = []
    for fid in range(n):
        ws = root / f"org_{fid:03d}"; key = generate_workspace(ws, fid, seed, add_semantic)
        scan.scan_workspace(ws / "policies", ws / "sops", ws / "out", judge=judge)
        score_one(key, json.loads((ws / "out" / "report.json").read_text()), by, fails, f"org_{fid:03d}")
    tot = sum(v[1] for v in by.values()); ok = sum(v[0] for v in by.values())
    print(f"{n} manuals, seed {seed}: {ok}/{tot} checks passed ({100*ok/tot:.1f}%)   [files: {root}]")
    for kx, (p, t) in sorted(by.items()): print(f"  {kx:34s} {p:4d}/{t:<4d} {100*p/t:5.1f}%")
    for f in fails[:show]: print("  FAIL", f)
    return ok, tot, fails, root


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 200, int(sys.argv[2]) if len(sys.argv) > 2 else 3)

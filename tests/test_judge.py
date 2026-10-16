"""Tests for the language-model check, using fake judges so no GPU or network is needed.
Run from the repo root:  python3 tests/test_judge.py
These test the PLUMBING and the safety rules. How accurate a real model is must be measured separately (eval/kaggle_run_judge.py)."""
import json, pathlib, shutil, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from compliance_agent import scan
from compliance_agent.engine import run_engine
from compliance_agent.judge import FakeJudge, NoJudge, Judge, parse_verdict

OLD = {"text": "Facilities must record vital signs at each visit."}
NEW = {"text": "Facilities must record vital signs at each visit. Staff must also complete a fire drill every six months."}
SOPS = [dict(id="alarms", title="Alarm test", text="Walk every floor each spring and test the alarms."),
        dict(id="signs", title="Lobby signs", text="Replace lobby signs every spring.")]


def test_parse_verdict_is_strict():
    assert parse_verdict('{"answer": "Yes", "reason": "same task"}') == ("yes", "same task")
    assert parse_verdict('Sure! {"answer":"no","reason":"x"} thanks')[0] == "no"
    assert parse_verdict("yes, it applies")[0] == "yes"
    assert parse_verdict("I think maybe")[0] == "unsure"            # unreadable never becomes a guess
    assert parse_verdict('{"answer": "definitely"}')[0] == "unsure"
    assert parse_verdict(None)[0] == "unsure"


def test_rules_alone_miss_the_case_judge_fixes():
    r = run_engine(OLD, NEW, SOPS)
    assert r["affected_sop_ids"] == [], "rules alone cannot connect 'fire drill' to 'test the alarms'"
    judge = FakeJudge(lambda k, a, b: "yes" if ("fire drill" in a and "alarms" in b) else "no")
    r = run_engine(OLD, NEW, SOPS, judge=judge)
    assert r["affected_sop_ids"] == ["alarms"], r["affected_sop_ids"]
    d = r["drafted_updates"][0]
    assert "Staff must also complete a fire drill every six months." in d["draft_text"], "added text must be verbatim from the policy"
    assert any("the model judged that it applies" in f for f in d["review_flags"]), d["review_flags"]
    assert r["judge_log"] and r["judge_log"][0]["answer"] in ("yes", "no")


def test_judge_cannot_break_rule_results():
    # A judge that always says 'no' or 'unsure' must not remove a correct rule-based match.
    old = {"text": "Claims are due within 30 days of discharge."}; new = {"text": "Claims are due within 45 days of discharge."}
    sops = [dict(id="a", title="a", text="File each claim within 30 days of discharge.")]
    base = run_engine(old, new, sops)["affected_sop_ids"]
    assert base == ["a"]
    for ans in ("no", "unsure"):
        assert run_engine(old, new, sops, judge=FakeJudge(lambda k, a, b, ans=ans: ans))["affected_sop_ids"] == ["a"], ans


def test_weak_link_dropped_only_on_no():
    old = {"text": "Providers must follow the program manual."}
    new = {"text": "Providers must follow the program manual. Providers must also post the current fee schedule in the waiting room."}
    sops = [dict(id="chairs", title="c", text="Wipe the waiting chairs every evening.")]
    assert run_engine(old, new, sops)["affected_sop_ids"] == ["chairs"], "one shared word links them without a judge"
    assert run_engine(old, new, sops, judge=FakeJudge(lambda k, a, b: "no"))["affected_sop_ids"] == []
    assert run_engine(old, new, sops, judge=FakeJudge(lambda k, a, b: "unsure"))["affected_sop_ids"] == ["chairs"]


def test_reworded_sentence_suppressed_only_on_yes():
    old = {"text": "Claims are due within 30 days of discharge."}
    new = {"text": "Facilities must submit claims no later than 30 days after discharge."}
    base = run_engine(old, new, [])
    assert base["needs_review"], "rules list it as uncertain"
    assert run_engine(old, new, [], judge=FakeJudge(lambda k, a, b: "yes"))["needs_review"] == []
    assert run_engine(old, new, [], judge=FakeJudge(lambda k, a, b: "unsure"))["needs_review"]


def test_no_judge_changes_nothing_and_limits_hold():
    assert run_engine(OLD, NEW, SOPS, judge=NoJudge()) == run_engine(OLD, NEW, SOPS)
    class Counter(Judge):
        n = 0
        def _ask(self, prompt): Counter.n += 1; return '{"answer":"no","reason":"x"}'
    j = Counter(max_calls=1)
    j.ask("applies", "a", "b"); j.ask("applies", "a", "b")           # cached: one call
    assert Counter.n == 1
    assert j.ask("applies", "c", "d")[0] == "unsure"                 # over the limit: unsure, not a guess


def test_scan_logs_judge_answers():
    tmp = pathlib.Path(tempfile.mkdtemp()); (tmp / "p" / "fam").mkdir(parents=True); (tmp / "s").mkdir()
    (tmp / "p/fam/v1_2023-01-01.txt").write_text(OLD["text"]); (tmp / "p/fam/v2_2026-01-01.txt").write_text(NEW["text"])
    for s in SOPS: (tmp / "s" / f"{s['id']}.txt").write_text(s["text"])
    judge = FakeJudge(lambda k, a, b: "yes" if "alarms" in b else "no")
    r = scan.scan_workspace(tmp / "p", tmp / "s", tmp / "out", judge=judge)
    assert r["summary"][0]["affected_sops"] == ["alarms"]
    events = [json.loads(l) for l in (tmp / "out/audit.jsonl").read_text().splitlines()]
    assert any(e["event"] == "judge_answer" and e["answer"] == "yes" for e in events)
    assert "What the language-model check decided" in (tmp / "out/report.md").read_text()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok  ", name)
    print("all judge tests passed")

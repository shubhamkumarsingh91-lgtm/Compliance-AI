"""End-to-end tests for the compliance agent. Run from the repo root:  python3 tests/test_agent.py
Exact-text checks on purpose: a substring check passed a broken draft once ('mail a within 10 days')."""
import asyncio, hashlib, json, pathlib, shutil, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from compliance_agent import scan, store

DEMO = ROOT / "demo_workspace"


def tree_hash(p):
    return {str(f.relative_to(p)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(p.rglob("*")) if f.is_file()}


def test_scan_and_safety():
    tmp = pathlib.Path(tempfile.mkdtemp()); ws = tmp / "ws"; shutil.copytree(DEMO, ws); out = tmp / "out"
    before = tree_hash(ws)
    r = scan.scan_workspace(ws / "policies", ws / "sops", out)
    assert tree_hash(ws) == before, "scan must never change the user's files"
    assert r["compared"] == 4, r
    d = {p.name: p.read_text() for p in (out / "drafts").iterdir()}
    claim = [v for k, v in d.items() if k.startswith("claim_packet") and k.endswith("draft.txt")][0]
    assert claim == "Submit Form X electronically within 10 days of the date of service.\nKeep the mailing receipt in the claim file.\n", claim
    fd = [v for k, v in d.items() if k.startswith("front_desk_visit_check") and k.endswith("draft.txt")][0]
    assert fd.startswith("Front desk staff verify the visit count against the 20-visit prior authorization threshold"), fd
    pa = [v for k, v in d.items() if k.startswith("pa_request_submission") and k.endswith("draft.txt")][0]
    assert pa.startswith("Submit prior authorization requests within 3 business days of the 20th visit."), pa
    flagged = {u["sop_id"] for p in json.loads((out / "report.json").read_text()) for u in p["updates"]}
    assert "patient_statements" not in flagged and "timely_filing_check" not in flagged, flagged
    r2 = scan.scan_workspace(ws / "policies", ws / "sops", out)
    assert r2["compared"] == 0 and r2["already_done"] == 4, r2
    assert "4 (0 new" in (out / "report.md").read_text(), "report must stay cumulative on rescan"
    return ws, out


def test_apply_requires_approval():
    ws, out = test_scan_and_safety()
    sop = ws / "sops" / "claim_packet.txt"
    draft = [p for p in (out / "drafts").iterdir() if p.name.startswith("claim_packet") and p.name.endswith("draft.txt")][0]
    try:
        scan.apply_draft(sop, draft, "  ", out); raise SystemExit("apply without approver must fail")
    except ValueError:
        pass
    scan.apply_draft(sop, draft, "Test Approver", out)
    assert "mail a paper copy" not in sop.read_text()
    assert (ws / "sops" / "claim_packet.txt.bak").exists()
    log = [json.loads(l) for l in (out / "audit.jsonl").read_text().splitlines()]
    assert any(e["event"] == "applied" and e["approved_by"] == "Test Approver" for e in log)


def payload(res):
    sc = getattr(res, "structured_content", None) or getattr(res, "structuredContent", None)
    return json.dumps(sc) if sc else res.content[0].text


def test_mcp_over_stdio():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def go():
        params = StdioServerParameters(command=sys.executable, args=["-m", "compliance_agent.mcp_server"], cwd=str(ROOT))
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = {t.name for t in (await s.list_tools()).tools}
                assert {"compare_policy_text", "scan_workspace", "suggest_sop_updates", "apply_draft", "read_audit_log",
                        "list_policy_versions", "compare_policy_files"} <= tools, tools
                res = await s.call_tool("compare_policy_text", {"old_text": "Claims are due within 30 days.", "new_text": "Claims are due within 45 days."})
                assert "30 -> 45" in payload(res), res
                out = tempfile.mkdtemp()
                res = await s.call_tool("scan_workspace", {"policies_dir": str(DEMO / "policies"), "sops_dir": str(DEMO / "sops"), "out_dir": out})
                assert "report.md" in payload(res)
    asyncio.run(go())


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok  ", name)
    print("all agent tests passed")

"""MCP server: lets any MCP-capable assistant or tool use the compliance agent.

Run:   python3 -m compliance_agent.mcp_server          (stdio)
Add to an MCP client config as:  {"command": "python3", "args": ["-m", "compliance_agent.mcp_server"]}

Language-model check: set COMPLIANCE_JUDGE=hf (local open model) or api (hosted model) before starting; default is none
(rules only). The judge only answers yes/no/unsure; see judge.py.

Safety design: every tool is read-only or writes only to the out folder, except apply_draft, which needs a named approver,
keeps a backup, and writes an audit log line.
"""
import json, pathlib
try:                                       # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:                        # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server
from . import store, scan
from .engine import run_engine
from .judge import make_judge

mcp = _Server("compliance-agent")


@mcp.tool()
def compare_policy_text(old_text: str, new_text: str) -> dict:
    """Compare two versions of a policy text. Returns the list of substantive changes (numbers, dates, counts,
    added or removed requirements) and anything uncertain that a person should check. Ignores wording-only changes."""
    r = run_engine(dict(text=old_text), dict(text=new_text), [])
    return dict(changes=r["changes_summary"], needs_review=r.get("needs_review", []))


@mcp.tool()
def compare_policy_files(old_path: str, new_path: str) -> dict:
    """Same as compare_policy_text but reads two files (txt, md, pdf, docx)."""
    return compare_policy_text(store.read_text(old_path), store.read_text(new_path))


@mcp.tool()
def list_policy_versions(policies_dir: str) -> dict:
    """Lists policy families (sub-folders) and their versions, oldest to newest."""
    return {f: [p.name for p in ps] for f, ps in store.list_versions(policies_dir).items()}


@mcp.tool()
def suggest_sop_updates(old_path: str, new_path: str, sops_dir: str) -> dict:
    """For one old and one new policy file, find which SOPs are affected and suggest updated text with a diff and review
    flags. Writes nothing."""
    sops = store.load_sops(sops_dir)
    return scan.compare(store.as_doc(old_path, "doc", 1), store.as_doc(new_path, "doc", 2), sops, judge=make_judge())


@mcp.tool()
def scan_workspace(policies_dir: str, sops_dir: str, out_dir: str, force: bool = False) -> dict:
    """Scan every policy family, compare each new version with the previous one, and write report.md, report.json, drafts
    and patches into out_dir. Already-compared versions are skipped unless force is true. Never edits SOP files."""
    return scan.scan_workspace(policies_dir, sops_dir, out_dir, force, judge=make_judge())


@mcp.tool()
def read_audit_log(out_dir: str, limit: int = 50) -> list:
    """Returns the last entries of the audit log (what was compared, what was applied, by whom)."""
    p = pathlib.Path(out_dir) / "audit.jsonl"
    if not p.exists(): return []
    return [json.loads(l) for l in p.read_text().splitlines()[-limit:]]


@mcp.tool()
def apply_draft(sop_path: str, draft_path: str, approved_by: str, out_dir: str) -> dict:
    """Overwrites an SOP file with a suggested draft. ONLY call this after a human has reviewed the diff and approved it;
    pass that person's name in approved_by. A .bak backup is kept and the action is logged."""
    return scan.apply_draft(sop_path, draft_path, approved_by, out_dir)


if __name__ == "__main__":
    mcp.run()

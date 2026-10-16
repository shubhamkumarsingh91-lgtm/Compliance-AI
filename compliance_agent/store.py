"""Reading documents from folders. Keeps 'where documents come from' separate from 'what we do with them',
so other sources (Google Drive, SharePoint, a git repo, an API) can be added without touching the engine.

Folder convention:
    policies/<policy_family>/<anything with a version>.(txt|md|pdf|docx)
    sops/<sop name>.(txt|md|pdf|docx)           one file per SOP
Versions are ordered by a date in the file name (2026-01-01), else a version number (v2), else the file's modified time.
"""
import hashlib, pathlib, re

SUPPORTED = {".txt", ".md", ".pdf", ".docx"}


def read_text(path):
    p = pathlib.Path(path)
    ext = p.suffix.lower()
    if ext in (".txt", ".md"):
        return p.read_text(encoding="utf-8", errors="replace")
    if ext == ".pdf":
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)
    if ext == ".docx":
        import docx
        return "\n".join(par.text for par in docx.Document(str(p)).paragraphs)
    raise ValueError(f"unsupported file type: {ext}")


def sha(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _order_key(path):
    name = path.stem
    d = re.search(r"(20\d\d|19\d\d)[-_.]?(\d\d)[-_.]?(\d\d)", name)
    if d: return (0, "".join(d.groups()), 0, "")
    v = re.search(r"(?:^|[^a-z])v(?:ersion)?[ _-]?(\d+)(?:[._](\d+))?", name, re.I)
    if v: return (1, "", int(v.group(1)) * 1000 + int(v.group(2) or 0), "")
    return (2, "", int(path.stat().st_mtime), name)


def list_versions(policies_dir):
    """{family: [paths oldest to newest]}. A family is a sub-folder, or 'default' for files directly in the folder."""
    root = pathlib.Path(policies_dir)
    fam = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            f = p.parent.name if p.parent != root else "default"
            fam.setdefault(f, []).append(p)
    return {f: sorted(ps, key=_order_key) for f, ps in fam.items()}


def load_sops(sops_dir):
    out = []
    for p in sorted(pathlib.Path(sops_dir).rglob("*")):
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            out.append(dict(id=p.stem, title=p.stem.replace("_", " "), text=read_text(p), path=str(p)))
    return out


def as_doc(path, family="doc", version=1):
    t = read_text(path)
    return dict(id=pathlib.Path(path).stem, title=pathlib.Path(path).name, text=t,
                metadata=dict(policy_family=family, version=version, path=str(path), sha=sha(t)))

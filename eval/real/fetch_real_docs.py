# Disclaimer: Independent personal project. Public documents only. Run on Kaggle with Internet on.
# Downloads public PDFs listed in real_pairs.json and extracts text for each pair.
import json, pathlib, sys, subprocess
try:
    import pypdf
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pypdf"]); import pypdf
import urllib.request

HERE = pathlib.Path(__file__).parent
OUT = HERE / "out"

def pdf_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (personal research project)"})
    data = urllib.request.urlopen(req, timeout=60).read()
    tmp = OUT / "_tmp.pdf"; tmp.write_bytes(data)
    r = pypdf.PdfReader(str(tmp))
    return "\n".join((p.extract_text() or "") for p in r.pages)

for pair in json.loads((HERE / "real_pairs.json").read_text())["pairs"]:
    if not (pair.get("old_url") or pair.get("old_path")) or not pair.get("new_url"):
        print("SKIP", pair["name"], "- missing url"); continue
    d = OUT / pair["name"]; d.mkdir(parents=True, exist_ok=True)
    try:
        old_text = (HERE.parent / pair["old_path"]).read_text() if pair.get("old_path") else pdf_text(pair["old_url"])
        (d / "old.txt").write_text(old_text)
        (d / "new.txt").write_text(pdf_text(pair["new_url"]))
        (d / "answer_key.TEMPLATE.json").write_text(json.dumps(
            {"changes": [{"id": "k1", "desc": "WRITE BY HAND before running", "key_terms": []}],
             "affected": [], "edits": {}}, indent=2))
        print("OK  ", pair["name"], len((d / "old.txt").read_text()), "and", len((d / "new.txt").read_text()), "chars")
    except Exception as e:
        print("FAIL", pair["name"], repr(e))
print("Next: read old.txt and new.txt, write your own answer_key.json from what actually changed, THEN run the pipeline.")

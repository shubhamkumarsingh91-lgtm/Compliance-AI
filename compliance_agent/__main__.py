import argparse, json, sys
from . import scan

def main():
    ap = argparse.ArgumentParser(prog="compliance_agent", description="Scan policies, map to SOPs, suggest updates.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("policies"); s.add_argument("sops"); s.add_argument("--out", default="out"); s.add_argument("--force", action="store_true")
    a = ap.parse_args()
    r = scan.scan_workspace(a.policies, a.sops, a.out, a.force)
    print(json.dumps(r, indent=1)); print("\nOpen", r["report"])

if __name__ == "__main__":
    main()

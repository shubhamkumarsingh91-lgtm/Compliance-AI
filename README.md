# AI-Native Compliance Infrastructure

> **Disclaimer:** Independent personal project for self-learning. Not affiliated with any employer, state agency or vendor. Uses only public documents and synthetic data. No internal or confidential data and no personal data (no SSNs, member or patient records, PHI/PII). Views are my own. See DISCLAIMER.md.

A RAG prototype that detects Medicaid policy changes between document versions, finds the
internal procedures (SOPs) those changes affect, and drafts updated procedure text with
citations to the source policy.

Built on a free Kaggle GPU using only public CMS-style policy text and synthetic internal
procedures.

## The problem

When a Medicaid policy changes, someone has to read it, work out which internal procedures
are affected, and rewrite them by hand. That is slow and easy to get wrong, and mistakes
show up later as audit findings.

## How it works

![Swim-lane diagram of the pipeline and what is done vs next](docs/swimlane.png)

Green solid boxes are built and tested. Amber dashed boxes are next steps.

1. **Ingest** - split policy text into chunks and embed them (all-MiniLM-L6-v2, FAISS)
2. **Detect changes** - compare old and new versions of the same policy with an LLM
3. **Map impact** - for each SOP, structured JSON says affected or not, with a reason
4. **Draft** - rewrite only the affected numbers in each affected SOP, with citation
5. **Flag** - any sentence in a draft that does not closely match the original SOP is
   marked for human review

## Results on the sample data

Change tested: prior-authorization threshold raised from 15 to 20 visits.

- 2 of 3 SOPs flagged as affected (PT intake, claims appeals)
- The telehealth SOP was correctly left alone (an earlier string-matching bug flagged it;
  fixed with structured JSON output and a negation-aware fallback parser)
- The model still sometimes adds sentences the policy never asked for. These are caught by
  the new-clause flagger and shown to the reviewer, not silently accepted.

## Honest status

A full log of what went wrong and what I changed is in [docs/LESSONS_LEARNED.md](docs/LESSONS_LEARNED.md).

- Evaluated on 9 synthetic cases and 1 real public pair (MITA 2.0 to 3.0). Latest repeated run: 6 of 10 cases passed. The tool finds changes reliably (recall 1.0) but over-flags unaffected SOPs and does not reliably delete removed requirements. Details in eval/README.md.
- Not tested on real versioned CMS or state documents.
- Market need is **unvalidated**: a first practitioner conversation suggested the current
  manual process may already be good enough. Customer interviews come before more building.

## Repo layout

```
eval/        Test harness: 6 synthetic + 1 real (MITA 2.0 to 3.0) old/new policy cases with answer keys, scorer, real-document fetcher
notebooks/   Kaggle notebooks, in run order (starter, phase 3 diff, phase 4 drafting)
patches/     Paste-in cells: structured impact fix, stricter draft prompt + flagger
demo/        compliance_demo.html (redline view), compliance_dashboard.html - open in a browser
data/        compliance_results.json - output of a real run
docs/        Swim-lane diagram, project overview PDF, setup guide, LESSONS_LEARNED.md
```

## Run it

1. On Kaggle: Create > New Notebook > File > Import Notebook
2. Settings: Accelerator GPU T4 x2, Internet on (phone verification required)
3. Run the notebooks in order, then the two cells in `patches/`
4. Open `demo/compliance_demo.html` to view the redlines

## Stack

| Part | Choice |
|---|---|
| Generation | Qwen2.5-7B-Instruct, 4-bit |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 |
| Search | FAISS |
| Compute | Kaggle T4 x2 |

## Roadmap

- [x] Ingest, retrieve, change detection, impact mapping, draft generation
- [x] Fix wrong-SOP flagging; add human-review flags for invented clauses
- [x] Test harness built: 6 synthetic cases (certification, MITA-style, policy, control) with answer keys - see `eval/`
- [ ] Run the harness on the real model and publish the numbers
- [ ] Grow to 20+ cases and add real old/new public document pairs
- [ ] Run on real public versioned CMS documents
- [ ] Customer interviews (agency, vendor, other-state practitioners) - decide build, pivot or stop
- [ ] Hosted backend so results persist

---

*Independent personal project. No proprietary, client, employer or agency data, and no personal data of any kind, is used anywhere in this repository. See [DISCLAIMER.md](DISCLAIMER.md).*

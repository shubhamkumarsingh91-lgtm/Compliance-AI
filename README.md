# AI-Native Compliance Infrastructure

A RAG prototype that detects Medicaid policy changes between document versions, finds the
internal procedures (SOPs) those changes affect, and drafts updated procedure text with
citations to the source policy.

Built on a free Kaggle GPU using only public CMS-style policy text and synthetic internal
procedures. No proprietary, client or employer data is used anywhere in this repository.

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

- Prototype validated on **one synthetic change set**. No accuracy numbers yet.
- Not tested on real versioned CMS or state documents.
- Market need is **unvalidated**: a first practitioner conversation suggested the current
  manual process may already be good enough. Customer interviews come before more building.

## Repo layout

```
notebooks/   Kaggle notebooks, in run order (starter, phase 3 diff, phase 4 drafting)
patches/     Paste-in cells: structured impact fix, stricter draft prompt + flagger
demo/        compliance_demo.html (redline view), compliance_dashboard.html - open in a browser
data/        compliance_results.json - output of a real run
docs/        Swim-lane diagram, project overview PDF, slide deck PDF, setup guide
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
- [ ] Accuracy check: 10-15 hand-labelled changes, report hit rate
- [ ] Run on real public versioned CMS documents
- [ ] Customer interviews (agency, vendor, other-state practitioners) - decide build, pivot or stop
- [ ] Hosted backend so results persist

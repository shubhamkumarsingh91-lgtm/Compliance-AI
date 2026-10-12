# Evaluation harness

> Independent personal project. Public documents and synthetic data only. No internal, confidential or personal data. See ../DISCLAIMER.md.

Tests whether the pipeline (1) finds the real changes between an old and a new version of a policy,
(2) flags only the SOPs that are actually affected, and (3) edits those SOPs correctly, without
touching the others or inventing new requirements.

## How it works

Each folder in `cases/` is one test:

| File | What it is |
|---|---|
| `old.txt`, `new.txt` | Old and new version of a policy document |
| `sops.json` | Synthetic internal procedures, including ones that should NOT change |
| `answer_key.json` | What the right answer is, **written before the AI runs** |
| `case.json` | Category and notes |

The scorer (`score.py`) needs no GPU. It checks four things per case:
change recall, which SOPs were flagged (precision and recall), whether each edited SOP contains
the new value and no longer contains the old one, and whether any unaffected SOP got a draft.
It also counts sentences the model added that were not in the original (human-review flags).

## The six synthetic cases (plus one real case, below)

| Case | Category | What it tests |
|---|---|---|
| `cert_01_checklist_deadlines` | certification | Two timing changes plus a newly added criterion; one SOP must stay untouched |
| `mita_01_self_assessment_window` | MITA-style | Window 12 to 18 months, refresh cycle 5 to 3 years; one SOP must stay untouched |
| `policy_01_prior_auth_threshold` | policy | Threshold and deadline change; telehealth SOP is a distractor |
| `policy_02_new_requirement_added` | policy | A new obligation with no changed number - the hardest kind |
| `policy_03_requirement_removed` | policy | An obligation removed; the SOP must drop it |
| `control_01_wording_only` | control | Wording changes only; the correct answer is to flag nothing |

All text is invented. The cases are modeled on the kinds of changes that appear in real
CMS updates, but they are not real policy text.

## Run it

1. Check the scorer itself (no GPU): `python3 test_harness.py`
2. On Kaggle, run your pipeline cells, then paste `kaggle_run_eval.py` as a new cell.
   It prints a pass/fail table and saves `eval_results.json`.
3. Put the numbers in the main README. No numbers yet - none have been run on the real model.

`mock_pipelines.py` holds fake pipelines used only to prove the scorer works (an "oracle" that
reads the answer key and scores 100%, a "do nothing" that should pass only the control, and a
"flag everything" that should fail all). They say nothing about the AI.

## Real public documents

`real/real_pairs.json` lists candidate old/new pairs. `real/fetch_real_docs.py` downloads them on
Kaggle and extracts text. For real documents there is **no ready answer key**: read both versions,
write the answer key by hand from what actually changed, then run the pipeline. Never write the key
after seeing the AI's output.

Known gaps: the 2007 MECT files have not been located (the current CMS page lists only version 2.3),
and a true old/new pair of the same document still needs to be chosen and verified.

## Limits

- Six synthetic cases is a smoke test, not a benchmark. Expect to grow it to 20 or more.
- Matching is keyword-based, so a correct change described in different words can count as missed.
  Read the failures before trusting the percentages.
- Synthetic documents are cleaner than real ones. Real-document scores will likely be lower.

## First real case: MITA introduction (FM6), 2.0 to 3.0

`cases/real_mita_intro_2_0_to_3_0/` pairs the 2006 "FM6 - Introduction to MITA Framework 2.0" (18 pages) with
the 2012 "FM6 Introduction to the MITA Framework 3.0" (21 pages): same title, same format, two real versions,
both public CMS documents, already extracted to text. The verified change is eight business areas (2.0) to
ten (3.0). Both describe five maturity levels, so the maturity-scoring SOP must NOT be flagged. The answer key
was written from the documents before any AI run. SOPs are synthetic.

This is the hard test: about 10,500 words across the two documents, with a single number buried in prose.
Expect the model to struggle, and report the real score either way. If it fails, the likely fix is comparing
matching sections instead of whole documents.

More real pairs are available in the full MITA 2.0 and 3.0 packages (for example Part I Chapter 3, the maturity
model, where 3.0 revised the Level 4 and 5 definitions) but they change in wording rather than numbers, so each
needs a hand-written key before use.

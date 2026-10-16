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

## The synthetic cases (plus one real case, below)

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
   It runs every case twice (whole-document vs section-by-section comparison), prints pass/fail tables
   and saves `eval_results_whole.json` and `eval_results_sectioned.json`. The real MITA case makes about
   70 model calls in section mode, so allow roughly 10-15 minutes.
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

## Section-by-section comparison (`sectioned.py`)

Long documents overwhelm a 7B model when both versions go into one prompt. `sectioned.py` splits both
versions into ~180-word chunks, pairs each new chunk with its two most similar old chunks (TF-IDF), drops
identical pairs and wording-only pairs, and asks the model about each remaining pair. `python3 test_sectioned.py`
checks this without a GPU: on the real MITA documents the pair holding the 8-to-10 change is found, and the
wording-only control produces no pairs.

Honest limits: the matching settings were tuned on this one real pair, so treat that check as a sanity test and
not proof. In 2.0 the "eight business areas" evidence is a figure caption, while 3.0 states it in prose; a looser
match was needed to connect them, which costs more model calls (about 68). Pairs the filter drops can never be
reported, so a real change that looks like pure rewording can be missed.

## Rule-based engine (`engine.py`) - no GPU, no language model

The language model version made errors a program does not make: false alarms on wording-only changes, removed
requirements left in drafts, and different answers on identical input. So the facts that code can check are now decided
by rules, with the same answer every time:

| Job | How the engine does it |
|---|---|
| Find changes | Align sentences old to new. Same numbers + same meaning words = wording-only, ignored. Numbers or dates swapped = value change. A sentence with no match = added or removed. "No longer required" = removal notice. Counted things ("eight business areas" to "ten") are compared across the whole document, which catches changes buried in captions. |
| Ignore noise | Running headers and footers, figure/table/page numbers, descriptive prose, examples, glued-together bullet text. |
| Map to SOPs | A value change flags an SOP only if it states the old value AND shares words with the changed sentence. Added or removed requirements need a rare shared word. |
| Draft | Swap the number or date. Cut the clause the policy dropped. For an added requirement, copy the policy sentence word for word (never invented) and flag it. Every edit carries a VERIFY flag. |

Run it: `python3 run_engine_eval.py` (seconds, no GPU). Latest: **10 of 10 development cases and 8 of 8 blind cases pass, identical
across repeated runs.**

**How much to trust that number (read this).**
- The rules were tuned while looking at the 10 development cases, including the real MITA pair and the holdouts, so 10/10 there proves little.
- The 8 blind cases were written afterwards with varied phrasing. The first run failed one (a month change, January to October) which exposed a real gap; I fixed it, so the blind set is now also partly used up. Fresh cases are needed for an unbiased number.
- One blind case passed by luck: an added requirement whose SOP used different words (identity check vs photo ID) was matched only because both mentioned "patient". Rules cannot judge meaning.
- Known limits: a heavily reworded sentence can look like a change; a requirement added in words the SOP never uses is missed; long glued-together PDF passages are reported but not mapped; the engine has never seen a real SOP.

The planned hybrid: rules decide everything checkable, and a language model (any size, since hardware is no longer the limit) is asked only narrow yes/no questions about uncertain pairs, such as "does this added requirement apply to this SOP?", with its answer logged for review.

## Results log (real runs on Qwen2.5-7B-Instruct 4-bit, Kaggle T4 x2)

Numbers here come from actual runs, not estimates.

### Run 1 - original prompts, whole-document comparison, 7 cases: 4 passed, 3 failed

| Case | Result | What happened |
|---|---|---|
| cert_01_checklist_deadlines | pass | |
| control_01_wording_only | pass | correctly flagged nothing |
| mita_01_self_assessment_window | pass | |
| policy_01_prior_auth_threshold | pass | |
| policy_02_new_requirement_added | FAIL | change detected, but the SOP was not flagged: no draft |
| policy_03_requirement_removed | FAIL | SOP drafted, but the removed requirement was still in the draft |
| real_mita_intro_2_0_to_3_0 | FAIL | out of memory: two documents of about 10,500 words in one prompt tried to allocate 26 GiB |

Averages: change recall 1.0, impact precision 0.83, impact recall 0.83, 7 invented clauses flagged for review.

What this means:
- The pipeline handles number and date changes on short synthetic text.
- The two synthetic failures were **prompt-design flaws of mine**, not only model weakness: the impact prompt
  flagged only SOPs that already mention the changed item, and the draft prompt said "change only numbers" and
  "add no new sentence", so it could not remove or add a requirement. Fixed in `patches/prompt_fix_v2_cells.py`.
- Comparing whole long documents in one prompt does not work at all on this hardware (out of memory), which is
  why section-by-section comparison exists.
- The section-by-section run (68 chunk pairs on the real case) had not finished when results were shared, so
  there is no score for it yet.

### Run 2 - prompt fix v2, whole-document comparison, 10 cases (one run each): 4 passed, 6 failed

| Case | Run 1 | Run 2 | Run 2 failure |
|---|---|---|---|
| cert_01_checklist_deadlines | pass | FAIL | program-integrity SOP (new EVV criterion) not flagged |
| mita_01_self_assessment_window | pass | FAIL | maturity-scoring SOP wrongly flagged and redrafted |
| policy_01_prior_auth_threshold | pass | pass | |
| policy_02_new_requirement_added | FAIL | FAIL | SOP not flagged |
| policy_03_requirement_removed | FAIL | FAIL | removed requirement still in draft |
| control_01_wording_only | pass | pass | |
| policy_04_new_requirement_b (holdout) | - | pass | |
| policy_05_requirement_removed_b (holdout) | - | FAIL | removed requirement still in draft |
| cert_02_mixed_changes (holdout) | - | pass | |
| real_mita_intro_2_0_to_3_0 | FAIL | FAIL | out of memory again (tried to allocate 26 GiB) |

Averages: change recall 1.0, impact precision 0.85, impact recall 0.85, 9 invented clauses flagged.

Honest reading:
- **The v2 prompts did not clearly help.** On the original six cases, run 1 passed 4 and run 2 passed 2. Two cases
  that passed before now fail. Holdouts passed 2 of 3 (the new-requirement and mixed cases passed; the removal case
  still left the removed text in the draft).
- **One run per prompt is too noisy to conclude much.** The model samples its output, so the same case can pass
  or fail by luck. A change of two cases between runs could be noise. The scorer now supports repeated runs
  (`REPEATS`, default 3) and reports pass rate and "flaky" cases, so prompts can be compared fairly.
- **Likely real problems, to confirm with repeats:** removed requirements are not reliably deleted from drafts
  (3 failures across two prompt versions), and the v2 impact wording may over-flag related-but-unaffected SOPs
  (the maturity-scoring SOP).
- **Whole-document comparison of the real MITA pair cannot run on this hardware** (out of memory in both runs).

### Run 2, section-by-section mode: 5 of 10 passed

On the nine short synthetic cases, section mode sees exactly the same text as whole-document mode (one chunk pair
each, zero for the wording-only control), so it is the same pipeline with a different random draw. The two runs
disagreed on four cases (cert_01 and policy_03 passed here and failed above; policy_04 failed here and passed
above; policy_01 and others matched). **That disagreement on identical inputs is direct evidence that single runs
are noisy.**

The real MITA case **ran out of memory in section mode too** (tried to allocate 18 GiB). The 68 chunk
comparisons are small (largest pair 412 words); the overflow came from merging up to 68 verbose model findings
into one prompt for the impact step. Fixed in `sectioned.py`: a finding is kept only if it mentions a number or
obligation word that really changed in that chunk pair, duplicates are dropped, and the merged summary is capped
at about 900 tokens. `python3 test_sectioned.py` checks the cap and that the real 8-to-10 finding survives, using
a simulated verbose model. This fix has not yet been run on the real model.

### Run 3 - whole-document, 3 repeats each: 6/10 passed (stable)

Change recall 1.0, impact recall 1.0, impact precision 0.889. Stable failures (same result in all 3 runs):
**policy_05_requirement_removed_b 0/3** (a holdout: the removed requirement stays in the draft, so the v2 prompt
fixed only the case it was tuned on) and **control_01_wording_only 0/3** (false alarm on a non-change).
cert_01 is flaky (2/3, occasionally flags an unaffected SOP). The real MITA case ran out of memory, as expected.

### Run 3 - section mode, 1 run each: 6/10 passed, no crash

The capped summary fixed the out-of-memory error on the real case (it completed). But section mode failed
policy_03, 04 and 05 with "no draft produced": on short documents there is no matching chunk for an added or
removed sentence, or the grounding filter dropped the finding. **This corrects the Run 2 note above that section
mode sees the same text as whole-document mode on short cases.** Fix: documents under about 1,500 words are now
compared whole. On the real MITA case, 68 chunk pairs were checked, only 4 findings were kept, and the 8 to 10
change was missed (sop_i2, the maturity-scoring SOP, was also wrongly flagged). Kept findings are now printed so
we can see whether the model or the filter caused the miss.

See `docs/LESSONS_LEARNED.md` for the full list of problems and fixes.

### Next
1. Rerun with `REPEATS = 3` for stable pass rates on the synthetic cases (do not change prompts before this).
2. Rerun the real MITA case in section mode with the capped summary.

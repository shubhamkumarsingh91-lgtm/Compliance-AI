# Build log: every change, why it was made, and where the code is

> Independent personal project for self-learning. Public and synthetic data only. No employer, agency or personal data. See [DISCLAIMER.md](../DISCLAIMER.md).

This is the single place to see what changed, why, and where. It is written so you can learn from it.

## 1. How to see any change yourself (no need to ask me)

| What you want | How |
|---|---|
| Every change, newest first | GitHub, your repo, click "Commits" (or open `https://github.com/shubhamkumarsingh91-lgtm/Compliance-AI/commits/main`) |
| Exactly which lines changed in one change | Click a commit, then "Files changed". Green = added, red = removed |
| Same thing in a terminal | `git log --oneline`, then `git show <hash>` for that change, or `git show <hash> --stat` for the file list |
| What a file looked like before | `git show <hash>:path/to/file` |
| Compare any two points | `git diff <old-hash> <new-hash> -- path/to/file` |

Rule from now on: **every batch of changes gets an entry in section 4 below before it is committed**, with what, why, where, and the test result.

## 2. What this project is, in six lines

1. A policy document changes (a number, a date, a requirement added or removed).
2. The agent compares the old and new version and lists the real changes, ignoring rewording.
3. It finds which of your internal procedures (SOPs) are affected.
4. It suggests the updated SOP text as a diff, with review flags. A person approves.
5. Everything is logged. Nothing is changed in your files without a named approver.
6. It can be used from the command line or as an MCP connector from any MCP-capable assistant.

## 3. Code map: where each piece lives

| File | What it does | Key functions |
|---|---|---|
| `compliance_agent/engine.py` | The rule engine: finds changes, maps SOPs, drafts edits. No AI model, no GPU | `sentences`, `diff_policy`, `quantity_changes`, `affected_sops`, `draft_sop`, `run_engine` |
| `compliance_agent/store.py` | Reads txt, md, pdf, docx; lists policy versions in order; loads SOPs. Where new sources (Drive, SharePoint, git) will plug in | `read_text`, `list_versions`, `load_sops` |
| `compliance_agent/scan.py` | Compares each new version to the previous, writes report, drafts, patches, audit log; approval-gated apply | `scan_workspace`, `compare`, `apply_draft` |
| `compliance_agent/mcp_server.py` | MCP connector with 7 tools | `compare_policy_text`, `suggest_sop_updates`, `scan_workspace`, `apply_draft` ... |
| `compliance_agent/__main__.py` | Command line: `python3 -m compliance_agent scan ...` | |
| `tests/test_agent.py` | End-to-end tests: scan safety, exact drafts, approval, audit, MCP over stdio | |
| `eval/score.py` | Scores any pipeline against answer keys (no GPU) | `score_case`, `run_eval` |
| `eval/cases/`, `eval/blind/` | 10 development cases (one real MITA pair) and 8 blind cases, each with an answer key | |
| `eval/generate_cases.py` | Makes 1,000+ labeled test cases automatically | `make`, `run` |
| `eval/run_engine_eval.py` | Runs the engine on all hand-written cases | |
| `eval/generate_documents.py` | Builds whole synthetic manuals plus SOP libraries in the agent's folder layout and scores the real scan | `generate_workspace`, `run` |
| `compliance_agent/judge.py` | The optional language-model check (yes/no/unsure questions only) | `Judge`, `HFJudge`, `ApiJudge` |
| `eval/sectioned.py`, `eval/kaggle_run_eval.py` | The language-model route for Kaggle: section-by-section comparison and the run cell | `make_sectioned_detector` |
| `notebooks/` , `patches/` | The original Kaggle notebooks (language-model pipeline) and the prompt fixes | |
| `demo_workspace/` | Sample policies and SOPs to try the agent on | |
| `docs/` | This log, design document, lessons learned, setup guide | |

## 4. Change ledger (oldest first)

### A. Before Kaggle testing: build and package

| Commit | What changed | Why | Where |
|---|---|---|---|
| 1274060 | Reorganized repo; swim-lane diagram; new README; notebooks, demo pages, results | Make the project showable on GitHub | `notebooks/`, `demo/`, `docs/`, `README.md` |
| e748ae4 | Added the disclaimer everywhere | Your rule: every project states it is independent, public and synthetic data only | `DISCLAIMER.md`, first cell of every notebook, demo banners |
| a74726e | Built the evaluation harness: scorer, 6 synthetic cases, mock pipelines | One example proves nothing; answer keys written before the AI runs make grading fair | `eval/score.py`, `eval/cases/`, `eval/test_harness.py` |
| b4da08a, 2476b85, 9935093 | Added the real MITA 2.0 vs 3.0 case with a verified answer key (8 business areas became 10) | Test on real public documents, not only invented ones | `eval/cases/real_mita_intro_2_0_to_3_0/` |

### B. Changes caused by what happened when you ran things on Kaggle

| Run result on Kaggle | Commit | What I changed | Why | Where |
|---|---|---|---|---|
| Run 1: 4 of 7 passed. The AI left removed requirements in drafts and missed added ones | 8a36a79 | New prompts (v2): an SOP is affected if a change alters something it states OR adds/removes a requirement for its activity; the draft may delete a removed requirement or add one sentence. Added 3 holdout cases the prompts were never tuned on | My first prompts forbade removing or adding requirements, which real policy changes do | `patches/prompt_fix_v2_cells.py`, `eval/cases/cert_02`, `policy_04`, `policy_05` |
| Same commit: one out-of-memory case broke the next | 8a36a79 | After each case, free GPU memory | One crash should fail one case, not the whole run | `eval/score.py` `_run_once` |
| Run 2: same cases passed in one run and failed in the next | 28ae400 | Repeat each case 3 times and report always-pass, flaky, never-pass | The model samples, so a single run can be luck | `eval/score.py` `run_eval`, `eval/kaggle_run_eval.py` |
| Whole-document comparison of the real MITA pair ran out of GPU memory (26 GiB asked) | 1575dcf | Section-by-section comparison: split into ~180-word chunks, match with TF-IDF, compare only matched chunks | The prompt was 10,500 words. Smaller pieces fit | `eval/sectioned.py`, `eval/test_sectioned.py` |
| Section mode ran out of memory too (18 GiB) | c14f283 | Keep a finding only if it mentions a really-changed number or obligation, drop duplicates, cap the merged summary at about 3,500 characters | 68 verbose findings merged into one prompt overflowed memory | `eval/sectioned.py` `make_sectioned_detector` |
| `TypeError: unexpected keyword argument 'repeats'` | 79c9af2 | The run cell now clears cached modules before importing | Python had kept the old version of `score.py` in memory | `eval/kaggle_run_eval.py` |
| Run 3 section mode: policy_03, 04, 05 failed with "no draft produced" | 6608069 | Documents under 1,500 words are compared whole; print the findings kept | Chunk matching hid added and removed sentences in short documents | `eval/sectioned.py` |
| Whole-document run was slow and always failed the real case | 9249d3c | `SKIP_WHOLE = True` runs only section mode | Saves time and memory | `eval/kaggle_run_eval.py` |

What the Kaggle results taught us (plain words): the AI model found every change (recall 1.0) but made errors a program does not make: false alarms on wording-only changes, removed requirements kept in drafts, and different answers on identical input. Those are not problems more memory fixes. That is why the next step moved the exact work out of the model.

### C. Documentation

| Commit | What | Why |
|---|---|---|
| 4628c42 | Lessons learned log; Run 3 results | Keep failures visible and learn from them |
| d281db1, c33481c, f469403 | Design document (markdown and PDF): goal, objectives, scope, impact, phases 0 to 2 in detail | One document that explains why and how |

### D. The rule engine (no AI model) and scale testing

| Commit | What changed | Why | Where |
|---|---|---|---|
| f17d1ff | Built `engine.py`: aligns sentences old to new; treats same numbers plus same meaning words as wording-only; numbers and dates compared as facts; counted things ("eight" to "ten business areas") compared across the whole document; removal notices; header/footer cleaning; added requirements copied word for word and flagged. Added 8 blind cases | Do exact work with code so the answer is identical every run | `compliance_agent/engine.py` (first in `eval/`), `eval/blind/`, `eval/run_engine_eval.py` |
| d991233 | Test generator: 1,000+ labeled cases per seed; engine fixes found by it (paraphrases flagged as changes, distractor SOPs matched on one common word, two changes colliding on one number); in-sentence differences now listed as "needs review" instead of treated as changes | Ten hand-written cases cannot show reliability; a generator finds bugs you would not think of | `eval/generate_cases.py`, `engine.py` (`uncertain` kind, `GENERIC_VERBS`, best-match filter) |

Result: 10/10 development, 8/8 blind, 97.6% to 98.3% on 4,000 generated cases. The only failures are an added requirement worded with none of the SOP's words, which rules cannot connect.

### E. The agent and MCP connector

| Commit | What changed | Why | Where |
|---|---|---|---|
| 6c4d06d | New package: folder scan, report, drafts, patches, audit log, approval-gated apply, 7 MCP tools, tests, demo workspace. Moved `engine.py` into the package | Turn the engine into something that scans documents and suggests changes | `compliance_agent/`, `tests/test_agent.py`, `demo_workspace/` |
| 6c4d06d | Bugs found by running it on a real folder and fixed: removal left "mail a within 10 days"; report overwritten on rescan; misleading "not edited" flag; trailing newline lost | The case scores had not caught them (a substring test passed the broken text) | `engine.py` `diff_policy`, `_remove_span`, `draft_sop`; `scan.py` `scan_workspace`; exact-text tests |

### F. Language-model check (judge)

### 2026-10-16 Language-model check for the cases rules cannot decide
What changed:   New `compliance_agent/judge.py`. The engine now takes an optional `judge` and asks it three narrow yes/no questions: (1) a new or removed requirement matched no SOP by words: does it apply to this SOP anyway; (2) an SOP was linked by only one shared word: is the link real; (3) same numbers but different words: is it the same requirement. Backends: none (default), fake (tests), `hf` (local open model, reuses the notebook's loaded Qwen), `api` (hosted model). CLI flag `--judge`, MCP env var `COMPLIANCE_JUDGE`.
Why:            After rule fixes, the only failures left in 4,000 generated cases were added requirements worded with none of the SOP's words (0% for rules). Rules cannot judge meaning.
Where:          `compliance_agent/judge.py` (all of it); `engine.py`: `_judge_pass`, `run_engine(..., judge=None)`, `Reason` class (remembers how many words linked a change to an SOP), `draft_sop` flags; `scan.py` (judge answers into audit log and report); `mcp_server.py`, `__main__.py` (switches).
Safety rules:   The judge answers yes / no / unsure and a one-line reason. It never writes SOP text: added text is copied word for word from the policy and flagged "the model judged that it applies". "Unsure" never adds or removes anything. Unreadable output counts as "unsure". Answers are cached (same question, same answer) and every answer is logged.
Tested by:      `python3 tests/test_judge.py` (7 tests with fake judges: strict parsing, rules miss the fire-drill case and the judge fixes it, an always-"no" judge cannot break correct rule matches, weak link dropped only on "no", reworded sentence suppressed only on "yes", no judge = identical results, call limit and cache, audit log). `generate_cases.py --oracle-judge` gives 1000/1000, which proves the plumbing only. Existing results unchanged: 10/10, 8/8, 98% on generated cases without a judge.
Risk / limits:  NOT yet measured with a real model. The `hf` and `api` backends have not been run in this repo's environment. A real model can answer wrongly. Next: run `eval/kaggle_run_judge.py` on Kaggle and compare "rules only" with "rules + judge" per case type before trusting it.

### G. Realistic manuals (long documents with sections, bullets and page headers)

### 2026-10-16 Whole-manual generator, sentence-splitting fix, faster SOP matching
What changed:   (1) New `eval/generate_documents.py`: builds 200 synthetic organisations per run, each with a policy manual (v1 and v2: section headings, bullets, running page headers, 25-40 sentences) and its own SOP library, written in the agent's real folder layout, then scored from the real `report.json` against an exact answer key. (2) Engine fix: sentence splitting. (3) Engine fix: SOP matching rewritten around a precomputed index. (4) Number-match rule: the SOP sharing the most words with a changed sentence wins; generic verbs ("keep", "send") no longer count as shared evidence.
Why:            The tiny-case score (98%) hid a problem. On realistic manuals the agent scored 74%: headings and bullets were glued onto the next sentence, so a number from one place ended up compared with the words of another. Separately, matching one change against a library of 1,600 SOPs timed out because word sets were recomputed for every pair.
Where:          `compliance_agent/engine.py`: `blocks`, `_is_heading`, `sentences` (headings label a section and are not requirements; bullets start a new block; hard-wrapped lines are joined), `SopIndex` and `_rare_terms` (computed once per run), `affected_sops` (value hits use the same best-match rule as word hits). `eval/generate_documents.py` (all).
Tested by:      `python3 eval/generate_documents.py 200 <seed>`. Before the fix: 73.8%. After: 96.7%, 98.5% and 97.6% on seeds 3, 5 and 8 (about 670 checks each). Number, date, removal, silent removal and added-requirement changes: 100% in every seed checked. Earlier suites unchanged: 10/10, 8/8, 98.2% on 1,000 tiny cases, both test files pass.
Risk / limits:  Remaining misses are all false alarms (about 1 in 10 manuals): an SOP linked to an added requirement by one shared word ("proof" in "submit proof of insurance" vs "keep proof of delivery"). That is exactly the "weak link" question the language-model check is for; it has not been run with a real model yet. These manuals are built from my templates, so the score shows robustness on this shape of document, not accuracy on real manuals. Heading detection is a heuristic and could mis-handle unusual layouts; real PDFs need more testing.

## 5. What is coming next (and which files will change)

| Step | What | Files that will change or be added | Why this order |
|---|---|---|---|
| 1 (built, awaiting real-model measurement) | Language-model check for the one failure type left (a new requirement worded with none of the SOP's words): ask a model one narrow yes/no question per uncertain pair, log its answer | `compliance_agent/judge.py` (new), `engine.py` (call it for uncertain pairs), tests with a fake model so tests need no GPU | Closes the last known failure type; any model size works |
| 2 | Real document pairs at scale: you collect old and new public versions, I add a loader and a labeling sheet, then measure | `eval/real/`, a labeling template | Only real pairs prove real-world accuracy |
| 3 | Web review screen: each diff with Approve / Reject, reviewer name, comments, audit trail | `compliance_agent/web.py` (new), `tests/` | A person-friendly front for the approval step |
| 4 | More sources: Google Drive, SharePoint, a git repo, web pages with change detection | `compliance_agent/store.py` and new source files | Documents live in many places |
| 5 | Product foundations for real customers: each customer's data kept separate, login, access control, encrypted storage, usage and accuracy reporting | new modules and `docs/` | Needed before any customer's documents touch it |

## 6. About your goal: a real-world agent that helps companies and can be sold

I understand it: help companies carry less compliance workload, and build something of real value. The path there is clear, and the build log above is part of it, because a buyer will want to see exactly what the system does and how it was tested. Three things a company will ask for: proof of accuracy on documents like theirs (step 2), a human approval and audit trail (built), and data safety (step 5).

One thing I will keep repeating because it protects the project: your employment. Before any company, demo or pilot involves Medicaid or anything near your agency's work, ask your employer's ethics office or a lawyer. I am not a lawyer. Choosing the target industry carefully is part of building this properly.

## 7. Entry template for future changes

```
### <date> <commit> <short title>
What changed:   <one or two lines>
Why:            <the problem it solves, with the evidence>
Where:          <files and functions>
Tested by:      <test or run and the result>
Risk / limits:  <what could still go wrong>
```

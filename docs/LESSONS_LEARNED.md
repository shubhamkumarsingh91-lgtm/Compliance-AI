# Lessons learned

Independent personal learning project. Public and synthetic data only, no employer or agency data, no SSNs/PHI/PII. See DISCLAIMER.md.

This is a running log of what went wrong while building and testing this tool, why, and what I changed. Failures are kept on purpose: they show where the tool can and cannot be trusted.

## A. Testing and evaluation lessons

1. **One run proves nothing.** The model samples its answers. The same case passed in one run and failed in the next on identical input. Fix: run each case 3 times and report pass rates ("always pass", "flaky", "never pass"). Only failures that repeat are treated as real problems.
2. **Tuning prompts on the failing test overfits.** The v2 prompt fixed the removed-requirement case I tuned it on (policy_03, 3/3) but not its twin (policy_05, 0/3). Fix: keep holdout cases the prompts were never tuned on, and do not change prompts again until repeated runs show stable failures.
3. **Write the answer key before running the AI**, and test the scorer itself with fake pipelines (perfect, do-nothing, flag-everything) so a scoring bug is not mistaken for an AI bug.
4. **Include a control case.** A wording-only change must produce no flags. It fails 0/3 in whole-document mode: the tool raises false alarms on non-changes. In compliance work this is the costly error, because reviewers learn to ignore a noisy tool.
5. **Do not assume two modes behave the same.** I wrote that section mode "sees the same text" as whole-document mode on short cases. A later run showed it did not: it hid added and removed sentences. Check claims against data.

## B. Pipeline design lessons

6. **Recall is good, precision and drafting are the weak spots.** Change detection recall and impact recall were 1.0 in whole-document runs. The failures are over-flagging (unaffected SOPs flagged) and drafts that keep requirements the policy removed.
7. **Prompt wording can block the right behavior.** My first prompts told the model not to remove or add requirements, and only flagged SOPs that mentioned the changed number. Real policy changes add and remove requirements. Fix: v2 prompts that allow deletion and a single added sentence.
8. **String matching on model output is fragile.** An early version flagged an unaffected SOP because the model wrote a sentence saying it was not affected. Fix: structured JSON output plus a negation-aware fallback parser.
9. **Always flag new clauses.** The model sometimes invents sentences. A similarity-based flagger shows these to the reviewer instead of accepting them silently. Human review stays in the loop.
10. **Section mode helps long documents and hurts short ones.** Chunk matching found the real 8 to 10 MITA pair, but on short synthetic documents it found no matching chunk for added or removed sentences, and the grounding filter dropped the finding. Fix: documents under about 1,500 words are compared whole.
11. **Matching chunks is harder than it looks.** Greedy one-to-one matching missed the real pair (a caption versus prose). Non-exclusive TF-IDF with top-2 matches worked. Version labels (v1/v2), years and month names created false pairs on the wording-only control and are now ignored.

## C. Hardware and memory lessons

12. **"CUDA out of memory" is GPU memory, not computer RAM.** The free Kaggle T4 has about 14.5 GiB per GPU and cannot be upgraded. Buying RAM would not help.
13. **Whole-document comparison of the real MITA pair cannot fit.** The prompt was about 10,500 words and asked for 26 GiB. This is a design limit, not a hardware shortage: the fix is smaller prompts.
14. **Merging many model findings can overflow too.** 68 verbose findings merged into one impact prompt asked for 18 GiB. Fix: keep a finding only if it mentions a number or obligation that really changed, drop duplicates, cap the merged summary at about 3,500 characters (about 900 tokens). The fix worked: the section-mode run completed with no crash.
15. **A dead kernel loses everything in memory** (model, functions, variables). Files in the working folder usually survive. Re-run setup cells in order and wait for each to finish.

## D. Notebook and environment gotchas (Kaggle / Jupyter)

16. `%run -i /path/file.py` is a magic command. Typing only the filename runs it as Python and gives `NameError`.
17. A cell shown as Markdown will not run. Add a Code cell with "+ Code".
18. `[*]` means a cell is running or queued. Later cells wait behind it. Interrupt it before running another.
19. "Run All" stops at the first error. Session restarts wipe variables.
20. `!rm -rf` on the cloned repo means it must be cloned again before `%run`.
21. Python caches imports in `sys.modules`. After updating a file, an old version can still run (`TypeError: unexpected keyword argument 'repeats'`). Fix: pop the cached modules, now done inside `kaggle_run_eval.py`.
22. The Kaggle Internet and GPU switches must be on for cloning and model loading.

## E. Data and process lessons

23. **Real versioned documents are hard to get.** The build environment could not reach medicaid.gov, so real PDFs came from manual uploads. MITA 2.0 and 3.0 are public; older MECT versions were not available as separate downloads.
24. **Build a small real case plus synthetic cases.** Synthetic cases give clean answer keys. The real case shows whether the approach survives real document length and messy layout.
25. **Market need is still unvalidated.** Code quality does not answer whether anyone would use this. Customer conversations come before more building.

## F. Foundation lessons (Phases 0 to 2)

26. **Plain RAG answered with the old version.** Asked for the prior-authorization threshold, the engine cited version 1 (12 visits) even though version 2 (20 visits) was retrieved. Retrieval finds relevant text; it does not know which version is current. This is the gap the rest of the project fills (version metadata, change detection).
27. **A toy corpus hides problems.** Three short documents became three chunks, so chunking was never exercised, and `top_k=3` on three chunks returns everything, so retrieval quality was not really tested. Real long documents (Phase 7) were needed to find the real limits.
28. **Check numbers written in notebook text.** The notebook said the model download was about 5 GB; it was 15.2 GB (the 5 GB is the 4-bit size in GPU memory).
29. **Keep version information machine-readable.** Version labels that exist only in a free-text title cannot be used for filtering. Explicit metadata (family, version, effective date, current flag) was added in Phase 3.

## G. Moving checkable work from the model to code

30. **Do not ask a language model to do what code can do exactly.** Comparing numbers, dates and counts, and swapping a value in a sentence, is deterministic. The rule-based engine does it identically every run, which removed the false alarm on wording-only changes and the noise between runs.
31. **PDF text is dirty.** Running headers, figure and page numbers, and bullets glued into one long "sentence" create fake changes. Cleaning (drop repeated lines, ignore figure/table/page numbers, skip long passages) mattered more than any model setting.
32. **A caption can hide the change.** In the real MITA pair the old version only had "Figure I-4. The Eight Business Areas" while the new one had a sentence "ten (10) business areas". Sentence matching cannot pair those. Comparing counted things across the whole document found it.
33. **A perfect score on cases you tuned on means little.** 10/10 on the development cases came after tuning on them. Fresh blind cases found a real gap (month names) on the first run; fixing it uses up those cases too. Keep making new ones.
34. **Rules cannot judge meaning.** A new requirement worded differently from the SOP is missed, and one shared common word can cause a wrong match or a lucky right one. This is the narrow place a language model still belongs.

35. **Generate test cases at scale.** A generator with known edits made 1,000 labeled cases in seconds and found bugs 10 hand-written cases never would: paraphrases flagged as changes, distractor SOPs matched by one common word ("waiting", "record"), and two number changes colliding on the same SOP number.
36. **When one shared word decides a match, rank the matches.** Keeping only SOPs whose overlap is at least 60% of the best match removed most distractor flags without losing real ones.
37. **Say what is uncertain instead of guessing.** Same numbers with different words inside a sentence cannot be classified by rules. They are now listed as "needs review", never auto-edited, instead of being treated as changes.

## H. Turning the engine into an agent

38. **A substring check can pass a broken draft.** The removal case "passed" while the draft read "mail a within 10 days", because the test only checked that "mail a paper copy" was gone. Running the real folder workflow exposed it. Fix: exact-text tests on whole drafts (`tests/test_agent.py`), and the removal notice now carries the words the earlier sentence lost.
39. **Test the workflow, not just the engine.** Scanning a real folder found a report that was overwritten on rescan, a misleading "not edited" flag after an earlier edit had already fixed the number, and trailing newlines lost in edits. None showed up in the case scores.
40. **Safety belongs in the design.** The agent writes suggestions to a separate folder, never edits originals, and applying a change needs a named approver, a backup and an audit line. A test checks that a scan leaves every input file byte-for-byte unchanged.
41. **Library versions move.** The MCP package changed its server class name between major versions; the server tries both. Tests run the real server over stdio so a break is caught.

42. **Give the model the narrowest possible job.** The judge answers one yes/no question with a reason and cannot write text. That bounds how much damage a wrong answer can do, and makes its errors countable.
43. **Test the safety rules, not just the happy path.** The tests prove an always-"no" or always-"unsure" judge cannot remove a correct rule-based match, that unreadable output becomes "unsure", and that a call limit and cache hold.
44. **A perfect score with a fake oracle only proves the wiring.** 1000/1000 with an oracle judge says nothing about a real model. The real number comes from `eval/kaggle_run_judge.py`.

45. **Realistic input is a different test.** The same engine scored 98% on tiny cases and 74% on whole manuals. The cause was not the matching rules but sentence splitting: headings and bullets were glued onto the next sentence. Always test on the shape of the real thing.
46. **Matching must scale.** Recomputing word sets for every change and SOP pair timed out at 1,600 SOPs. Precompute an index once per run.
47. **Test in the shape you will deploy.** Putting 200 organisations' SOPs in one folder made identical SOPs from other organisations look like false alarms. Each organisation now has its own workspace, like a real customer.
48. **Headings are not requirements.** Treating "Section 3. Timelines" as sentence text polluted numbers and words. Headings now label a section and are dropped.

## Open problems (as of the latest run)

| Problem | Evidence | Next step |
|---|---|---|
| Removed requirements stay in drafts | policy_05 fails 0/3 | Have the model only name the sentence to delete, and delete it in code; mark for human review if not found verbatim |
| False alarms on wording-only change | control_01 fails 0/3 (whole-document) | Flag an SOP only if the changed terms appear in it |
| Real MITA 8 to 10 change missed in section mode | 68 pairs checked, 4 findings kept, none about 8 to 10 | Read the kept findings (now printed) to see whether the model or my filter is at fault |
| Maturity-scoring SOP wrongly flagged | Both runs on the real case | Same fix as false alarms |

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

## Open problems (as of the latest run)

| Problem | Evidence | Next step |
|---|---|---|
| Removed requirements stay in drafts | policy_05 fails 0/3 | Have the model only name the sentence to delete, and delete it in code; mark for human review if not found verbatim |
| False alarms on wording-only change | control_01 fails 0/3 (whole-document) | Flag an SOP only if the changed terms appear in it |
| Real MITA 8 to 10 change missed in section mode | 68 pairs checked, 4 findings kept, none about 8 to 10 | Read the kept findings (now printed) to see whether the model or my filter is at fault |
| Maturity-scoring SOP wrongly flagged | Both runs on the real case | Same fix as false alarms |

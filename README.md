# Compliance AI Agent

A prototype that helps a compliance analyst identify the impact of a policy update. It compares policy versions, identifies potentially affected internal procedures, drafts proposed updates, and packages the results for human review.

**Status:** Kaggle notebook prototype through Phase 4. The web interface and formal evaluation are planned.

## What it does

1. **Answers policy questions:** Loads sample policy text or public PDFs, retrieves relevant passages, and generates an answer grounded in those passages.
2. **Detects policy changes:** Pairs older and newer versions of a policy and summarizes what changed.
3. **Maps operational impact:** Identifies sample internal standard operating procedures (SOPs) that may be affected.
4. **Drafts procedure updates:** Generates proposed language for affected SOPs, referencing the newer policy and its effective date.
5. **Exports reviewable results:** Returns a structured result from `run_full_compliance_check()` and writes `compliance_results.json` for a future UI.

## Example workflow

**Sample policy change:** Prior authorization for outpatient physical therapy changes from **more than 12 visits** to **more than 20 visits** per calendar year. The advance submission period changes from **5 business days** to **3 business days**.

The prototype compares the two policy versions, summarizes those changes, identifies potentially affected sample SOPs, and drafts proposed procedure text. The output is marked `drafts_ready_for_review`; a compliance analyst must verify it before use.

## How it works

| Component | Implementation |
|---|---|
| Document ingestion | Sample text, with an optional public-PDF loader using `pypdf` |
| Chunking | Word-based chunks with overlap |
| Retrieval | `all-MiniLM-L6-v2` embeddings and a FAISS index |
| Generation | `Qwen2.5-7B-Instruct` loaded in 4-bit quantization |
| Change and impact analysis | Prompts comparing policy versions and sample SOPs |
| Output | Structured Python dictionaries and `compliance_results.json` |

## Run the prototype

1. Import the notebook into **Kaggle**.
2. Enable a GPU accelerator in the notebook settings.
3. Run the cells in order, starting with dependency installation.
4. Start with the included synthetic sample policies and SOPs. Optionally add public policy PDFs through Kaggle’s **Add Data** panel and update the PDF folder path in the notebook.
5. Review the generated report and download `compliance_results.json` from `/kaggle/working/`.

## Data and review boundaries

The included policy examples and internal SOPs are **synthetic**. The optional PDF loader is intended for **public** documents. Do not upload employer documents, confidential procedures, or protected health information.

Generated change summaries, impact mappings, and procedure drafts are proposals. A qualified reviewer must check them against the source policy before making an operational or compliance decision.

## Current limitations and next steps

- The prototype has not been validated against a labeled evaluation set; no accuracy or time-savings claim is made.
- Impact identification and draft quality need systematic testing, including missed changes and incorrect SOP mappings.
- The Phase 5 web interface is planned. The current JSON export provides sample data for building it.
- Future work includes source-level citations, reviewer approval and edit tracking, and tests using real public policy updates.

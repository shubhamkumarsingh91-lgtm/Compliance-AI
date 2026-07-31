# AI-Native Compliance Infrastructure

A RAG-based compliance engine for Medicaid payers and state agencies. It reads policy
documents, detects changes between versions, maps those changes to affected internal
procedures, and drafts the updated procedure language - automatically, with citations
back to the source policy.

Built as a working prototype entirely on free-tier cloud GPU (Kaggle), using only public
CMS/Medicaid policy text and synthetic internal procedures - no proprietary or client data.

---

## The problem

State Medicaid agencies and MCOs currently track regulatory changes manually: someone reads
CMS/state bulletins, cross-references them against internal policy manuals, and updates SOPs
by hand. It's slow, inconsistent, and error-prone - and the compliance stakes (audits,
clawbacks, CMS penalties) are high.

## What this does

1. **Ingests** policy documents (public CMS/Medicaid bulletins, PDF or plain text)
2. **Retrieves** relevant passages for any compliance question (RAG)
3. **Detects changes** between policy versions - old vs. new, side by side
4. **Maps impact** - which internal procedures does this change actually affect, and why
5. **Drafts updates** - rewrites the affected procedure language, with a citation back to
   the source policy and its effective date

Every answer is grounded in retrieved source text, not the model's memory - if the answer
isn't in the provided documents, it says so instead of guessing.

## Demo

Open `compliance_demo.html` directly in a browser - no server or install needed. It renders
the AI's output as a redline diff (old text struck through, new text inserted), the same way
a compliance analyst would review tracked changes in a real document.

## Stack

| Component | Choice | Why |
|---|---|---|
| Generation model | Qwen2.5-7B-Instruct (4-bit quantized) | Strong instruction-following at a size that fits free-tier GPU |
| Embedding model | sentence-transformers `all-MiniLM-L6-v2` | Fast, lightweight, good retrieval quality |
| Vector search | FAISS | Simple, fast similarity search |
| Compute | Kaggle free GPU (T4 x2) | No local hardware, no cost |

## Repo contents

```
compliance_ai_starter.ipynb   - full pipeline: setup, RAG engine, change detection, drafting
compliance_results.json       - sample generated output from a real run
compliance_demo.html          - standalone demo UI (open in any browser)
AI_Native_Compliance_Infrastructure_Overview.pdf  - project/business overview
```

## Running it yourself

1. Upload `compliance_ai_starter.ipynb` to [Kaggle](https://kaggle.com) → **Create → New
   Notebook → File → Import Notebook**
2. **Settings → Accelerator → GPU T4 x2**
3. Run all cells top to bottom
4. Swap the sample policy text for real public CMS/Medicaid documents when ready

## Status

Working prototype. Validated end-to-end on sample Medicaid prior-authorization and telehealth
policy text. Not yet connected to a real client's documents or deployed as a hosted service.

## Roadmap

- [ ] Fix change-attribution parsing (currently string-matches SOP IDs, occasionally
      misflags an unaffected procedure - see commit notes)
- [ ] Expand to real public CMS/state Medicaid document sets
- [ ] Add a persistence layer so results don't need to be regenerated per session
- [ ] Multi-state policy comparison (state-level Medicaid rule variation)

---

*No proprietary, client, or employer data is used anywhere in this repository - only
publicly available policy text and synthetic examples.*

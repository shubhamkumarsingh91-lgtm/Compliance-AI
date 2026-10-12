# Setup Guide — Phase 0 to 2

## 1. Create your accounts (5 minutes)
- **Kaggle**: kaggle.com → sign up (free, no credit card)
- **GitHub**: github.com → sign up, create a **private** repo called `compliance-ai` to store your code
- **Hugging Face**: huggingface.co → sign up (needed to download the open-source model)

## 2. Upload the notebook to Kaggle
1. Go to kaggle.com → **Create** → **New Notebook**
2. Click **File → Import Notebook** → upload `compliance_ai_starter.ipynb`
3. On the right sidebar: **Settings → Accelerator → GPU T4 x2** (this turns on the free GPU)
4. Click **Save Version** occasionally so you don't lose progress — Kaggle sessions reset after 9 hours

## 3. Run it
- Run each cell top to bottom with Shift+Enter
- First run will take a few minutes (downloading the model, ~5GB)
- If you see "No GPU detected" — double check Settings → Accelerator is set to GPU

## 4. What you'll have by the end
A working RAG (retrieval-augmented generation) engine that:
- Reads sample Medicaid policy text (swap in real public CMS/Medicaid PDFs when ready)
- Answers questions grounded in that text, with source citations
- Runs entirely on Kaggle's free GPU — nothing on your own machine

## 5. Weekly GPU budget
Kaggle gives you **30 free GPU hours per week**, resetting weekly. This notebook uses maybe
15–20 minutes per session once the model is cached, so you have plenty of room to iterate.

## 6. When you outgrow the free tier
Once you're ready for a bigger model or a private, dedicated GPU (e.g. once you're handling
anything beyond public sample data), move to **RunPod** (runpod.io) — pay-per-hour, private
instance, no sharing with other users. Roughly $0.20–$0.80/hour depending on GPU size.

## Next session
We'll build **Phase 3 — the change-detection ("diff") layer** on top of this notebook: the
logic that automatically spots when a policy changed and flags what it affects.

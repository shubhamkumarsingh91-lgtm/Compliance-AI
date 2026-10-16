"""The language-model check ("judge").

Rules decide everything that can be checked exactly (numbers, dates, counts, added or removed sentences). Rules cannot
judge MEANING, so the engine asks a judge narrow yes/no questions in three places only:

  1. applies(requirement, sop)       - a new or removed requirement shares no words with an SOP: does it still apply?   (recall)
  2. applies(...) on weak matches    - only one common word linked a change to an SOP: is the link real?                (precision)
  3. same_requirement(old, new)      - same numbers, different words: did the requirement actually change?             (noise)

Design rules:
  * A judge only answers yes / no / unsure and gives a short reason. It never writes SOP text. Edits stay rule-based or
    verbatim from the policy, and are flagged for a person.
  * "unsure" never creates a flag and never removes one: it goes to "needs review".
  * Every call is logged (question, answer, reason, backend) so you can see exactly what the model decided.
  * Answers are cached by question, so the same question always gets the same answer in a run, and costs once.
  * Backends: NoJudge (default, rules only), FakeJudge (tests), HFJudge (a local open model on a GPU, e.g. Qwen),
    ApiJudge (a hosted model through its API). Any model size works; the interface is the same.
"""
import hashlib, json, os, re

QUESTION = {
    "applies": ("A policy now contains this requirement:\n\"{a}\"\n\nAn internal procedure says:\n\"{b}\"\n\n"
                "Does the procedure perform the activity that this requirement regulates, so that the procedure may need "
                "to be updated because of it? Answer yes only if the procedure covers that same activity. Sharing a common "
                "word is not enough. If you cannot tell, answer unsure."),
    "same_requirement": ("Old policy sentence:\n\"{a}\"\n\nNew policy sentence:\n\"{b}\"\n\n"
                         "Do both sentences impose exactly the same requirement (only worded differently)? Answer yes if "
                         "the requirement is the same, no if something is added, removed or different. If you cannot tell, "
                         "answer unsure."),
}
SYSTEM = ("You are a careful compliance analyst. Reply with JSON only, in this form: "
          "{\"answer\": \"yes\" | \"no\" | \"unsure\", \"reason\": \"one short sentence\"}.")


def parse_verdict(raw):
    """Turns model text into (answer, reason). Anything unreadable becomes 'unsure', never a guess."""
    m = re.search(r"\{.*?\}", raw or "", re.S)
    if m:
        try:
            d = json.loads(m.group(0)); a = str(d.get("answer", "")).strip().lower()
            if a in ("yes", "no", "unsure"): return a, str(d.get("reason", ""))[:300]
        except Exception:
            pass
    low = (raw or "").strip().lower()
    for w in ("yes", "no", "unsure"):
        if low.startswith(w): return w, (raw or "")[:300]
    return "unsure", f"unreadable answer: {(raw or '')[:100]!r}"


class Judge:
    name = "base"

    def __init__(self, max_calls=200):
        self.cache, self.log, self.calls, self.max_calls = {}, [], 0, max_calls

    def _ask(self, prompt):                      # backends implement this: prompt text in, model text out
        raise NotImplementedError

    def ask(self, kind, a, b):
        prompt = QUESTION[kind].format(a=a, b=b)
        key = hashlib.sha256((kind + prompt).encode()).hexdigest()[:16]
        if key in self.cache:
            return self.cache[key]
        if self.calls >= self.max_calls:
            return ("unsure", "judge call limit reached")
        self.calls += 1
        answer, reason = parse_verdict(self._ask(prompt))
        self.cache[key] = (answer, reason)
        self.log.append(dict(kind=kind, a=a[:200], b=b[:200], answer=answer, reason=reason, backend=self.name))
        return answer, reason


class NoJudge(Judge):
    name = "none"
    def ask(self, kind, a, b): return ("unsure", "no judge configured")


class FakeJudge(Judge):
    """For tests. `rule(kind, a, b)` returns 'yes'/'no'/'unsure' (or a (answer, reason) pair)."""
    name = "fake"
    def __init__(self, rule, **kw): super().__init__(**kw); self.rule = rule
    def _ask(self, prompt): raise AssertionError("FakeJudge answers in ask()")
    def ask(self, kind, a, b):
        key = (kind, a, b)
        if key in self.cache: return self.cache[key]
        self.calls += 1
        r = self.rule(kind, a, b); r = r if isinstance(r, tuple) else (r, "fake")
        self.cache[key] = r; self.log.append(dict(kind=kind, a=a[:200], b=b[:200], answer=r[0], reason=r[1], backend="fake"))
        return r


class HFJudge(Judge):
    """A local open model through Hugging Face transformers (for a GPU such as the Kaggle T4, or any larger one)."""
    name = "hf"
    def __init__(self, model_name="Qwen/Qwen2.5-7B-Instruct", model=None, tokenizer=None, **kw):
        super().__init__(**kw)
        self.model_name = model_name
        if model is None:                         # reuse an already-loaded model when you have one (as in the notebooks)
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForCausalLM.from_pretrained(
                model_name, device_map="auto",
                quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16))
        self.model, self.tok = model, tokenizer

    def _ask(self, prompt):
        import torch
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
        ids = self.tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(ids, max_new_tokens=80, do_sample=False)   # no sampling: same answer every time
        return self.tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True)


class ApiJudge(Judge):
    """A hosted model through the Anthropic API. Needs `pip install anthropic` and ANTHROPIC_API_KEY. Not run in this repo's tests."""
    name = "api"
    def __init__(self, model="claude-sonnet-5-5", **kw):
        super().__init__(**kw)
        import anthropic
        self.client, self.model = anthropic.Anthropic(), model

    def _ask(self, prompt):
        r = self.client.messages.create(model=self.model, max_tokens=120, temperature=0, system=SYSTEM,
                                        messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")


def make_judge(kind=None, **kw):
    """make_judge('none' | 'hf' | 'api'); default reads COMPLIANCE_JUDGE from the environment."""
    kind = (kind or os.environ.get("COMPLIANCE_JUDGE", "none")).lower()
    return {"none": NoJudge, "hf": HFJudge, "api": ApiJudge}[kind](**kw)

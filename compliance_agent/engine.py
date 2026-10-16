"""Deterministic change engine - no language model, no GPU.

Why it exists: the LLM version kept making errors that a program does not make (false alarms on wording-only
changes, removed requirements left in drafts, different answers on identical input). Facts that can be checked by
code (numbers, dates, added or removed sentences) are handled here by rules that give the SAME answer every time.
A language model is then only needed for optional plain-language explanation, never for deciding what changed.

Limits (be honest): it matches sentences by shared words, so it can miss a change that is reworded heavily, and it can
flag an SOP that shares unusual words with a changed sentence. Every draft is marked for human review.
"""
import re

MONTHS = {"january","february","march","april","june","july","august","september","october","november","december"}  # "may" skipped: also a verb
NUMWORDS = {"zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,
            "eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,"twenty":20,"thirty":30,"sixty":60,"ninety":90}
STOP = set("""a an the and or of to in on for with by from at as is are was were be been being it its this that these those
also must shall will may can should each every all any no not only per than then if when which who whom has have had
their there into within after before over under through provider providers state""".split())
GENERIC_NOT_STOP = set()
REMOVAL_MARKERS = re.compile(r"\b(no longer|is not required|are not required|has been removed|have been removed|"
                             r"eliminated|rescinded|repealed|discontinued|deleted)\b", re.I)
HEADER_LINE = re.compile(r"^(SYNTHETIC EXAMPLE|SOURCE|Sample .*\(v\d+\)|.*\(v\d+\)$)", re.I)


def _stem(w):
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            break
    if w.endswith("e") and len(w) > 3:
        w = w[:-1]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "aeiouls":
        w = w[:-1]
    return w


def _tokens(s):
    return re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?", s)


REFERENCE = re.compile(r"\b(figure|table|page|section|appendix|part|chapter|fm|exhibit)s?\s+[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*", re.I)


def numbers_in(s):
    """Normalized numeric facts: digits as written, number words as digits, ordinals kept (10th).
    Figure, table, page and section numbers are ignored: they are labels, not rules."""
    out = []
    for t in _tokens(REFERENCE.sub(" ", s)):
        tl = t.lower()
        if re.fullmatch(r"\d+(st|nd|rd|th)?", tl):
            out.append(tl)
        elif tl in NUMWORDS:
            out.append(str(NUMWORDS[tl]))
        elif tl in MONTHS:
            out.append(tl)
    return out


def content_stems(s):
    out = set()
    for t in _tokens(s):
        tl = t.lower()
        if tl in STOP or re.fullmatch(r"\d+(st|nd|rd|th)?", tl) or tl in NUMWORDS or tl in MONTHS:
            continue
        out.add(_stem(tl))
    return out


OBLIG = re.compile(r"\b(must|shall|required|will|need to|needs to|are to|is to)\b", re.I)


def clean_lines(text):
    """Drops running headers and footers (a line that repeats 3+ times once digits are masked) and bare codes."""
    lines = [l.strip() for l in text.splitlines() if l.strip() and not HEADER_LINE.match(l.strip())]
    masked = [re.sub(r"\d+", "#", l) for l in lines]
    from collections import Counter
    cnt = Counter(masked)
    return [l for l, m in zip(lines, masked) if cnt[m] < 3 and not re.fullmatch(r"[\d\W]+", l)]


def sentences(text):
    lines = clean_lines(text)
    body = " ".join(lines)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", body)
    return [p.strip() for p in parts if len(p.split()) >= 3]


def _jac(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def diff_policy(old_text, new_text, match_min=0.30):
    """Returns a list of change dicts: kind in value_change | added | removed."""
    olds, news = sentences(old_text), sentences(new_text)
    ostem = [content_stems(s) for s in olds]
    nstem = [content_stems(s) for s in news]
    changes, used_old = [], set()
    NOTICE_WORDS = {"longer", "requir", "remov", "eliminat", "rescind", "repeal", "discontinu", "delet", "not"}
    for j, ns in enumerate(news):
        if REMOVAL_MARKERS.search(ns):
            changes.append(dict(kind="removal_notice", new=ns, stems=nstem[j] - NOTICE_WORDS))
            continue
        best, bi = 0.0, None
        for i, os_ in enumerate(ostem):
            sc = _jac(os_, nstem[j])
            if sc > best: best, bi = sc, i
        if bi is None or best < match_min:
            changes.append(dict(kind="added", new=ns, stems=nstem[j]))
            continue
        used_old.add(bi)
        on, nn = numbers_in(olds[bi]), numbers_in(ns)
        dropped = ostem[bi] - nstem[j]
        gained = nstem[j] - ostem[bi]
        rem = [x for x in on if x not in nn]; add = [x for x in nn if x not in on]
        if rem and add:                       # a number swapped for another; a number that merely vanished is ambiguous
            changes.append(dict(kind="value_change", old=olds[bi], new=ns, old_values=rem, new_values=add,
                                stems=dropped | gained, ctx=ostem[bi] | nstem[j]))
        elif sorted(on) == sorted(nn) and (len(dropped) >= 2 or len(gained) >= 2):
            # Same numbers, different words inside a matched sentence: could be a reworded rule or a real extra clause.
            # Code cannot tell, so it is listed for a person (or a later language-model check), not auto-applied.
            changes.append(dict(kind="uncertain", old=olds[bi], new=ns, stems=dropped | gained))
        # else: wording-only, ignored on purpose
    for i, os_ in enumerate(olds):
        if i in used_old: continue
        if not any(_jac(ostem[i], ns_) >= match_min for ns_ in nstem):
            changes.append(dict(kind="removed", old=os_, new="", stems=ostem[i]))
    # A removal notice ("a paper copy is no longer required") explains a clause dropped from an earlier sentence:
    # give the notice the words that sentence lost, so the whole clause ("mail a paper copy") can be cut from an SOP.
    for rn in [c for c in changes if c["kind"] == "removal_notice"]:
        for u in [c for c in changes if c["kind"] == "uncertain"]:
            if rn["stems"] and rn["stems"] <= content_stems(u["old"]):
                rn["stems"] = rn["stems"] | (content_stems(u["old"]) - content_stems(u["new"]))
                u["consumed"] = True
    changes = [c for c in changes if not c.get("consumed")]
    # Only requirement sentences create SOP work; descriptive prose that appears or disappears is ignored.
    keep = []
    for c in changes:
        if c["kind"] == "uncertain":
            if OBLIG.search(c["new"]): keep.append(c)
            continue
        if c["kind"] in ("added", "added_in_sentence"):
            if not OBLIG.search(c["new"]): continue
        elif c["kind"] == "removed":
            if not OBLIG.search(c.get("old", "")): continue
        keep.append(c)
    return keep + quantity_changes(old_text, new_text)


DISPLAY = {}


def quantity_facts(text):
    """Maps a 'what is being counted' key (the two content words after a number) to the set of numbers seen with it."""
    toks = re.findall(r"[A-Za-z0-9]+", " ".join(clean_lines(text)))
    facts = {}
    i = 0
    while i < len(toks):
        tl = toks[i].lower()
        num = str(NUMWORDS[tl]) if tl in NUMWORDS else (tl if re.fullmatch(r"\d+", tl) else None)
        if num is None:
            i += 1; continue
        j = i + 1
        while j < len(toks) and (toks[j].lower() in NUMWORDS or re.fullmatch(r"\d+", toks[j])):
            j += 1                                              # "ten (10)" counts once
        words, shown = [], []
        while j < len(toks) and len(words) < 2:
            w = toks[j].lower()
            if w in STOP or w in NUMWORDS or w.isdigit(): break
            words.append(_stem(w)); shown.append(w); j += 1
        if len(words) == 2:
            facts.setdefault(tuple(words), set()).add(num); DISPLAY.setdefault(tuple(words), " ".join(shown))
        i = max(j, i + 1)
    return facts


def quantity_changes(old_text, new_text):
    """A counted thing (for example 'business areas') whose numbers in the old and new document do not overlap."""
    fo, fn = quantity_facts(old_text), quantity_facts(new_text)
    out = []
    for key in fo.keys() & fn.keys():
        if fo[key] & fn[key]: continue
        out.append(dict(kind="quantity_change", key=key, old_values=sorted(fo[key]), new_values=sorted(fn[key]),
                        new=f"{DISPLAY.get(key, ' '.join(key))}: {sorted(fo[key])} -> {sorted(fn[key])}", label=DISPLAY.get(key, " ".join(key)), stems=set(key), ctx=set(key)))
    return out


GENERIC_VERBS = {_stem(w) for w in """record log keep send submit check complete maintain ensure provide review update track
notify mail give get make use need follow include prepare""".split()}


def _rare_terms(stems, sops):
    """Terms that appear in fewer than half of the SOPs (so shared common words do not cause false flags)."""
    sop_stems = [content_stems(s["text"]) for s in sops]
    n = len(sops)
    keep = set()
    for t in stems:
        if t in GENERIC_VERBS: continue
        df = sum(1 for ss in sop_stems if t in ss)
        if df and (n == 1 or df <= n / 2):
            keep.add(t)
    return keep


def _near_number(text, old_vals, key):
    """Finds an old number in the SOP within 4 words before the counted thing's words."""
    toks = re.findall(r"[A-Za-z0-9]+", text)
    low = [_stem(t.lower()) for t in toks]
    for i, t in enumerate(toks):
        tl = t.lower()
        v = str(NUMWORDS[tl]) if tl in NUMWORDS else tl
        if v in old_vals and all(k in low[i + 1: i + 5] for k in key):
            return v
    return None


MAX_RULE_WORDS = 45


def is_long_passage(ch):
    if ch["kind"] == "uncertain": return True       # never mapped to SOPs automatically
    """Glued-together bullets and headings (common in PDF text) are too messy to map to an SOP by rule."""
    return ch["kind"] in ("added", "removed", "added_in_sentence", "removal_notice") and \
        len((ch.get("new") or ch.get("old") or "").split()) > MAX_RULE_WORDS


def affected_sops(changes, sops):
    """Maps each change to the SOPs it touches. Returns {sop_id: [(change, reason)]}."""
    out = {}
    for ch in changes:
        if is_long_passage(ch): continue
        if re.match(r"\s*(for example|e\.g\.|for instance)", (ch.get("new") or ch.get("old") or ""), re.I): continue
        term_hits = {}                                   # SOPs matched only by shared words, with how many
        for s in sops:
            toks = set(t.lower() for t in _tokens(s["text"]))
            if ch["kind"] == "quantity_change":
                near = _near_number(s["text"], ch["old_values"], ch["key"])
                if near:
                    out.setdefault(s["id"], []).append((ch, f"states {near} next to '{' '.join(ch['key'])}'"))
            elif ch["kind"] == "value_change":
                has_val = any(v in toks for v in ch["old_values"])
                shared_ctx = ch["ctx"] & content_stems(s["text"] + " " + s.get("title", ""))
                if has_val and shared_ctx:
                    out.setdefault(s["id"], []).append(
                        (ch, f"states old value {ch['old_values']} and shares terms {sorted(shared_ctx)}"))
            else:
                shared = _rare_terms(ch["stems"], sops) & content_stems(s["text"])
                if shared: term_hits[s["id"]] = shared
        if term_hits:                                     # keep the best matches only (at least 60% of the top overlap)
            top = max(len(v) for v in term_hits.values())
            for sid, shared in term_hits.items():
                if len(shared) >= 0.6 * top:
                    out.setdefault(sid, []).append(
                        (ch, f"shares terms {sorted(shared)} with a {ch['kind'].replace('_', ' ')}"))
    # A number in an SOP belongs to the changed sentence it shares the most words with.
    for sid, items in out.items():
        sop_text = next(x["text"] for x in sops if x["id"] == sid)
        best = {}
        for ch, why in items:
            if ch["kind"] != "value_change": continue
            sc = len(ch["ctx"] & content_stems(sop_text))
            for v in ch["old_values"]:
                if sc > best.get(v, (-1, None))[0]: best[v] = (sc, ch)
        out[sid] = [(ch, why) for ch, why in items
                    if ch["kind"] != "value_change" or any(best[v][1] is ch for v in ch["old_values"] if v in best)]
    return {k: v for k, v in out.items() if v}


def _replace_values(text, old_vals, new_vals):
    if len(old_vals) != len(new_vals):
        return text, False
    for o, n in zip(old_vals, new_vals):
        rep = n.capitalize() if o.isalpha() else n
        text2 = re.sub(rf"(?<!\w){re.escape(o)}(?!\w)", rep, text, flags=re.I)
        if text2 == text and o.isdigit():
            pass
        text = text2
    return text, True


def _remove_span(text, stems):
    words = text.split(" ")
    hit = [(i, _stem(re.sub(r"\W", "", w.lower()))) for i, w in enumerate(words)]
    idx = [i for i, st in hit if st in stems]
    if not idx: return text, False
    runs, cur = [], [idx[0]]
    for i in idx[1:]:                                  # words within 3 positions belong to the same phrase
        if i - cur[-1] <= 3: cur.append(i)
        else: runs.append(cur); cur = [i]
    runs.append(cur)
    best = max(runs, key=lambda r: len({dict(hit)[i] for i in r}))
    a, b = best[0], best[-1]
    while a > 0 and re.sub(r"\W", "", words[a - 1].lower()) in ("and", "also", "then", "or"):
        a -= 1
    rest = words[:a] + words[b + 1:]
    if rest and re.sub(r"\W", "", rest[0].lower()) in ("and", "or", "then"):
        rest = rest[1:]
    trailing = text[len(text.rstrip()):]
    out = " ".join(rest).replace(" ,", ",").strip()
    return ((out[:1].upper() + out[1:]) if out else out) + trailing, True


def draft_sop(sop, reasons):
    text, flags = sop["text"], []
    rem_stems = set()
    for ch, _ in reasons:
        if ch["kind"] in ("removed", "removal_notice"):
            rem_stems |= ch["stems"]
    if len(rem_stems & content_stems(text)) >= 2 and len(rem_stems) <= 8:
        t2, ok = _remove_span(text, rem_stems & content_stems(text))
        if ok and t2 != text:
            text = t2; flags.append("VERIFY: a requirement was removed from this SOP because the policy dropped it")
    for ch, _ in reasons:
        if ch["kind"] == "quantity_change":
            toks = re.findall(r"[A-Za-z0-9]+", text)
            near = _near_number(text, ch["old_values"], ch["key"])
            if near is None and _near_number(text, ch["new_values"], ch["key"]):
                continue                                           # an earlier edit already updated it
            if near and len(ch["new_values"]) == 1:
                text = re.sub(rf"(?<!\w){re.escape(near)}(?!\w)", ch["new_values"][0], text, count=1)
                flags.append(f"VERIFY: count changed {ch['old_values']} -> {ch['new_values']} for '{ch['label']}'")
            else:
                flags.append(f"VERIFY: count for '{ch['label']}' changed {ch['old_values']} -> {ch['new_values']}; not edited")
        elif ch["kind"] == "value_change":
            before_t = text
            text, ok = _replace_values(text, ch["old_values"], ch["new_values"])
            if ok and text != before_t: flags.append(f"VERIFY: value changed {ch['old_values']} -> {ch['new_values']}")
            if not ok: flags.append(f"VERIFY: values changed {ch['old_values']} -> {ch['new_values']} but counts differ; not edited")
        elif ch["kind"] in ("added", "added_in_sentence"):
            sentence = ch["new"].rstrip(".") + "."
            if sentence.lower() not in text.lower():
                text = text.rstrip() + " " + sentence
                flags.append(f"NEW CLAUSE copied word for word from the policy, verify it belongs here: {sentence}")
    return text, flags


def run_engine(old_doc, new_doc, sops):
    changes = diff_policy(old_doc["text"], new_doc["text"])
    mapped = affected_sops(changes, sops)
    drafts = []
    for s in sops:
        if s["id"] in mapped:
            t, fl = draft_sop(s, mapped[s["id"]])
            drafts.append(dict(sop_id=s["id"], sop_title=s.get("title", ""), original_text=s["text"], draft_text=t,
                               review_flags=fl, reasons=[w for _, w in mapped[s["id"]]]))
    def line(c):
        if c["kind"] == "value_change":
            return f"[value_change] {', '.join(c['old_values'])} -> {', '.join(c['new_values'])}: {c['new'][:160]}"
        if c["kind"] == "quantity_change":
            return f"[quantity_change] number of {c['label']}: {', '.join(c['old_values'])} -> {', '.join(c['new_values'])}"
        tag = {"uncertain": "reworded_or_clause_changed_check_by_hand"}.get(c["kind"]) or \
              ("long_passage_changed_review_manually" if is_long_passage(c) else c["kind"])
        return f"[{tag}] " + (c.get("new") or c.get("old", ""))[:200]
    summary = "No substantive changes." if not changes else "\n".join(line(c) for c in changes)
    uncertain = [c for c in changes if c["kind"] == "uncertain"]
    return dict(changes_summary=summary, impact_analysis=mapped and {k: [w for _, w in v] for k, v in mapped.items()},
                impact_parse_method="rules", affected_sop_ids=list(mapped), drafted_updates=drafts,
                needs_review=[dict(old=c["old"], new=c["new"]) for c in uncertain])

"""Section-by-section change detection for long documents. No GPU needed for the splitting/matching.

Why: asking a 7B model to compare two 5,000-word documents in one prompt makes it miss small changes.
Instead: split both versions into chunks, pair up matching chunks, drop identical pairs, keep pairs where a
number or an obligation word changed, and ask the model about each small pair separately.

Usage (after your pipeline cells define detect_changes):
    from sectioned import make_sectioned_detector
    detect_changes = make_sectioned_detector(detect_changes)   # run_full_compliance_check now uses it
"""
import re

NUMBER_WORDS = {"one","two","three","four","five","six","seven","eight","nine","ten","eleven","twelve","fifteen",
                "twenty","thirty","forty","sixty","ninety","hundred","first","second","third"}
OBLIGATION = {"must","shall","required","require","requires","within","before","after","no","not","only","may","prohibited"}
STOP = {"the","a","an","of","to","and","or","in","on","for","is","are","be","by","as","at","with"}


def _norm_words(s):
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", s.lower())


def split_chunks(text, max_words=180):
    """Joins broken lines, splits into sentences, groups sentences into ~max_words chunks."""
    text = re.sub(r"\n(?!\n)", " ", text)           # single newlines are layout, not structure
    text = re.sub(r"\s+", " ", text)
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])", text)
    chunks, cur, n = [], [], 0
    for s in sents:
        w = len(s.split())
        if cur and n + w > max_words:
            chunks.append(" ".join(cur)); cur, n = [], 0
        cur.append(s); n += w
    if cur: chunks.append(" ".join(cur))
    return chunks


def _jaccard(a, b):
    a, b = set(_norm_words(a)) - STOP, set(_norm_words(b)) - STOP
    return len(a & b) / len(a | b) if a | b else 0.0


MONTHS = {"january","february","march","april","june","july","august","september","october","november","december"}
_LABEL = re.compile(r"^(v\d+|19\d\d|20\d\d)$")


def _changed_tokens(old, new):
    """Words that differ between two chunks, ignoring version labels (v1, v2), years and month names."""
    o, n = set(_norm_words(old)), set(_norm_words(new))
    return {t for t in (o ^ n) if not _LABEL.match(t) and t not in MONTHS}


def _is_focus(old, new):
    """True if what changed includes a digit, a number word, or an obligation word."""
    return any(t.isdigit() or any(c.isdigit() for c in t) or t in NUMBER_WORDS or t in OBLIGATION
               for t in _changed_tokens(old, new))


def _similarity_matrix(new_chunks, old_chunks):
    """Rows = new chunks, columns = old chunks. TF-IDF cosine (word + 2-word phrases); Jaccard if sklearn is missing."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        v = TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2), stop_words="english").fit(old_chunks + new_chunks)
        return (v.transform(new_chunks) @ v.transform(old_chunks).T).toarray()
    except ImportError:
        return [[_jaccard(o, n) for o in old_chunks] for n in new_chunks]


def candidate_pairs(old_text, new_text, top_k=2, min_sim=0.05, focus=True, max_words=180):
    """Pairs each new chunk with its top_k most similar old chunks (NOT one-to-one: a figure caption in the old
    version may correspond to a sentence in the new one). Drops identical pairs and, if focus=True, pairs whose
    only differences are wording. Chunks with no similar partner become 'added' or 'removed' pairs."""
    old_c, new_c = split_chunks(old_text, max_words), split_chunks(new_text, max_words)
    S = _similarity_matrix(new_c, old_c)
    pairs, seen = [], set()
    for ni, nc in enumerate(new_c):
        order = sorted(range(len(old_c)), key=lambda oi: -S[ni][oi])[:top_k]
        matched = False
        for oi in order:
            if S[ni][oi] < min_sim: continue
            matched = True
            oc = old_c[oi]
            if (oi, ni) in seen or _norm_words(oc) == _norm_words(nc): continue
            if focus and not _is_focus(oc, nc): continue
            seen.add((oi, ni)); pairs.append((oc, nc))
        if not matched and _is_focus("", nc):
            pairs.append(("", nc))                                   # new section
    for oi, oc in enumerate(old_c):
        if max(S[ni][oi] for ni in range(len(new_c))) < min_sim and _is_focus(oc, ""):
            pairs.append((oc, ""))                                   # removed section
    return pairs


NO_CHANGE = re.compile(r"\b(no (substantive|concrete|significant)? ?changes?|nothing (substantive )?changed|no changes)\b", re.I)


def _focus_tokens(old, new):
    """The numbers, number words and obligation words that actually differ between a chunk pair."""
    return {t for t in _changed_tokens(old, new)
            if any(c.isdigit() for c in t) or t in NUMBER_WORDS or t in OBLIGATION}


def _grounded(finding, tokens):
    """A finding only counts if it mentions at least one number/obligation word that really changed in that pair.
    This drops chatter and hallucinated 'changes' from rewording-only pairs."""
    words = set(_norm_words(finding))
    hits = len(words & tokens)
    return hits


def make_sectioned_detector(base_detect, focus=True, verbose=True, max_chars=3500, short_words=1500):
    """Wraps detect_changes(old_doc, new_doc) so it runs per matched chunk and merges the results.

    The merged summary is filtered (must mention a really-changed number/obligation word), de-duplicated and
    capped at max_chars (about 900 tokens). Without the cap, 68 verbose findings produced an 18 GiB
    out-of-memory error in the impact step."""
    def detect(old_doc, new_doc, **kw):
        # Short documents fit in one prompt, so compare them whole. Chunk matching only helps long documents, and on short
        # ones it hid added/removed sentences (no matching chunk, or the grounding filter dropped the finding).
        if len(old_doc["text"].split()) + len(new_doc["text"].split()) <= short_words:
            if verbose: print("  sectioned: short document, comparing whole")
            return base_detect(old_doc, new_doc)
        pairs = candidate_pairs(old_doc["text"], new_doc["text"], focus=focus)
        if verbose: print(f"  sectioned: {len(pairs)} candidate chunk pair(s) to check")
        scored, seen = [], set()
        for oc, nc in pairs:
            o = dict(old_doc, text=oc or "(this section did not exist in the old version)")
            n = dict(new_doc, text=nc or "(this section was removed in the new version)")
            out = (base_detect(o, n) or "").strip()
            if not out or NO_CHANGE.search(out[:120]): continue
            hits = _grounded(out, _focus_tokens(oc, nc))
            key = " ".join(_norm_words(out))[:200]
            if hits == 0 or key in seen: continue
            seen.add(key); scored.append((hits, out))
        scored.sort(key=lambda x: -x[0])                      # most grounded findings first
        merged, size = [], 0
        for hits, out in scored:
            if size + len(out) > max_chars: continue
            merged.append(out); size += len(out)
        if verbose:
            print(f"  sectioned: kept {len(merged)} of {len(pairs)} findings ({size} chars)")
            for m in merged: print("     kept:", m.replace("\n", " ")[:160])
        return "\n".join(merged) if merged else "No substantive changes."
    return detect

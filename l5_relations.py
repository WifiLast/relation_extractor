"""L5: neural ensemble relation extraction (plan.md §33, phase P3 slice).

Two complementary models, both vendored under ``other/`` and installed
editable into the service env:

* ReLiK (``other/relik``) - end-to-end closed relation extraction: finds its
  own entity spans and links them with a fixed NYT relation inventory.
* GLiREL (``other/GLiREL``) - zero-shot relation classification between given
  entity spans, over any label set (the tool caller can pass its own).

GLiREL gets the union of spaCy NER entities, ReLiK's spans, the deterministic
L3 identifiers and (for plain technical prose, where NER finds nothing) noun
chunks. Both outputs are merged into one triple list; a triple found by both
models is marked as agreed. The spaCy/NLTK SVO pass in
``spacy_relation_extract`` stays as the fallback when neither model is
available or they return nothing for a proposition.

Models load lazily (or in the background via ``preload_async``) because the
two DeBERTa-large encoders take a while to come up.
"""
from __future__ import annotations

import os
import re
import threading
import traceback
from dataclasses import dataclass, field

GLIREL_MODEL = os.getenv("GLIREL_MODEL", "jackboyla/glirel-large-v0")
RELIK_MODEL = os.getenv("RELIK_MODEL", "sapienzanlp/relik-relation-extraction-nyt-large")
GLIREL_THRESHOLD = float(os.getenv("GLIREL_THRESHOLD", "0.5"))
# Upper bound on candidate entities per proposition: GLiREL scores every
# ordered pair, so the cost grows quadratically.
MAX_ENTITIES = int(os.getenv("GLIREL_MAX_ENTITIES", "12"))
ENABLED_BACKENDS = {
    b.strip().lower() for b in os.getenv("RE_BACKENDS", "relik,glirel").split(",") if b.strip()
}

NO_RELATION = "no relation"

# Default zero-shot label set: general-purpose plus the plant/automation
# vocabulary this service mostly sees. Constraints only apply when both
# entities carry a spaCy NER type - noun chunks and L3 identifiers are
# untyped for this purpose and pass through.
DEFAULT_LABELS: dict[str, dict[str, list[str]]] = {
    "founded by": {"allowed_head": ["ORG"], "allowed_tail": ["PERSON", "ORG"]},
    "headquartered in": {"allowed_head": ["ORG"], "allowed_tail": ["GPE", "LOC", "FAC"]},
    "located in": {"allowed_tail": ["GPE", "LOC", "FAC", "ORG"]},
    "employed by": {"allowed_head": ["PERSON"], "allowed_tail": ["ORG"]},
    "subsidiary of": {"allowed_head": ["ORG"], "allowed_tail": ["ORG"]},
    "manufactured by": {"allowed_tail": ["ORG", "PERSON"]},
    "part of": {},
    "has part": {},
    "instance of": {},
    "uses": {},
    "controls": {},
    "connected to": {},
    "communicates via": {},
    "has property": {},
    "measures": {},
    "produces": {},
    "born in": {"allowed_head": ["PERSON"], "allowed_tail": ["GPE", "LOC"]},
    "spouse of": {"allowed_head": ["PERSON"], "allowed_tail": ["PERSON"]},
    "child of": {"allowed_head": ["PERSON"], "allowed_tail": ["PERSON"]},
    "date of": {"allowed_tail": ["DATE"]},
    NO_RELATION: {},
}

_NER_TYPES = {
    "PERSON", "NORP", "FAC", "ORG", "GPE", "LOC", "PRODUCT", "EVENT", "WORK_OF_ART",
    "LAW", "LANGUAGE", "DATE", "TIME", "PERCENT", "MONEY", "QUANTITY", "ORDINAL", "CARDINAL",
}
# Numeric-ish NER types rarely head a relation and blow up the pair count;
# L4 handles quantities already.
_SKIP_NER_TYPES = {"CARDINAL", "ORDINAL", "PERCENT", "QUANTITY", "MONEY"}
# Bare noun chunks that are really part of a relation phrase ("is part of",
# "a kind of") rather than an entity.
_RELATIONAL_NOUNS = {"part", "kind", "type", "sort", "lot", "number", "set", "group", "member", "piece"}


@dataclass
class _Entity:
    start: int  # char offsets into the proposition text
    end: int
    text: str
    label: str
    source: str


@dataclass
class Relation:
    subject: str
    relation: str
    object: str
    score: float
    sources: list[str] = field(default_factory=list)
    subject_span: tuple[int, int] = (0, 0)
    object_span: tuple[int, int] = (0, 0)

    def as_dict(self) -> dict:
        return {
            "subject": self.subject,
            "relation": self.relation,
            "object": self.object,
            "score": round(self.score, 4),
            "sources": self.sources,
            "agreed": len(self.sources) > 1,
            "subject_span": list(self.subject_span),
            "object_span": list(self.object_span),
        }


_lock = threading.RLock()
_state: dict = {"nlp": None, "glirel": None, "relik": None, "errors": {}, "loading": False}


def _device() -> str:
    forced = os.getenv("RE_DEVICE")
    if forced:
        return forced
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _load_nlp():
    if _state["nlp"] is None:
        import spacy
        _state["nlp"] = spacy.load(os.getenv("RE_SPACY_MODEL", "en_core_web_sm"))
    return _state["nlp"]


def _load_glirel():
    if _state["glirel"] is None and "glirel" not in _state["errors"]:
        try:
            from glirel import GLiREL
            model = GLiREL.from_pretrained(GLIREL_MODEL)
            model = model.to(_device())
            model.eval()
            _state["glirel"] = model
        except Exception as e:
            _state["errors"]["glirel"] = f"{type(e).__name__}: {e}"
            traceback.print_exc()
    return _state["glirel"]


def _load_relik():
    if _state["relik"] is None and "relik" not in _state["errors"]:
        try:
            from relik import Relik
            from relik.retriever.pytorch_modules.model import GoldenRetriever

            # ReLiK's annotator never passes num_workers, and the retriever
            # defaults to 4 DataLoader worker processes per call - far too
            # heavy for short per-request texts inside a server process.
            if not getattr(GoldenRetriever.retrieve, "_single_process", False):
                _orig_retrieve = GoldenRetriever.retrieve

                def _retrieve(self, *args, **kwargs):
                    kwargs["num_workers"] = 0
                    return _orig_retrieve(self, *args, **kwargs)

                _retrieve._single_process = True
                GoldenRetriever.retrieve = _retrieve

            _state["relik"] = Relik.from_pretrained(RELIK_MODEL, device=_device())
        except Exception as e:
            _state["errors"]["relik"] = f"{type(e).__name__}: {e}"
            traceback.print_exc()
    return _state["relik"]


def load_models() -> dict:
    """Load every enabled backend (idempotent); returns ``status()``."""
    with _lock:
        _state["loading"] = True
        try:
            _load_nlp()
            if "relik" in ENABLED_BACKENDS:
                _load_relik()
            if "glirel" in ENABLED_BACKENDS:
                _load_glirel()
        finally:
            _state["loading"] = False
    return status()


def preload_async() -> threading.Thread:
    t = threading.Thread(target=load_models, name="l5-preload", daemon=True)
    t.start()
    return t


def status() -> dict:
    return {
        "backends": sorted(ENABLED_BACKENDS),
        "relik_loaded": _state["relik"] is not None,
        "glirel_loaded": _state["glirel"] is not None,
        "loading": _state["loading"],
        "errors": dict(_state["errors"]),
        "relik_model": RELIK_MODEL,
        "glirel_model": GLIREL_MODEL,
        "device": _device(),
    }


def available() -> bool:
    return _state["relik"] is not None or _state["glirel"] is not None


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _add_entity(entities: list[_Entity], cand: _Entity) -> None:
    """Keep the first-added (higher-priority) span on overlap."""
    if cand.end <= cand.start or not cand.text.strip():
        return
    for e in entities:
        if cand.start < e.end and e.start < cand.end:
            return
    entities.append(cand)


def _candidate_entities(doc, relik_spans, l3_entities) -> list[_Entity]:
    entities: list[_Entity] = []
    for ent in doc.ents:
        if ent.label_ in _SKIP_NER_TYPES:
            continue
        _add_entity(entities, _Entity(ent.start_char, ent.end_char, ent.text, ent.label_, "spacy"))
    for s in relik_spans:
        _add_entity(entities, _Entity(s.start, s.end, s.text, "ENTITY", "relik"))
    for e in l3_entities or []:
        _add_entity(entities, _Entity(e.start, e.end, e.text, e.label, "l3"))
    for chunk in doc.noun_chunks:
        # Drop leading determiners/possessives so "the pump" and "pump" match
        # across sources; skip bare pronouns.
        toks = [t for t in chunk if not (t.i == chunk.start and t.pos_ in {"DET", "PRON"} and len(chunk) > 1)]
        if not toks or (len(toks) == 1 and (toks[0].pos_ == "PRON" or toks[0].lemma_.lower() in _RELATIONAL_NOUNS)):
            continue
        start, end = toks[0].idx, toks[-1].idx + len(toks[-1].text)
        _add_entity(entities, _Entity(start, end, doc.text[start:end], "NOUN_CHUNK", "noun_chunk"))
        if len(entities) >= MAX_ENTITIES:
            break
    entities.sort(key=lambda e: e.start)
    return entities[:MAX_ENTITIES]


def _type_ok(label_spec: dict, head: str, tail: str) -> bool:
    allowed_head = label_spec.get("allowed_head")
    allowed_tail = label_spec.get("allowed_tail")
    if allowed_head and head in _NER_TYPES and head not in allowed_head:
        return False
    if allowed_tail and tail in _NER_TYPES and tail not in allowed_tail:
        return False
    return True


_label_lemmas: dict[str, str] = {}


def _label_lemma(label: str) -> str:
    if label not in _label_lemmas:
        _label_lemmas[label] = _load_nlp()(label.split()[0])[0].lemma_.lower()
    return _label_lemmas[label]


def _orient(label: str, first: _Entity, second: _Entity, sent) -> tuple[_Entity, _Entity]:
    """Pick head/tail for a GLiREL pair from syntax.

    GLiREL scores both directions of a pair almost identically, so its own
    direction is noise. The labels read head-first ("X controls Y", "X part
    of Y", "X founded by Y"), so textual order is right by default. Voice only
    matters when the label's verb is the sentence's verb: "the pump is
    controlled by the PLC" flips "controls", and "Jobs founded Apple" flips
    the already-passive "founded by".
    """
    if label.endswith((" of", " in", " via", " to", " with", " from")):
        return first, second
    lemma = _label_lemma(label)
    verb = next((t for t in sent if t.pos_ in ("VERB", "AUX") and t.lemma_.lower() == lemma), None)
    if verb is None:
        return first, second
    passive_verb = any(c.dep_ in ("auxpass", "nsubjpass") for c in verb.children)
    return (second, first) if passive_verb != label.endswith(" by") else (first, second)


def _glirel_relations(doc, entities, labels: dict, threshold: float) -> list[Relation]:
    """GLiREL over each sentence separately - a proposition can hold several
    sentences, and cross-sentence pairs are almost all noise for GLiREL."""
    model = _state["glirel"]
    if model is None or len(entities) < 2:
        return []
    batch_tokens, batch_ner, batch_maps = [], [], []
    for sent in doc.sents:
        ner, by_tok = [], {}
        for e in entities:
            span = doc.char_span(e.start, e.end, alignment_mode="expand")
            if span is None or len(span) == 0 or span.start < sent.start or span.end > sent.end:
                continue
            key = (span.start - sent.start, span.end - sent.start)
            if key in by_tok:
                continue
            by_tok[key] = e
            ner.append([key[0], key[1] - 1, e.label, e.text])  # GLiREL: inclusive end
        if len(ner) < 2:
            continue
        ner.sort(key=lambda x: x[0])
        batch_tokens.append([t.text for t in sent])
        batch_ner.append(ner)
        batch_maps.append((by_tok, sent))
    if not batch_tokens:
        return []
    raw_batch = model.batch_predict_relations(
        batch_tokens, list(labels), threshold=threshold, ner=batch_ner, top_k=1,
    )

    best: dict[tuple, Relation] = {}
    for raw, (by_tok, sent) in zip(raw_batch, batch_maps):
        for r in raw:
            label = r["label"]
            if label == NO_RELATION:
                continue
            head = by_tok.get(tuple(r["head_pos"]))
            tail = by_tok.get(tuple(r["tail_pos"]))
            if head is None or tail is None or head is tail:
                continue
            if not _type_ok(labels.get(label, {}), head.label, tail.label):
                continue
            key = (frozenset((head.start, tail.start)), label)
            score = float(r["score"])
            if key in best and best[key].score >= score:
                continue
            head, tail = _orient(label, *sorted((head, tail), key=lambda e: e.start), sent)
            best[key] = Relation(
                head.text, label, tail.text, score, ["glirel"],
                (head.start, head.end), (tail.start, tail.end),
            )
    return list(best.values())


def _relik_relations(out) -> list[Relation]:
    rels = []
    for t in getattr(out, "triplets", None) or []:
        rels.append(Relation(
            t.subject.text, t.label, t.object.text, float(getattr(t, "confidence", 1.0) or 1.0),
            ["relik"], (t.subject.start, t.subject.end), (t.object.start, t.object.end),
        ))
    return rels


def _merge(relik: list[Relation], glirel: list[Relation]) -> list[Relation]:
    merged: dict[tuple, Relation] = {}
    for r in relik + glirel:
        key = (_norm(r.subject), _norm(r.relation), _norm(r.object))
        if key in merged:
            m = merged[key]
            m.sources = sorted(set(m.sources) | set(r.sources))
            m.score = max(m.score, r.score)
        else:
            merged[key] = r
    # Entity pair agreement across differently named relations: surface it
    # without collapsing the labels (ReLiK's NYT inventory and the zero-shot
    # labels rarely share a name).
    pairs: dict[frozenset, set] = {}
    for r in merged.values():
        pairs.setdefault(frozenset((_norm(r.subject), _norm(r.object))), set()).update(r.sources)
    for r in merged.values():
        srcs = pairs[frozenset((_norm(r.subject), _norm(r.object)))]
        if len(srcs) > 1 and len(r.sources) == 1:
            r.sources = r.sources + [f"pair:{s}" for s in sorted(srcs - set(r.sources))]
    return sorted(merged.values(), key=lambda r: (min(r.subject_span[0], r.object_span[0]), -r.score))


def extract(
    texts: list[str],
    l3_entities: list[list] | None = None,
    labels: list[str] | dict | None = None,
    threshold: float | None = None,
) -> list[list[Relation]] | None:
    """Relations for each text, or ``None`` when no neural backend loaded.

    :param l3_entities: per-text L3 ``EntitySpan`` lists, used as extra
        GLiREL candidates (identifiers like article numbers).
    :param labels: zero-shot GLiREL labels (list, or ``{label: constraints}``);
        defaults to ``DEFAULT_LABELS``. ReLiK's inventory is fixed.
    """
    load_models()
    if not available():
        return None
    if labels is None:
        label_spec = DEFAULT_LABELS
    elif isinstance(labels, dict):
        label_spec = dict(labels)
    else:
        label_spec = {str(l): {} for l in labels}
    label_spec.setdefault(NO_RELATION, {})
    thr = GLIREL_THRESHOLD if threshold is None else threshold
    l3_entities = l3_entities or [[] for _ in texts]

    with _lock:
        nlp = _load_nlp()
        relik_outs = [None] * len(texts)
        if _state["relik"] is not None and texts:
            try:
                outs = _state["relik"](list(texts))
                relik_outs = outs if isinstance(outs, list) else [outs]
            except Exception:
                traceback.print_exc()

        results = []
        for text, out, l3 in zip(texts, relik_outs, l3_entities):
            doc = nlp(text)
            relik_rels = _relik_relations(out) if out is not None else []
            relik_spans = list(getattr(out, "spans", None) or []) if out is not None else []
            try:
                glirel_rels = _glirel_relations(doc, _candidate_entities(doc, relik_spans, l3), label_spec, thr)
            except Exception:
                traceback.print_exc()
                glirel_rels = []
            results.append(_merge(relik_rels, glirel_rels))
    return results

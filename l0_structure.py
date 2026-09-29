"""L0: structure normalization of LLM/Markdown output (plan.md §20, phase P2).

markdown-it-py supplies block-level segmentation (headings, paragraphs, list
nesting, code fences) via line-range tokens; its core has no GFM table rule
(that needs the `mdit_py_plugins` extra, not a project dependency), so tables
are detected with a small manual line-based parser instead. Everything else
works off raw-text slices addressed by that block segmentation, so exact
character offsets into the original text are preserved throughout (the
prerequisite for span replacement, plan.md §7).

Simplifications versus the full §20 spec: heading context is "most recent
heading text" (no per-level stack - fine as a fallback subject, real linking
is L7); list-context inheritance is heuristic string concatenation, not NLG.
Covers the common LLM-output patterns (§30 categories 15, 16, 35, 37, 38),
not every Markdown corner case.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from markdown_it import MarkdownIt

_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_PAREN_RE = re.compile(r"\(([^()]+)\)")
_TABLE_ROW_RE = re.compile(r"^[ \t]*\|(.+)\|[ \t]*$")
_TABLE_SEP_RE = re.compile(r"^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(\|[ \t]*:?-{2,}:?[ \t]*)+\|?[ \t]*$")
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")

_md = MarkdownIt("commonmark")


@dataclass
class Fact:
    """A directly-derived (subject, predicate, value) triple that bypasses
    NLP entirely - currently only tables produce these (§20: "the most
    precise fact source in LLM output")."""
    subject: str
    predicate: str
    value: str
    source: str
    span: tuple[int, int]


@dataclass
class Proposition:
    text: str
    span: tuple[int, int]
    context_entity: Optional[str] = None
    kind: str = "text"  # "text" | "list_item" | "parenthetical"
    parent_index: Optional[int] = None


@dataclass
class NormalizedDocument:
    propositions: list[Proposition] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    code_blocks: list[tuple[str, tuple[int, int]]] = field(default_factory=list)
    placeholders: dict[str, str] = field(default_factory=dict)


def _line_offsets(text: str) -> list[int]:
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def _split_tables(lines: list[str], line_starts: list[int]) -> tuple[list[Fact], set[int]]:
    """GFM-style table -> Facts: first column is the entity, header row gives
    the predicates, each remaining cell is a value (§20)."""
    facts: list[Fact] = []
    consumed: set[int] = set()
    i = 0
    while i < len(lines) - 1:
        header_m = _TABLE_ROW_RE.match(lines[i])
        sep_m = _TABLE_SEP_RE.match(lines[i + 1]) if header_m else None
        if not (header_m and sep_m):
            i += 1
            continue
        headers = [c.strip() for c in header_m.group(1).split("|")]
        row_i = i + 2
        table_lines = {i, i + 1}
        while row_i < len(lines):
            row_m = _TABLE_ROW_RE.match(lines[row_i])
            if not row_m:
                break
            cells = [c.strip() for c in row_m.group(1).split("|")]
            table_lines.add(row_i)
            if cells and cells[0]:
                entity = cells[0]
                for col, value in enumerate(cells[1:], start=1):
                    if col < len(headers) and value:
                        facts.append(Fact(
                            subject=entity,
                            predicate=headers[col],
                            value=value,
                            source="table",
                            span=(line_starts[row_i], line_starts[row_i] + len(lines[row_i])),
                        ))
            row_i += 1
        consumed |= table_lines
        i = row_i
    return facts, consumed


def _mask_inline_code(text: str, placeholders: dict[str, str]) -> str:
    """Inline code -> a ⟨ID_nn⟩ placeholder, original text kept in
    `placeholders`, so a downstream tokenizer never splits on `.`/`_` inside
    identifiers like GVL.xStart (§20)."""
    def _sub(m: re.Match) -> str:
        idx = len(placeholders)
        token = f"⟨ID_{idx:02d}⟩"
        placeholders[token] = m.group(1)
        return token
    return _INLINE_CODE_RE.sub(_sub, text)


def _split_parentheses(prop_text: str, base_offset: int, parent_index: int) -> list[Proposition]:
    """(default: 500 ms) / (e.g. Modbus) become their own proposition,
    pointing back at the parent sentence (§20)."""
    return [
        Proposition(
            text=m.group(1).strip(),
            span=(base_offset + m.start(1), base_offset + m.end(1)),
            kind="parenthetical",
            parent_index=parent_index,
        )
        for m in _PAREN_RE.finditer(prop_text)
    ]


def normalize(text: str) -> NormalizedDocument:
    doc = NormalizedDocument()
    lines = text.splitlines()
    line_starts = _line_offsets(text)

    table_facts, table_lines = _split_tables(lines, line_starts)
    doc.facts.extend(table_facts)

    tokens = _md.parse(text)

    heading_context: Optional[str] = None
    list_context_stack: list[Optional[str]] = []
    pending_intro: Optional[str] = None

    def _block_span(tok) -> tuple[str, int]:
        start_line, end_line = tok.map
        if any(l in table_lines for l in range(start_line, end_line)):
            return "", -1
        raw = "\n".join(lines[start_line:end_line]).strip()
        return raw, line_starts[start_line]

    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]

        if tok.type == "heading_open":
            inline = tokens[idx + 1]
            heading_context = inline.content.strip()
            idx += 3
            continue

        if tok.type in ("fence", "code_block"):
            start_line, end_line = tok.map
            end_line = min(end_line, len(lines))
            span = (line_starts[start_line], line_starts[end_line])
            doc.code_blocks.append((tok.content, span))
            idx += 1
            continue

        if tok.type in ("bullet_list_open", "ordered_list_open"):
            context = list_context_stack[-1] if list_context_stack else pending_intro
            list_context_stack.append(context)
            pending_intro = None
            idx += 1
            continue

        if tok.type in ("bullet_list_close", "ordered_list_close"):
            if list_context_stack:
                list_context_stack.pop()
            idx += 1
            continue

        if tok.type in ("list_item_open", "list_item_close"):
            idx += 1
            continue

        if tok.type == "paragraph_open":
            raw, base_offset = _block_span(tok)
            if base_offset < 0:
                idx += 3
                continue

            if list_context_stack:
                marker_m = _LIST_MARKER_RE.match(raw)
                if marker_m:
                    base_offset += marker_m.end()
                    raw = raw[marker_m.end():]

            masked = _mask_inline_code(raw, doc.placeholders)

            if list_context_stack:
                context = list_context_stack[-1]
                item_text = masked.rstrip(".")
                if context:
                    ctx = context.rstrip(":").rstrip(".")
                    sentence = f"{ctx} {item_text}".strip()
                else:
                    sentence = item_text
                if not sentence.endswith((".", "!", "?")):
                    sentence += "."
                prop = Proposition(sentence, (base_offset, base_offset + len(raw)),
                                    context_entity=heading_context, kind="list_item")
            else:
                pending_intro = masked
                prop = Proposition(masked, (base_offset, base_offset + len(raw)),
                                    context_entity=heading_context, kind="text")

            doc.propositions.append(prop)
            parent_idx = len(doc.propositions) - 1
            doc.propositions.extend(_split_parentheses(masked, base_offset, parent_idx))
            idx += 3
            continue

        idx += 1

    return doc

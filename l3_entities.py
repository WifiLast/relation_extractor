"""L3: deterministic entity/identifier layer (plan.md §23, phase P2).

Regex/EntityRuler only for now - GLiNER zero-shot NER is deferred (it needs a
new ML dependency plus the ontology classes wired up as prompt labels, out of
scope for this P1+P2 slice). §23's conflict rule ("the regex span wins over
the GLiNER span, and the longest span wins among equal sources") is
implemented as pure longest-span-wins for now, since regex is the only source
until GLiNER is added.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ontology import resolve_attribute


@dataclass
class EntitySpan:
    text: str
    label: str
    start: int
    end: int
    source: str = "regex"


_PROTOCOLS = (
    "PROFINET", "EtherCAT", "OPC UA", "Modbus TCP", "Modbus RTU", "Modbus",
    "CANopen", "PROFIBUS", "MQTT", "BACnet", "IO-Link",
)

_IEC_TYPES = (
    "BOOL", "BYTE", "WORD", "DWORD", "LWORD", "SINT", "INT", "DINT", "LINT",
    "USINT", "UINT", "UDINT", "ULINT", "REAL", "LREAL", "TIME", "STRING", "WSTRING",
)

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ipv4", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
    ("ipv6", re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b")),
    ("mac_address", re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")),
    ("article_number", re.compile(r"\b\d{3}-\d{4}\b")),
    # each dotted segment needs >=2 chars, so "e.g"/"i.e" (single-letter
    # segments) don't get misread as a variable path like GVL.xStart
    ("variable_path", re.compile(r"\b[A-Za-z_][A-Za-z0-9_]+(?:\.[A-Za-z_][A-Za-z0-9_]+)+\b")),
    ("version", re.compile(r"\bv?\d+\.\d+(?:\.\d+){0,2}\b")),
    ("iec_type", re.compile(r"\b(?:" + "|".join(_IEC_TYPES) + r")\b")),
    ("protocol", re.compile(r"\b(?:" + "|".join(re.escape(p) for p in _PROTOCOLS) + r")\b", re.IGNORECASE)),
]


def find_entities(text: str) -> list[EntitySpan]:
    """One deterministic regex pass per category, then resolve overlaps by
    longest-span-wins (§23's conflict rule)."""
    candidates: list[EntitySpan] = []
    for label, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            candidates.append(EntitySpan(m.group(0), label, m.start(), m.end()))

    candidates.sort(key=lambda e: (e.start, -(e.end - e.start)))
    kept: list[EntitySpan] = []
    for cand in candidates:
        if not kept or cand.start >= kept[-1].end:
            kept.append(cand)
        elif (cand.end - cand.start) > (kept[-1].end - kept[-1].start):
            kept[-1] = cand
    return kept


_COMPOUND_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9_-]*)(?:'s)?\b((?:\s+[a-zà-öø-ÿ]+){1,2})"
)


def resolve_compound_attributes(text: str) -> list[tuple[str, str]]:
    """§23 compound resolution: "PFC200 supply voltage" / possessive
    "PFC200's supply voltage" -> [("PFC200", "has_supply_voltage")]. Checks
    the last word of a one/two-word lowercase tail following a capitalized
    token against the ontology's attribute lexicon (EN/DE)."""
    out = []
    for m in _COMPOUND_RE.finditer(text):
        entity = m.group(1)
        tail_words = m.group(2).split()
        predicate = resolve_attribute(tail_words[-1])
        if predicate:
            out.append((entity, predicate))
    return out

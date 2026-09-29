"""L4: quantities, units, intervals (plan.md §24, phase P2).

Every quantity becomes an interval [lo, hi] with an SI unit - the shape that
maps directly onto a Z3 `lo <= x, x <= hi` pair. Implemented as a regex
cascade (the plan's explicit alternative to a `lark` grammar) plus a small
manual SI conversion table instead of `pint`: `pint` isn't installed in this
project yet, and the unit set actually needed here (V, A, W, Hz, s, degC,
bar, %, l/min, kWh...) is small enough to hardcode. Swap in `pint` later if
the unit set grows past what's worth hand-maintaining.

Relative comparisons ("20% higher than B") and percentage-point deltas are
tagged as their own quantity but not resolved to a concrete interval here -
resolving them needs the *other* operand, which is an L6 concern (§26
comparison encoding), out of scope for this P1+P2 slice.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

APPROX_TOLERANCE = 0.1  # the "valve" §24 mentions for approximations

# (exact literal as written, SI unit, multiplier to SI). Deliberately
# case-sensitive and narrower than "any case variant" of each unit - SI
# symbols are case-sensitive by convention anyway (V != v, mV != MV), and
# staying strict avoids collisions like "USB" containing "us" (microseconds)
# or a bare lowercase "a"/"h" colliding with the English article/pronoun.
_UNIT_FORMS: list[tuple[str, str, float]] = [
    ("mV", "V", 1e-3), ("kV", "V", 1e3), ("V", "V", 1.0),
    ("mA", "A", 1e-3), ("µA", "A", 1e-6), ("uA", "A", 1e-6), ("A", "A", 1.0),
    ("kW", "W", 1e3), ("mW", "W", 1e-3), ("W", "W", 1.0),
    ("kHz", "Hz", 1e3), ("MHz", "Hz", 1e6), ("Hz", "Hz", 1.0),
    ("ms", "s", 1e-3), ("µs", "s", 1e-6), ("us", "s", 1e-6),
    ("min", "s", 60.0), ("h", "s", 3600.0), ("s", "s", 1.0),
    ("°C", "degC", 1.0), ("degC", "degC", 1.0),
    ("mbar", "bar", 1e-3), ("bar", "bar", 1.0),
    ("%", "%", 1.0),
    ("l/min", "l/min", 1.0), ("kWh", "kWh", 1.0),
]
_UNIT_LOOKUP: dict[str, tuple[str, float]] = {form: (si, factor) for form, si, factor in _UNIT_FORMS}

_NUM = r"[-+]?\d[\d.,]*"
# Only ever matches a *known* unit token (longest-first, so "mV" doesn't lose
# to "V"), never an arbitrary trailing word - otherwise "2 Ethernet ports"
# would regex-match "ports" as if it were a physical unit. The trailing
# (?![A-Za-z]) guards the other direction: without it, single-letter units
# like "h"/"s"/"A" match as a bare prefix of the *next* word ("has 8 inputs"
# -> "h" read as hours, "PFC200 supports" -> "s" read as seconds).
_UNIT_ALT = "|".join(re.escape(form) for form, _, _ in sorted(_UNIT_FORMS, key=lambda t: -len(t[0])))
_UNIT_TOKEN = rf"(?:{_UNIT_ALT})(?![A-Za-z])"
_UNIT = rf"(?:{_UNIT_TOKEN})?"
_UNIT_REQUIRED = _UNIT_TOKEN


@dataclass
class QuantityMatch:
    text: str
    start: int
    end: int
    lo: float
    hi: float
    unit: Optional[str]
    form: str  # "point" | "range" | "tolerance" | "bound_max" | "bound_min" | "approx"
    confidence: float = 1.0
    ambiguous: bool = False


def _to_float(raw: str, locale: str) -> float:
    """§24 number-format normalization: '1.000'/'1,000' mean different things
    in de vs en. `locale="unknown"` leaves the raw separators as-is (English
    convention) and the caller is expected to check `ambiguous`."""
    raw = raw.strip()
    if locale == "de":
        return float(raw.replace(".", "").replace(",", "."))
    return float(raw.replace(",", ""))


def _unit_lookup(raw_unit: str) -> tuple[Optional[str], float]:
    """`raw_unit` only ever comes from a regex group built out of `_UNIT`/
    `_UNIT_REQUIRED`, so it's either empty or an exact, case-sensitive known
    unit literal - never arbitrary trailing text."""
    raw_unit = raw_unit.strip()
    if not raw_unit:
        return None, 1.0
    return _UNIT_LOOKUP.get(raw_unit, (None, 1.0))


# Cue words are wrapped in scoped case-insensitive groups (?i:...) so "Max."/
# "MAX" still match, while the unit-token group stays case-sensitive (the
# collision guard above only works if the outer pattern isn't re.IGNORECASE).
_TOLERANCE_RE = re.compile(rf"({_NUM})\s*({_UNIT})\s*(?:±|\+/-|(?i:plus/minus))\s*({_NUM})\s*%")
_RANGE_RE = re.compile(rf"({_NUM})\s*(?:–|-|(?i:to|and|bis))\s*({_NUM})\s*({_UNIT})")
_BOUND_MAX_RE = re.compile(rf"(?:(?i:max\.?|maximum|up to|höchstens)|≤|<=)\s*({_NUM})\s*({_UNIT})")
_BOUND_MIN_RE = re.compile(rf"(?:(?i:min\.?|minimum|at least|mindestens)|≥|>=)\s*({_NUM})\s*({_UNIT})")
_APPROX_RE = re.compile(rf"(?:(?i:about|approx\.?|ca\.?|ungefähr)|~)\s*({_NUM})\s*({_UNIT})")
_POINT_RE = re.compile(rf"({_NUM})\s*({_UNIT_REQUIRED})")


def find_quantities(text: str, locale: str = "en") -> list[QuantityMatch]:
    """Runs the more specific forms first (tolerance/range/bound/approx) and
    marks their character spans consumed, then a bare point-value pass fills
    in whatever's left - so '24 V ±10 %' becomes one tolerance match, not a
    tolerance plus a stray '24 V' point match."""
    matches: list[QuantityMatch] = []
    consumed = bytearray(len(text))

    def _free(start: int, end: int) -> bool:
        return not any(consumed[start:end])

    def _mark(start: int, end: int) -> None:
        for i in range(start, end):
            consumed[i] = 1

    for m in _TOLERANCE_RE.finditer(text):
        if not _free(m.start(), m.end()):
            continue
        center = _to_float(m.group(1), locale)
        unit, factor = _unit_lookup(m.group(2))
        pct = _to_float(m.group(3), locale) / 100.0
        lo, hi = center * (1 - pct) * factor, center * (1 + pct) * factor
        matches.append(QuantityMatch(m.group(0), m.start(), m.end(), min(lo, hi), max(lo, hi), unit, "tolerance"))
        _mark(m.start(), m.end())

    for m in _RANGE_RE.finditer(text):
        if not _free(m.start(), m.end()):
            continue
        lo_raw, hi_raw = _to_float(m.group(1), locale), _to_float(m.group(2), locale)
        unit, factor = _unit_lookup(m.group(3))
        lo, hi = sorted((lo_raw * factor, hi_raw * factor))
        matches.append(QuantityMatch(m.group(0), m.start(), m.end(), lo, hi, unit, "range"))
        _mark(m.start(), m.end())

    for m in _BOUND_MAX_RE.finditer(text):
        if not _free(m.start(), m.end()):
            continue
        val = _to_float(m.group(1), locale)
        unit, factor = _unit_lookup(m.group(2))
        matches.append(QuantityMatch(m.group(0), m.start(), m.end(), float("-inf"), val * factor, unit, "bound_max"))
        _mark(m.start(), m.end())

    for m in _BOUND_MIN_RE.finditer(text):
        if not _free(m.start(), m.end()):
            continue
        val = _to_float(m.group(1), locale)
        unit, factor = _unit_lookup(m.group(2))
        matches.append(QuantityMatch(m.group(0), m.start(), m.end(), val * factor, float("inf"), unit, "bound_min"))
        _mark(m.start(), m.end())

    for m in _APPROX_RE.finditer(text):
        if not _free(m.start(), m.end()):
            continue
        val = _to_float(m.group(1), locale)
        unit, factor = _unit_lookup(m.group(2))
        lo, hi = val * (1 - APPROX_TOLERANCE) * factor, val * (1 + APPROX_TOLERANCE) * factor
        matches.append(QuantityMatch(m.group(0), m.start(), m.end(), lo, hi, unit, "approx", confidence=0.7))
        _mark(m.start(), m.end())

    for m in _POINT_RE.finditer(text):
        if not _free(m.start(), m.end()):
            continue
        unit, factor = _unit_lookup(m.group(2))
        if unit is None:
            continue  # a bare number with no unit isn't a quantity here
        raw_num = m.group(1)
        ambiguous = locale == "unknown" and ("." in raw_num or "," in raw_num)
        val = _to_float(raw_num, "en" if locale == "unknown" else locale) * factor
        matches.append(QuantityMatch(
            m.group(0), m.start(), m.end(), val, val, unit, "point",
            confidence=0.5 if ambiguous else 1.0, ambiguous=ambiguous,
        ))
        _mark(m.start(), m.end())

    matches.sort(key=lambda q: q.start)
    return matches

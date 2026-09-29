"""Ontology v1 for the relation-extraction pipeline (plan.md §5/§23, phase P1
in §33: "classes, predicates, types, bounds").

Classes double as the label set L3's entity layer uses (and, later, GLiNER's
zero-shot labels, §23). Predicates carry domain/range typing and physical
bounds for L8 validation (a later phase - the fields already exist so L8
doesn't need a schema migration when it lands). The attribute lexicon is
shared by L1 bridging's domain lookup (§21) and L3's compound resolution
("PFC200 supply voltage" -> has_supply_voltage(PFC200), §23).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

CLASSES: tuple[str, ...] = (
    "device", "module", "software", "protocol", "signal",
    "parameter", "firmware", "component", "location",
)


@dataclass(frozen=True)
class Predicate:
    name: str
    domain: tuple[str, ...]
    range: str  # an entity class name, or a value type: "quantity" | "text" | "int" | "bool"
    unit: Optional[str] = None
    bounds: Optional[tuple[float, float]] = None
    inverse_of: Optional[str] = None


PREDICATES: dict[str, Predicate] = {
    p.name: p
    for p in (
        Predicate("has_supply_voltage", ("device", "module"), "quantity", unit="V", bounds=(0.0, 1000.0)),
        Predicate("has_current", ("device", "module", "signal"), "quantity", unit="A", bounds=(0.0, 1000.0)),
        Predicate("has_temperature", ("device", "module"), "quantity", unit="degC", bounds=(-273.15, 1000.0)),
        Predicate("has_frequency", ("device", "module", "signal"), "quantity", unit="Hz", bounds=(0.0, 1e9)),
        Predicate("has_count", ("device", "module", "component"), "int", bounds=(0.0, 100000.0)),
        Predicate("runs", ("device",), "software"),
        Predicate("supports", ("device", "module", "software"), "protocol"),
        Predicate("located_in", ("device", "module", "component"), "location"),
        Predicate("part_of", ("component", "module"), "device", inverse_of="contains"),
        Predicate("contains", ("device", "module"), "component", inverse_of="part_of"),
        Predicate("type", CLASSES, "text"),
        Predicate("alias", CLASSES, "text"),
        Predicate("has_firmware_version", ("device", "module"), "text"),
    )
}

# compound head noun (EN/DE) -> canonical predicate name
ATTRIBUTE_LEXICON: dict[str, str] = {
    "voltage": "has_supply_voltage",
    "spannung": "has_supply_voltage",
    "versorgungsspannung": "has_supply_voltage",
    "current": "has_current",
    "strom": "has_current",
    "temperature": "has_temperature",
    "temperatur": "has_temperature",
    "frequency": "has_frequency",
    "frequenz": "has_frequency",
    "firmware": "has_firmware_version",
}


def predicate_domain_classes(predicate: str) -> tuple[str, ...]:
    """Entity classes `predicate`'s subject may belong to - §21 bridging uses
    this to pick the most recently mentioned entity of a matching class."""
    pred = PREDICATES.get(predicate)
    return pred.domain if pred else CLASSES


def resolve_attribute(head_word: str) -> Optional[str]:
    """§23 compound resolution: canonical predicate for a bare attribute head
    noun, or None if `head_word` isn't in the lexicon."""
    return ATTRIBUTE_LEXICON.get(head_word.lower())

"""P1 gold-corpus infrastructure (plan.md §33 P1, exit criterion: "≥ 10
examples per §30 category").

Real annotation - 400-600 propositions taken from actual weak-model answers
in the CODESYS/WAGO domain, labeled in Argilla/Label Studio per §32 - still
has to be collected by hand; that's a data-curation task, not something to
fabricate here. This module provides the category list, the example schema,
a coverage checker against the exit criterion, and one illustrative seed
example per §30 category to bootstrap that annotation effort.
"""
from __future__ import annotations

from dataclasses import dataclass

CATEGORIES: dict[int, str] = {
    1: "coordinated_objects", 2: "coordinated_subjects", 3: "collective_reading",
    4: "gapping", 5: "relative_clause", 6: "apposition", 7: "passive",
    8: "copula_preposition", 9: "existential", 10: "possessive_compound",
    11: "nominalization", 12: "light_verb", 13: "pronoun", 14: "bridging",
    15: "list_inheritance", 16: "table", 17: "negation_scope",
    18: "double_negation", 19: "pseudo_negation", 20: "modality", 21: "hedge",
    22: "conditional", 23: "counterfactual", 24: "causal_temporal",
    25: "quantifier", 26: "generic", 27: "comparative_ratio", 28: "superlative",
    29: "range_tolerance_bound", 30: "number_format", 31: "relative_percentage",
    32: "version_scope", 33: "attribution", 34: "example_list",
    35: "parenthesis_default", 36: "definition", 37: "identifiers",
    38: "code_block", 39: "instruction", 40: "language_mix",
}

MIN_EXAMPLES_PER_CATEGORY = 10


@dataclass
class GoldExample:
    category_id: int
    text: str
    language: str = "en"
    notes: str = ""


SEED_EXAMPLES: list[GoldExample] = [
    GoldExample(1, "The PFC200 supports Modbus TCP and OPC UA."),
    GoldExample(2, "The PFC100 and PFC200 run Linux."),
    GoldExample(3, "The PFC100 and PFC200 together draw 5 A."),
    GoldExample(4, "Input 1 uses 24 V, input 2 12 V."),
    GoldExample(5, "The controller, which runs CODESYS 3.5, has 8 inputs."),
    GoldExample(6, "PFC200, a Linux-based PLC, has two Ethernet ports."),
    GoldExample(7, "The value is written by task 2."),
    GoldExample(8, "The fuse is located in cabinet 3."),
    GoldExample(9, "There are 8 inputs on module X."),
    GoldExample(10, "The PFC200's supply voltage is 24 V.", notes="also DE: Versorgungsspannung"),
    GoldExample(11, "Activation of the pump occurs after a delay."),
    GoldExample(12, "Perform a restart to apply the change."),
    GoldExample(13, "It supports EtherCAT."),
    GoldExample(14, "The module has 8 channels. The voltage is 24 V."),
    GoldExample(15, "Features:\n- 2 Ethernet ports\n- 1 USB port"),
    GoldExample(16, "| Parameter | Value |\n|---|---|\n| Voltage | 24 V |"),
    GoldExample(17, "The device does not support A and B."),
    GoldExample(18, "This configuration is not impossible."),
    GoldExample(19, "The module offers not only Modbus but also OPC UA."),
    GoldExample(20, "The device must support 24 V input."),
    GoldExample(21, "The device usually starts within 5 seconds."),
    GoldExample(22, "If the fuse trips, the output switches off."),
    GoldExample(23, "The task would have failed without the patch."),
    GoldExample(24, "Since the fuse tripped, the output switched off."),
    GoldExample(25, "All modules support at least 2 ports."),
    GoldExample(26, "PLCs use cyclic tasks."),
    GoldExample(27, "The PFC200 is twice as fast as the PFC100."),
    GoldExample(28, "The PFC200 is the fastest module in the series."),
    GoldExample(29, "The supply voltage is 24 V ±10 %."),
    GoldExample(30, "Der Druck beträgt 3,5 bar.", language="de"),
    GoldExample(31, "Throughput is 20 % higher than the previous model."),
    GoldExample(32, "Since firmware 04, the device supports OPC UA."),
    GoldExample(33, "According to the manual, the fuse rating is 1 A."),
    GoldExample(34, "The device supports several protocols, e.g. Modbus."),
    GoldExample(35, "The timeout defaults to 500 ms (default: 500 ms)."),
    GoldExample(36, "PLC means Programmable Logic Controller."),
    GoldExample(37, "Set GVL.xStart to configure the address 192.168.1.10."),
    GoldExample(38, "Use this code:\n```st\nGVL.xStart := TRUE;\n```"),
    GoldExample(39, "Open the device tree and select the module."),
    GoldExample(40, "Die Versorgungsspannung beträgt 24 V DC.", language="de"),
]


def coverage_report(examples: list[GoldExample] = SEED_EXAMPLES) -> dict[int, int]:
    """category_id -> example count."""
    counts = {cid: 0 for cid in CATEGORIES}
    for ex in examples:
        counts[ex.category_id] = counts.get(ex.category_id, 0) + 1
    return counts


def missing_coverage(examples: list[GoldExample] = SEED_EXAMPLES) -> dict[int, int]:
    """category_id -> how many more annotated examples are needed to hit the
    P1 exit criterion (0 if already met)."""
    counts = coverage_report(examples)
    return {
        cid: max(0, MIN_EXAMPLES_PER_CATEGORY - counts.get(cid, 0))
        for cid in CATEGORIES
    }

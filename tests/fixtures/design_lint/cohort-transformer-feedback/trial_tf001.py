"""Detector-level synthetic probe for pinned kicad-happy TF-001."""

from __future__ import annotations

import json
from collections.abc import Sequence
from types import SimpleNamespace
from typing import Literal, TypedDict

from domain_detectors import detect_transformer_feedback


class ComponentPin(TypedDict):
    number: str
    name: str


class ComponentRecord(TypedDict):
    reference: str
    type: Literal["ic"]
    value: str
    lib_id: str
    pins: list[ComponentPin]


class FeedbackSummary(TypedDict):
    rule_id: str
    reference: str
    optocoupler: str | None
    shunt_reference: str | None
    confidence: Literal["deterministic", "heuristic"]
    evidence_source: str
    components: list[str]
    description: str


def _component(
    reference: str, value: str, lib_id: str, pins: Sequence[tuple[str, str]]
) -> ComponentRecord:
    return {
        "reference": reference,
        "type": "ic",
        "value": value,
        "lib_id": lib_id,
        "pins": [ComponentPin(number=number, name=name) for number, name in pins],
    }


def _context(case: str) -> SimpleNamespace:
    components = [_component("U1", "UC3842", "Controller:UC3842", [("1", "FB")])]
    pin_nets: dict[str, dict[str, tuple[str, None]]] = {"U1": {"1": ("FB_NET", None)}}
    if case != "controller_only":
        components.extend(
            [
                _component(
                    "U2",
                    "PC817",
                    "Optocoupler:PC817",
                    [("1", "C"), ("2", "E"), ("3", "A"), ("4", "K")],
                ),
                _component(
                    "U3",
                    "TL431",
                    "Regulator:TL431",
                    [("1", "REF"), ("2", "A"), ("3", "K")],
                ),
            ]
        )
        if case == "keyword_match":
            pin_nets["U2"] = {
                "1": ("FB_NET", None),
                "2": ("OPTO_RETURN", None),
                "3": ("SENSE_NET", None),
                "4": ("OPTO_K", None),
            }
            pin_nets["U3"] = {
                "1": ("SENSE_NET", None),
                "2": ("TL431_A", None),
                "3": ("TL431_K", None),
            }
        else:
            pin_nets["U2"] = {
                "1": ("SENSE_NET", None),
                "2": ("OPTO_RETURN", None),
                "3": ("FB_NET", None),
                "4": ("OPTO_K", None),
            }
            pin_nets["U3"] = {
                "1": ("TL431_REF", None),
                "2": ("TL431_A", None),
                "3": ("SENSE_NET", None),
            }
    return SimpleNamespace(
        components=components,
        comp_lookup={item["reference"]: item for item in components},
        ref_pins=pin_nets,
        nets={},
    )


def _summarize(case: str) -> list[FeedbackSummary]:
    keys = (
        "rule_id",
        "reference",
        "optocoupler",
        "shunt_reference",
        "confidence",
        "evidence_source",
        "components",
        "description",
    )
    return [
        {key: item[key] for key in keys} for item in detect_transformer_feedback(_context(case))
    ]


def main() -> None:
    cases = ("keyword_match", "controller_only", "role_agnostic_match")
    results = {name: _summarize(name) for name in cases}
    assert results["keyword_match"][0]["confidence"] == "deterministic"
    assert results["keyword_match"][0]["shunt_reference"] is not None
    assert results["controller_only"][0]["optocoupler"] is None
    assert results["role_agnostic_match"][0]["confidence"] == "deterministic"
    assert all("T1" not in item["components"] for case in results.values() for item in case)
    assert results == {name: _summarize(name) for name in cases}
    print(json.dumps(results, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()

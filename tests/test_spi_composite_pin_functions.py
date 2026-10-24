"""Exact slash-separated SPI aliases on dual-interface symbol pins."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted_digital_peer_spi_roster import (
    verify_spi_composite_alias_coverage,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import ComponentContract, DesignLintPolicy, NetlistContract
from kicad_tooling.hwrepo.spi_models import SpiAnalysis
from kicad_tooling.hwrepo.spi_participants import SpiRosterContext, unmapped_spi_participants
from tests.spi_participant_support import coach, spi_netlist, spi_roster

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


@pytest.mark.design_lint_rule(rule_id="bus.spi_unmapped_participant")
def test_combo_interface_spi_aliases_are_reviewed_but_i2c_only_names_are_not() -> None:
    source = spi_netlist(combo_interface=True)
    context = SpiRosterContext(
        state="required",
        analysis=spi_roster(device_references=("U2", "U3")),
        source_path="projects/synthetic-spi-roster/electrical.json",
        source_sha256="b" * 64,
    )

    report = evaluate(
        "synthetic-spi-roster",
        coach(source),
        DesignLintPolicy(),
        spi_roster=context,
    )
    finding = next(
        item for item in report.findings if item.rule_id == "bus.spi_unmapped_participant"
    )
    assert finding.subject == "U4: SPI roster coverage"
    assert finding.evidence["SCK_pins"] == ("U4.1",)
    assert finding.evidence["input_data_pins"] == ("U4.2",)
    assert finding.evidence["output_data_pins"] == ("U4.2", "U4.3")
    assert finding.evidence["chip_select_pins"] == ("U4.4",)

    i2c_only_functions = dict(source.pin_functions)
    i2c_only_functions.update({"U4.1": "SCL", "U4.2": "SDA", "U4.3": "SA0", "U4.4": "INT1"})
    i2c_only = source.model_copy(update={"pin_functions": i2c_only_functions})
    candidates = unmapped_spi_participants(i2c_only, context)
    assert "U4" not in {item.reference for item in candidates}


@pytest.mark.design_lint_rule(rule_id="bus.spi_unmapped_participant")
def test_combo_interface_spi_alias_review_is_stable_and_roster_entry_clears_it() -> None:
    source = spi_netlist(combo_interface=True)
    rule_id = "bus.spi_unmapped_participant"

    def findings(
        netlist: NetlistContract,
        roster: SpiAnalysis,
    ) -> dict[str, tuple[str, dict[str, tuple[str, ...]]]]:
        report = evaluate(
            "synthetic-spi-roster",
            coach(netlist),
            DesignLintPolicy(),
            spi_roster=SpiRosterContext(state="required", analysis=roster),
        )
        return {
            item.subject: (item.fingerprint, item.evidence)
            for item in report.findings
            if item.rule_id == rule_id
        }

    incomplete = spi_roster(device_references=("U2", "U3"))
    original = findings(source, incomplete)
    assert tuple(original) == ("U4: SPI roster coverage",)

    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    assert findings(reordered, incomplete) == original
    assert not findings(source, spi_roster(device_references=("U2", "U3", "U4")))


@pytest.mark.design_lint_rule(rule_id="bus.spi_unmapped_participant")
def test_hosted_combo_alias_lane_records_fault_and_roster_control() -> None:
    fixture = (
        Path(__file__).parent
        / "fixtures/design_lint/spi-composite-participant-native/combo-device.kicad_sch"
    )
    fixture_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
    observed = NetlistContract(
        components={"U1": ComponentContract(value="Synthetic combo", footprint="Synthetic:QFN")},
        nets={
            "SENSOR_CLOCK": ("U1.1",),
            "SENSOR_DATA": ("U1.2",),
            "SENSOR_OUT": ("U1.3",),
            "SENSOR_CS": ("U1.4",),
        },
        component_symbols={"U1": "Synthetic:Combo_SPI_Node"},
        pin_functions={
            "U1.1": "SCL/SPC",
            "U1.2": "SDA/SDI/SDO",
            "U1.3": "SDO/SA0",
            "U1.4": "CS",
        },
        component_pin_numbers={"U1": ("1", "2", "3", "4")},
    )
    root = Path(__file__).resolve().parents[1]
    events: list[tuple[str, str, dict[str, str | float]]] = []

    def record_event(stage: str, status: str, **details: str | float) -> None:
        events.append((stage, status, details))

    context = SimpleNamespace(
        contracts={"combo-device": {"first": observed}},
        hashes={"combo-device": {"first": "c" * 64, "repeat": "d" * 64}},
        normalized_hashes={"combo-device": {"first": "e" * 64, "repeat": "e" * 64}},
        combo_spi_source_hash=fixture_hash,
        config=SimpleNamespace(kicad_version="10.0.5"),
        log=SimpleNamespace(event=record_event),
        project="synthetic-spi-composite",
        pinned="synthetic:kicad-10.0.5",
        root=root,
        scratch=root / "build/test-spi-composite",
    )

    verify_spi_composite_alias_coverage(context)

    assert tuple((stage, status) for stage, status, _details in events) == (
        ("spi-participant-fixture/composite-unrostered", "PASS"),
        ("spi-participant-fixture/composite-rostered", "PASS"),
    )
    assert all(details["source_sha256"] == fixture_hash for _stage, _status, details in events)
    assert events[0][2]["lint_status"] == "REVIEW"
    assert events[0][2]["findings"] == "U1: SPI roster coverage"
    assert events[1][2]["lint_status"] == "PASS"
    assert events[1][2]["findings"] == "none"

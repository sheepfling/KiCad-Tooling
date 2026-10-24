"""Focused regressions for open SPI data pins on partially connected channels."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.spi_unconnected_data_pins import spi_unconnected_data_netlist

RULE_ID = "bus.spi_unconnected_data_pin"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    source: NetlistContract | None = None,
    mode: str | None = None,
    ignores: tuple[DesignLintIgnore, ...] = (),
) -> DesignLintReport:
    selected = spi_unconnected_data_netlist() if source is None else source
    overrides = (
        ()
        if mode is None
        else (DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="test policy"),)
    )
    return evaluate(
        "synthetic-spi-unconnected-data-pin",
        coach(selected),
        DesignLintPolicy(rules=overrides, ignores=ignores),
    )


def test_native_fault_fixture_source_is_pinned() -> None:
    fixture = (
        Path(__file__).parent
        / "fixtures/design_lint/spi-unconnected-data-native/open-mosi.kicad_sch"
    )
    assert sha256(fixture.read_bytes()).hexdigest() == (
        "d18786cbb35cf58f723b452b12b61abe5b3f347ebc1a540e3b9655097e98f13d"
    )


def test_open_spi_data_pin_emits_exact_review_evidence_when_enabled() -> None:
    report = _report(mode="review")
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert finding.subject == "U1.1: MOSI"
    assert finding.evidence == {
        "U1.1": (),
        "function": ("MOSI",),
        "spi_channel": ("default",),
        "spi_data_family": ("MOSI-family",),
    }
    assert "does not establish SPI use or PCB routing" in finding.message


def test_rule_defaults_off_and_supports_review_block_off_and_exact_ignore() -> None:
    default = next(item for item in _report().findings if item.rule_id == RULE_ID)
    assert (default.mode, default.disposition) == ("off", "RULE_OFF")
    assert _report(mode="review").status == "REVIEW"
    assert _report(mode="block").status == "FAIL"
    assert _report(mode="off").status == _report().status
    ignored = _report(
        mode="review",
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=default.fingerprint,
                reason="reviewed intentionally unused SPI data direction",
            ),
        ),
    )
    ignored_findings = [item for item in ignored.findings if item.rule_id == RULE_ID]
    assert len(ignored_findings) == 1
    assert ignored_findings[0].disposition == "IGNORED"


@pytest.mark.parametrize(
    ("function", "family", "channel", "assigned_function"),
    (
        ("MOSI", "MOSI-family", "default", "MISO"),
        ("SDI", "MOSI-family", "default", "SDO"),
        ("COPI", "MOSI-family", "default", "CIPO"),
        ("MISO", "MISO-family", "default", "MOSI"),
        ("SDO", "MISO-family", "default", "SDI"),
        ("CIPO", "MISO-family", "default", "COPI"),
        ("SPI1_COPI", "MOSI-family", "index1", "SPI1_CIPO"),
    ),
)
def test_supported_data_aliases_keep_role_and_channel_evidence(
    function: str, family: str, channel: str, assigned_function: str
) -> None:
    source = spi_unconnected_data_netlist(
        open_pins=("U1.1",),
        functions={
            "U1.1": function,
            "U1.2": assigned_function,
            "U2.1": "SPI1_COPI",
            "U2.2": "SPI1_CIPO",
        },
    )
    finding = next(
        item for item in _report(source, mode="review").findings if item.rule_id == RULE_ID
    )
    assert finding.evidence["spi_data_family"] == (family,)
    assert finding.evidence["spi_channel"] == (channel,)


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(spi_unconnected_data_netlist(open_pins=()), id="connected-control"),
        pytest.param(
            spi_unconnected_data_netlist(open_pins=("U1.1", "U1.2", "U2.1", "U2.2")),
            id="all-data-pins-open",
        ),
        pytest.param(
            spi_unconnected_data_netlist(
                open_pins=("U1.1",),
                functions={
                    "U1.1": "SPI1_COPI",
                    "U1.2": "SPI0_CIPO",
                    "U2.1": "SPI1_COPI",
                    "U2.2": "SPI1_CIPO",
                },
            ),
            id="different-channel-control",
        ),
        pytest.param(spi_unconnected_data_netlist(dnp_components=("U1",)), id="dnp-ic"),
        pytest.param(
            spi_unconnected_data_netlist(
                functions={
                    "U1.1": "MOSI_TX",
                    "U1.2": "MISO_RX",
                    "U2.1": "COPI",
                    "U2.2": "CIPO",
                }
            ),
            id="unsupported-aliases",
        ),
    ),
)
def test_connected_unused_or_unsupported_shapes_do_not_emit(source: NetlistContract) -> None:
    assert not any(item.rule_id == RULE_ID for item in _report(source, mode="review").findings)


def test_connector_reference_is_outside_the_spi_ic_predicate() -> None:
    source = spi_unconnected_data_netlist(open_pins=("J1.1",))
    source = source.model_copy(
        update={
            "components": {
                "J1": source.components["U1"],
                "U2": source.components["U2"],
            },
            "component_pin_numbers": {"J1": ("1", "2"), "U2": ("1", "2")},
            "component_symbols": {
                "J1": "Synthetic:SpiConnector",
                "U2": source.component_symbols["U2"],
            },
            "pin_functions": {
                "J1.1": "MOSI",
                "J1.2": "MISO",
                "U2.1": "COPI",
                "U2.2": "CIPO",
            },
        }
    )
    assert not any(item.rule_id == RULE_ID for item in _report(source, mode="review").findings)


def test_ambiguous_assignment_does_not_count_as_channel_activity() -> None:
    source = spi_unconnected_data_netlist(open_pins=("U1.1",))
    source = source.model_copy(update={"nets": {**source.nets, "SPI_AUX": ("U1.2",)}})
    assert not any(item.rule_id == RULE_ID for item in _report(source, mode="review").findings)


def test_ordering_is_stable_and_assigning_open_pin_clears_candidate() -> None:
    source = spi_unconnected_data_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
        }
    )
    original = next(
        item for item in _report(source, mode="review").findings if item.rule_id == RULE_ID
    )
    repeated = next(
        item for item in _report(reordered, mode="review").findings if item.rule_id == RULE_ID
    )
    repaired = source.model_copy(update={"nets": {**source.nets, "SPI_MOSI": ("U1.1", "U2.1")}})

    assert (repeated.fingerprint, repeated.evidence) == (original.fingerprint, original.evidence)
    assert not any(item.rule_id == RULE_ID for item in _report(repaired, mode="review").findings)

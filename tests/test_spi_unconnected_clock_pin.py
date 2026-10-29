"""Deterministic review coverage for open SPI clock functions."""

from __future__ import annotations

import hashlib
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
from tests.design_lint_fixtures.spi_unconnected_clock_pin import spi_unconnected_clock_netlist

RULE_ID = "bus.spi_unconnected_clock_pin"
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
    selected = spi_unconnected_clock_netlist(open_pins=("U1.1",)) if source is None else source
    overrides = (
        ()
        if mode is None
        else (DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="test policy"),)
    )
    return evaluate(
        "synthetic-spi-unconnected-clock",
        coach(selected),
        DesignLintPolicy(rules=overrides, ignores=ignores),
    )


def test_open_clock_with_assigned_same_channel_data_emits_exact_review_evidence() -> None:
    finding = next(item for item in _report(mode="review").findings if item.rule_id == RULE_ID)
    assert finding.subject == "U1.1: SCK"
    assert finding.evidence == {
        "U1.1": (),
        "active_peer_pins": ("U1.2",),
        "function": ("SCK",),
        "spi_channel": ("default",),
    }
    assert "does not establish SPI use or PCB routing" in finding.message


def test_native_fixture_sources_match_reviewed_hashes() -> None:
    root = Path(__file__).parent / "fixtures/design_lint/spi-unconnected-clock-native"
    expected = {
        "control.kicad_sch": "cf9cf52926767b8d4a3ba311bec79f669d95a2d3fc4865cdc895ab7b48c9e738",
        "fault.kicad_sch": "bd2d07d875ef4b580a8d378dfc92d757c4a856b4ce76b5f2167810184fe0f214",
    }
    assert {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in expected
    } == expected


def test_policy_and_exact_ignore_are_configurable() -> None:
    default = next(item for item in _report().findings if item.rule_id == RULE_ID)
    assert (default.mode, default.disposition) == ("off", "RULE_OFF")
    assert _report(mode="review").status == "REVIEW"
    assert _report(mode="block").status == "FAIL"
    ignored = _report(
        mode="review",
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=default.fingerprint,
                reason="reviewed unused clock function",
            ),
        ),
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(spi_unconnected_clock_netlist(open_pins=()), id="clock-assigned"),
        pytest.param(
            spi_unconnected_clock_netlist(open_pins=("U1.1", "U1.2", "U2.1", "U2.2")),
            id="all-channel-pins-open",
        ),
        pytest.param(
            spi_unconnected_clock_netlist(
                open_pins=("U1.1",),
                functions={
                    "U1.1": "SPI1_SCK",
                    "U1.2": "SPI0_MOSI",
                    "U2.1": "SPI1_SCK",
                    "U2.2": "SPI1_MISO",
                },
            ),
            id="other-channel-active",
        ),
        pytest.param(
            spi_unconnected_clock_netlist(open_pins=("U1.1",), dnp_components=("U1",)),
            id="dnp-component",
        ),
        pytest.param(
            spi_unconnected_clock_netlist(
                open_pins=("U1.1",), functions={"U1.1": "CLK", "U1.2": "MOSI"}
            ),
            id="generic-clock-name",
        ),
    ),
)
def test_unsupported_or_inactive_clock_shapes_are_quiet(source: NetlistContract) -> None:
    assert not any(item.rule_id == RULE_ID for item in _report(source, mode="review").findings)


def test_ordering_is_stable_and_assigning_open_clock_clears_candidate() -> None:
    source = spi_unconnected_clock_netlist(open_pins=("U1.1",))
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    findings = lambda report: tuple(
        (item.subject, item.fingerprint) for item in report.findings if item.rule_id == RULE_ID
    )
    assert findings(_report(source, mode="review")) == findings(_report(reordered, mode="review"))
    repaired = source.model_copy(update={"nets": {**source.nets, "SPI_CLK": ("U1.1", "U2.1")}})
    assert not any(item.rule_id == RULE_ID for item in _report(repaired, mode="review").findings)

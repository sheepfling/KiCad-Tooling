"""Repeated-component power-domain hosted-lane fixture checks."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
]

_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures/design_lint/component-peer-power-native"


@pytest.mark.parametrize(
    ("filename", "expected_sha256"),
    (
        pytest.param(
            "control.kicad_sch",
            "0198205216be6cd5be0c03ac14b7c2b9de52258aacd564159e16532fadb10446",
            id="control",
        ),
        pytest.param(
            "fault.kicad_sch",
            "92a2cfda8088c7eebe8305e5ecf786870ed44bc846acb031fe4bb1d567418ae3",
            id="fault",
        ),
    ),
)
def test_component_peer_power_fixture_matches_synthetic_digest(filename, expected_sha256) -> None:
    source = _FIXTURE_ROOT / filename
    text = source.read_text(encoding="utf-8")

    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_sha256
    assert "NOT FOR MANUFACTURE - tooling fixture" in text
    assert text.count('(symbol "Synthetic:PeerModule"') == 1
    assert text.count('(lib_id "Synthetic:PeerModule")') == 2


def test_component_peer_power_lane_reports_divergence_and_control(
    digital_peer_fixture_results,
) -> None:
    results = digital_peer_fixture_results
    control = results["component-peer-power-fixture/control"]
    fault = results["component-peer-power-fixture/fault"]

    assert control["lint_status"] == "PASS"
    assert control["peer_power_findings"] == "none"
    assert control["pin_assignments"] == (
        "U1.1=IO_SHARED;U1.2=+3V3;U1.3=GND;U2.1=IO_SHARED;U2.2=+3V3;U2.3=GND"
    )
    assert fault["lint_status"] == "REVIEW"
    assert fault["peer_power_findings"] == (
        "component.peer_power_pin_assignment_divergence;"
        "component.peer_power_pin_assignment_divergence"
    )
    assert fault["divergent_pin_roles"] == "2:VDD:supply;3:GND:ground/return"
    assert fault["pin_assignments"] == (
        "U1.1=IO_SHARED;U1.2=+3V3;U1.3=AGND;U2.1=IO_SHARED;U2.2=+5V;U2.3=DGND"
    )

    for result in (control, fault):
        assert result["erc_report_version"] == "10.0.0"
        assert result["erc_warning_types"] == "none"
        assert result["erc_error_types"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]

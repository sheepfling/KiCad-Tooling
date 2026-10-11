"""Digest-pinned native component peer power-assignment regressions."""

from __future__ import annotations

import pytest

from tests.digital_peer_native_acceptance import NATIVE_DIGITAL_PEER_PROJECTS

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.parametrize(("project", "version"), NATIVE_DIGITAL_PEER_PROJECTS)
def test_component_peer_power_fault_control_and_native_erc_by_version(
    native_digital_peer_results, project: str, version: str
) -> None:
    results = native_digital_peer_results[project]
    control = results["component-peer-power-fixture/control"]
    fault = results["component-peer-power-fixture/fault"]

    assert control["kicad_version"] == version
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
    expected_erc = {
        "control": (
            "power_pin_not_driven;power_pin_not_driven",
            "footprint_link_issues;footprint_link_issues;lib_symbol_issues;lib_symbol_issues",
        ),
        "fault": (
            "power_pin_not_driven;power_pin_not_driven;power_pin_not_driven;power_pin_not_driven",
            (
                "footprint_link_issues;footprint_link_issues;isolated_pin_label;isolated_pin_label;"
                "isolated_pin_label;isolated_pin_label;lib_symbol_issues;lib_symbol_issues"
            ),
        ),
    }
    for name, result in (("control", control), ("fault", fault)):
        expected_errors, expected_warnings = expected_erc[name]
        assert result["erc_report_version"] == version
        assert result["erc_error_types"] == expected_errors
        assert result["erc_warning_types"] == expected_warnings
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]


def test_component_peer_power_normalized_netlists_match_across_native_versions(
    native_digital_peer_results,
) -> None:
    hashes_by_version = {
        version: tuple(
            native_digital_peer_results[project][f"component-peer-power-fixture/{case}"][
                "normalized_netlist_sha256"
            ]
            for case in ("control", "fault")
        )
        for project, version in NATIVE_DIGITAL_PEER_PROJECTS
    }
    assert hashes_by_version["10.0.0"] == hashes_by_version["10.0.5"]
    assert hashes_by_version["10.0.0"] == (
        "27b214dc9bd5b33dc7732f1155267462fb7a4efdcd2ed8efb7614ad3e489c0b6",
        "afb64b0e55b04276c8c2d45e94a6aeec056a424aeff2bb349be5aba78b36a1f9",
    )

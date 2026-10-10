"""Focused USB connector-to-PHY reference lint regressions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
    UsbDataInterfaceRequirement,
)
from tests.usb_c_peer_support import (
    usb_c_data_map,
    usb_c_peer_netlist,
)
from tests.usb_peer_reference_support import (
    PATH_RULE_ID,
    RULE_ID,
    lint_report,
    usb_data_map,
    usb_peer_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_usb_c_map_must_name_every_duplicate_contact_before_suppressing_review() -> None:
    observed = usb_c_peer_netlist()
    exact = usb_c_data_map()
    exact_report = lint_report(observed, path_map=exact)
    assert (RULE_ID) not in ({item.rule_id for item in exact_report.findings})
    assert (PATH_RULE_ID) not in ({item.rule_id for item in exact_report.findings})

    incomplete_report = lint_report(
        observed,
        path_map=usb_c_data_map(include_duplicate_contacts=False),
    )
    assert (RULE_ID) in ({item.rule_id for item in incomplete_report.findings})
    path_findings = tuple(
        item for item in incomplete_report.findings if item.rule_id == PATH_RULE_ID
    )
    assert ({item.evidence["line"][0] for item in path_findings}) == ({"D+", "D-"})
    assert all(
        "mapped D+ pin inventory" in " ".join(item.evidence["issues"])
        or "mapped D- pin inventory" in " ".join(item.evidence["issues"])
        for item in path_findings
    )


def test_exact_common_and_separate_usb_maps_resolve_the_review() -> None:
    cases = (
        (
            usb_peer_netlist(connector_reference_net="BOARD_GND", phy_reference_net="BOARD_GND"),
            usb_data_map(
                reference_policy="common_net",
                expected_connector_reference_net="BOARD_GND",
                expected_phy_reference_net="BOARD_GND",
            ),
        ),
        (
            usb_peer_netlist(),
            usb_data_map(reference_policy="separate_nets"),
        ),
    )
    for observed, path_map in cases:
        report = lint_report(observed, path_map=path_map)
        rule_ids = {item.rule_id for item in report.findings}
        context = path_map.interfaces[0].reference_policy
        assert RULE_ID not in rule_ids, context
        assert PATH_RULE_ID not in rule_ids, context


def test_source_matched_map_reports_stale_reference_assignment() -> None:
    report = lint_report(
        usb_peer_netlist(),
        path_map=usb_data_map(reference_policy="common_net", expected_phy_reference_net="USB_GND"),
    )
    assert (RULE_ID) not in ({item.rule_id for item in report.findings}), (
        "the explicit current map owns this decision and should avoid a duplicate prompt"
    )
    mismatch = next(item for item in report.findings if item.rule_id == PATH_RULE_ID)
    assert (mismatch.subject) == ("usb-interface-1: USB reference path")
    assert ("U1 reference assignments differ") in (" ".join(mismatch.evidence["issues"]))


def test_stale_map_identity_does_not_suppress_peer_review() -> None:
    path_map = usb_data_map(reference_policy="separate_nets", phy_reference_pin="U1.8")
    report = lint_report(usb_peer_netlist(), path_map=path_map)
    assert (RULE_ID) in ({item.rule_id for item in report.findings})
    assert (PATH_RULE_ID) in ({item.rule_id for item in report.findings})


def test_review_block_off_and_exact_ignore_are_project_configurable() -> None:
    fault = lint_report(usb_peer_netlist())
    finding = next(item for item in fault.findings if item.rule_id == RULE_ID)
    ignored = lint_report(
        usb_peer_netlist(),
        ignore=DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=finding.fingerprint,
            reason="Synthetic owner decision: retain separate interface references",
        ),
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert (ignored_finding.disposition) == ("IGNORED")
    blocked = lint_report(
        usb_peer_netlist(),
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="block",
            reason="Synthetic acceptance mode",
        ),
    )
    assert (blocked.status) == ("FAIL")
    disabled = lint_report(
        usb_peer_netlist(),
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="off",
            reason="Synthetic not-applicable decision",
        ),
    )
    disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
    assert (disabled_finding.disposition) == ("RULE_OFF")


def test_reference_map_requires_complete_commonality_decision_shape() -> None:
    with pytest.raises(ValidationError):
        usb_data_map(reference_policy="common_net")
    with pytest.raises(ValidationError):
        UsbDataInterfaceRequirement.model_validate(
            {
                **usb_data_map(reference_policy="separate_nets").interfaces[0].model_dump(),
                "reference_policy": "common_net",
                "phy_reference_pins": ({"pin": "U1.3", "net": "BOARD_GND"},),
            }
        )

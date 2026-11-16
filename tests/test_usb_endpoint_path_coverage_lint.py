"""Configurable review for USB endpoint groups outside supported path coverage."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintRuleOverride
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.usb_data_path_support import (
    lint_report as lint_usb_data_path,
)
from tests.usb_data_path_support import (
    usb_inline_component_map,
    usb_inline_component_netlist,
)
from tests.usb_peer_reference_support import lint_report, usb_peer_netlist

RULE_ID = "bus.usb_endpoint_path_coverage_incomplete"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _finding(report: DesignLintReport):
    return next(item for item in report.findings if item.rule_id == RULE_ID)


def test_incomplete_recognized_endpoints_get_a_non_defect_review_prompt() -> None:
    report = lint_report(usb_peer_netlist(incomplete=True))
    finding = _finding(report)

    assert finding.mode == "review"
    assert "does not infer a missing connection" in finding.message
    assert finding.evidence["unassessed_USB_endpoint_groups"] == (
        "connector J1 (USB 2.0 data; SUPPORTED)",
        "phy U1 (USB 2.0 data; INCOMPLETE)",
    )
    assert report.usb_peer_reference_coverage is not None
    assert report.usb_peer_reference_coverage.status == "INCOMPLETE"


def test_complete_but_unpaired_usb_endpoints_get_coverage_review() -> None:
    observed = usb_peer_netlist()
    nets = dict(observed.nets)
    nets["USB_DP"] = ("J1.1",)
    nets["USB_DP_PHY"] = ("U1.1",)

    report = lint_report(observed.model_copy(update={"nets": nets}))
    finding = _finding(report)

    assert finding.evidence["unassessed_USB_endpoint_groups"] == (
        "connector J1 (USB 2.0 data; SUPPORTED)",
        "phy U1 (USB 2.0 data; SUPPORTED)",
    )
    assert report.usb_peer_reference_coverage is not None
    assert report.usb_peer_reference_coverage.status == "NO_SUPPORTED_PEER_PATHS"
    assert report.usb_peer_reference_coverage.incomplete_group_count == 0


def test_supported_usb_path_is_a_quiet_coverage_control() -> None:
    report = lint_report(usb_peer_netlist())

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    assert report.usb_peer_reference_coverage is not None
    assert report.usb_peer_reference_coverage.supported_data_path_count == 1


def test_dnp_only_connector_groups_do_not_create_coverage_prompts() -> None:
    report = lint_report(usb_peer_netlist(dnp=("J1",)))

    assert not any(item.rule_id == RULE_ID for item in report.findings)


def test_unrecognized_projects_do_not_get_usb_endpoint_coverage_prompts() -> None:
    report = lint_report(NetlistContract(components={}, nets={}))

    assert report.usb_peer_reference_coverage is not None
    assert report.usb_peer_reference_coverage.status == "NO_USB_ENDPOINTS"
    assert not any(item.rule_id == RULE_ID for item in report.findings)


def test_specific_unmapped_topology_prompt_supersedes_generic_coverage_prompt() -> None:
    report = lint_usb_data_path(usb_inline_component_netlist(), path_map=None)

    assert any(item.rule_id == "bus.usb_unmapped_multi_pin_topology" for item in report.findings)
    assert not any(item.rule_id == RULE_ID for item in report.findings), tuple(
        item.evidence for item in report.findings if item.rule_id == RULE_ID
    )


def test_exact_authored_map_resolves_endpoint_coverage_prompt() -> None:
    report = lint_usb_data_path(usb_inline_component_netlist(), path_map=usb_inline_component_map())

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    assert report.usb_peer_reference_coverage is not None
    assert report.usb_peer_reference_coverage.supported_data_path_count == 1


def test_stale_authored_map_leaves_exact_map_mismatch_as_the_specific_finding() -> None:
    path_map = usb_inline_component_map()
    interface = path_map.interfaces[0].model_copy(
        update={
            "inline_component": path_map.interfaces[0].inline_component.model_copy(
                update={"expected_symbol": "Synthetic:WrongProtection"}
            )
        }
    )
    report = lint_usb_data_path(
        usb_inline_component_netlist(),
        path_map=path_map.model_copy(update={"interfaces": (interface,)}),
    )

    assert any(item.rule_id == "bus.usb_data_path_mismatch" for item in report.findings)
    assert not any(item.rule_id == RULE_ID for item in report.findings)


def test_rule_override_and_exact_ignore_are_available() -> None:
    observed = usb_peer_netlist(incomplete=True)
    review = _finding(lint_report(observed))
    blocked = _finding(
        lint_report(
            observed,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="This project requires complete USB endpoint review",
            ),
        )
    )
    disabled = lint_report(
        observed,
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="off",
            reason="This project tracks USB coverage in a separate review",
        ),
    )
    ignored = lint_report(
        observed,
        ignore=DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=review.fingerprint,
            reason="The endpoint group is intentionally unsupported by this analyzer",
        ),
    )

    assert review.mode == "review"
    assert blocked.mode == "block"
    assert _finding(disabled).disposition == "RULE_OFF"
    assert _finding(ignored).disposition == "IGNORED"


def test_endpoint_coverage_fingerprint_is_stable_under_netlist_mapping_order() -> None:
    observed = usb_peer_netlist(incomplete=True)
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )

    first = _finding(lint_report(observed))
    second = _finding(lint_report(reordered))

    assert (second.fingerprint, second.evidence) == (first.fingerprint, first.evidence)

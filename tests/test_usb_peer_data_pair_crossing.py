"""Review crossed USB 2.0 data pairs using source-bound endpoint evidence."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_data_pair_crossing import (
    usb_data_pair_crossing_netlist,
    usb_data_pair_crossing_with_port_groups,
    usb_data_pair_crossing_with_tvs_shunt,
    usb_data_pair_crossing_with_unrelated_branch,
)

RULE_ID = "bus.usb_peer_data_pair_crossed"

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _findings(observed: NetlistContract):
    return tuple(item for item in candidates(observed) if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_neutral_usb_data_nets_with_crossed_endpoint_functions_are_reviewed() -> None:
    observed = usb_data_pair_crossing_netlist()
    report = evaluate("synthetic-usb-pair-crossing", coach(observed), DesignLintPolicy())

    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    assert finding.mode == "review"
    assert finding.subject == "J1 / U1: USB 2.0 data pair is crossed"
    assert finding.evidence["connector_positive_pins"] == ("J1.1",)
    assert finding.evidence["connector_positive_net"] == ("DATA_A",)
    assert finding.evidence["phy_negative_pins"] == ("U1.2",)
    assert finding.evidence["connector_negative_pins"] == ("J1.2",)
    assert finding.evidence["phy_positive_pins"] == ("U1.1",)
    assert not any(
        item.rule_id == "bus.usb_data_polarity_label_mismatch" for item in report.findings
    )
    indexed = usb_data_pair_crossing_with_port_groups(
        connector_port_group="1",
        phy_port_group="1",
    )
    indexed_candidate = next(iter(_findings(indexed)))
    assert indexed_candidate.evidence["connector_port_group"] == ("1",)
    assert indexed_candidate.evidence["phy_port_group"] == ("1",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_correct_data_pair_and_explicit_polarity_labels_are_left_to_other_checks() -> None:
    correct = usb_data_pair_crossing_netlist(crossed=False)
    explicitly_labelled = usb_data_pair_crossing_netlist(net_names=("USB_D-", "USB_D+"))

    assert not _findings(correct)
    assert not _findings(explicitly_labelled)
    assert any(
        item.rule_id == "bus.usb_data_polarity_label_mismatch"
        for item in candidates(explicitly_labelled)
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_or_ambiguous_usb_endpoint_evidence_is_not_classified() -> None:
    crossed = usb_data_pair_crossing_netlist()
    incomplete_inventory = crossed.model_copy(
        update={"component_pin_numbers": {"J1": ("1", "2"), "U1": ("1", "2", "3")}}
    )
    ambiguous_assignment = crossed.model_copy(update={"nets": {**crossed.nets, "AUX": ("J1.1",)}})
    dnp = crossed.model_copy(update={"dnp_components": ("U1",)})
    open_reference = crossed.model_copy(
        update={"nets": {"DATA_A": ("J1.1", "U1.2"), "DATA_B": ("J1.2", "U1.1")}}
    )
    mismatched_port_groups = usb_data_pair_crossing_with_port_groups(
        connector_port_group="1",
        phy_port_group="2",
    )
    partly_indexed_pair = usb_data_pair_crossing_with_port_groups(
        connector_port_group=None,
        phy_port_group="1",
    )

    assert all(
        not _findings(item)
        for item in (
            incomplete_inventory,
            ambiguous_assignment,
            dnp,
            open_reference,
            mismatched_port_groups,
            partly_indexed_pair,
        )
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_bounded_tvs_shunt_is_allowed_but_unrelated_route_branch_is_not() -> None:
    assert len(_findings(usb_data_pair_crossing_with_tvs_shunt())) == 1
    assert not _findings(usb_data_pair_crossing_with_unrelated_branch())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_interface_map_owns_the_same_endpoint_pair() -> None:
    from kicad_tooling.hwrepo.usb_data_path_models import (
        UsbDataInterfaceRequirement,
        UsbDataPathLineRequirement,
        UsbDataPathMap,
    )
    from kicad_tooling.hwrepo.usb_reference_pin_models import UsbReferencePinRequirement

    path_map = UsbDataPathMap(
        basis="synthetic reviewed USB endpoint map",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="usb0",
                basis="synthetic reviewed USB endpoint map",
                connector_reference="J1",
                expected_connector_symbol="Connector:USB_A",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:USB_PHY",
                expected_phy_footprint="Synthetic:QFN",
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin="J1.1",
                    phy_pin="U1.1",
                    connector_net="DATA_A",
                    phy_net="DATA_A",
                    topology="direct",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin="J1.2",
                    phy_pin="U1.2",
                    connector_net="DATA_B",
                    phy_net="DATA_B",
                    topology="direct",
                ),
                connector_reference_pins=(UsbReferencePinRequirement(pin="J1.4", net="BOARD_GND"),),
                phy_reference_pins=(UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),),
                reference_policy="common_net",
            ),
        ),
    )

    mapped_candidates = candidates(usb_data_pair_crossing_netlist(), usb_data_path_map=path_map)

    assert any(item.rule_id == "bus.usb_data_path_mismatch" for item in mapped_candidates)
    assert not any(item.rule_id == RULE_ID for item in mapped_candidates)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_override_ignore_ordering_and_repair_are_deterministic() -> None:
    observed = usb_data_pair_crossing_netlist()
    base_report = evaluate("synthetic-usb-pair-crossing", coach(observed), DesignLintPolicy())
    finding = next(item for item in base_report.findings if item.rule_id == RULE_ID)
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
        }
    )
    reordered_finding = next(
        item
        for item in evaluate(
            "synthetic-usb-pair-crossing", coach(reordered), DesignLintPolicy()
        ).findings
        if item.rule_id == RULE_ID
    )
    blocked = evaluate(
        "synthetic-usb-pair-crossing",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Reviewed map"),)
        ),
    )
    disabled = evaluate(
        "synthetic-usb-pair-crossing",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Intentional map"),)
        ),
    )
    ignored = evaluate(
        "synthetic-usb-pair-crossing",
        coach(observed),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Reviewed endpoint pin map",
                ),
            )
        ),
    )
    corrected = usb_data_pair_crossing_netlist(crossed=False)

    assert reordered_finding.fingerprint == finding.fingerprint
    assert blocked.status == "FAIL"
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )
    assert not _findings(corrected)

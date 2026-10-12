"""Bounded USB SuperSpeed connector-to-PHY reference review regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import text_report
from kicad_tooling.hwrepo.models import DesignLintRuleOverride
from kicad_tooling.hwrepo.usb_peer_reference_review import usb_peer_reference_reviews
from tests.usb_peer_reference_support import RULE_ID, lint_report, usb_data_map
from tests.usb_peer_superspeed_support import superspeed_peer_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_split_reference_direct_superspeed_pair_emits_review_and_family_evidence() -> None:
    observed = superspeed_peer_netlist()
    reviews = usb_peer_reference_reviews(observed)
    assert len(reviews) == 1
    link = reviews[0].data_link
    assert (link.connector_signal_family, link.phy_signal_family) == (
        "USB SuperSpeed TX",
        "USB SuperSpeed RX",
    )
    assert (link.connector_positive_net, link.phy_positive_net) == ("SS_LANE_A", "SS_LANE_A")
    assert (link.connector_negative_net, link.phy_negative_net) == ("SS_LANE_B", "SS_LANE_B")

    report = lint_report(observed)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.subject == "J1 / U1: USB SuperSpeed reference-domain review"
    assert finding.evidence["USB_SuperSpeed_positive_link"] == ("J1.1 / U1.1=SS_LANE_A",)
    assert finding.evidence["USB_SuperSpeed_negative_link"] == ("J1.2 / U1.2=SS_LANE_B",)
    assert finding.evidence["USB_connector_pair_family"] == ("USB SuperSpeed TX",)
    assert finding.evidence["USB_PHY_pair_family"] == ("USB SuperSpeed RX",)
    assert "USB SuperSpeed TX -> RX" in text_report(report)
    assert "TX+ -> RX+" in text_report(report)

    coverage = report.usb_peer_reference_coverage
    assert coverage is not None
    assert coverage.supported_connector_group_count == 1
    assert coverage.supported_phy_group_count == 1
    assert coverage.separate_reference_path_count == 1


def test_common_reference_superspeed_pair_is_a_quiet_control() -> None:
    observed = superspeed_peer_netlist(
        connector_reference_net="BOARD_GND",
        phy_reference_net="BOARD_GND",
    )
    assert usb_peer_reference_reviews(observed) == ()
    report = lint_report(observed)
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.usb_peer_reference_coverage.common_reference_path_count == 1


def test_full_duplex_superspeed_reviews_each_complementary_direction() -> None:
    observed = superspeed_peer_netlist(full_duplex=True)
    report = lint_report(observed)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    assert len(findings) == 2
    coverage = report.usb_peer_reference_coverage
    assert coverage is not None
    assert coverage.supported_data_path_count == 2
    assert coverage.candidate_group_count == 2
    assert {
        (item.data_path.connector_signal_family, item.data_path.phy_signal_family)
        for item in coverage.path_entries
    } == {
        ("USB SuperSpeed TX", "USB SuperSpeed RX"),
        ("USB SuperSpeed RX", "USB SuperSpeed TX"),
    }

    common = superspeed_peer_netlist(
        full_duplex=True,
        connector_reference_net="BOARD_GND",
        phy_reference_net="BOARD_GND",
    )
    assert RULE_ID not in {item.rule_id for item in lint_report(common).findings}


def test_usb_2_data_map_cannot_suppress_a_superspeed_reference_review() -> None:
    observed = superspeed_peer_netlist()
    path_map = usb_data_map(reference_policy="separate_nets")
    interface = path_map.interfaces[0]
    superspeed_interface = interface.model_copy(
        update={
            "positive": interface.positive.model_copy(
                update={"connector_net": "SS_LANE_A", "phy_net": "SS_LANE_A"}
            ),
            "negative": interface.negative.model_copy(
                update={"connector_net": "SS_LANE_B", "phy_net": "SS_LANE_B"}
            ),
        }
    )
    report = lint_report(
        observed,
        path_map=path_map.model_copy(update={"interfaces": (superspeed_interface,)}),
    )
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.evidence["USB_reference_policy_state"] == ("USB_2.0_map_not_applicable",)


def test_project_rule_override_can_turn_off_superspeed_review() -> None:
    report = lint_report(
        superspeed_peer_netlist(),
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="off",
            reason="Synthetic project reviewed this isolated reference domain",
        ),
    )
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.disposition == "RULE_OFF"


@pytest.mark.parametrize(
    ("changes", "expected_path_count"),
    [
        ({"phy_pair_family": "SSTX"}, 0),
        ({"reverse_polarity": True}, 0),
        ({"extra_positive_peer": True}, 0),
        ({"missing_metadata_pin": "U1.4"}, 0),
        ({"dnp": ("U1",)}, 0),
    ],
)
def test_superspeed_path_boundaries_are_not_promoted_to_findings(
    changes: dict[str, object], expected_path_count: int
) -> None:
    observed = superspeed_peer_netlist(**changes)
    assert usb_peer_reference_reviews(observed) == ()
    report = lint_report(observed)
    assert RULE_ID not in {item.rule_id for item in report.findings}
    coverage = report.usb_peer_reference_coverage
    assert coverage is not None
    assert coverage.supported_data_path_count == expected_path_count
    if changes.get("dnp"):
        assert coverage.dnp_group_count == 1
    if changes.get("missing_metadata_pin"):
        assert coverage.incomplete_group_count == 1


def test_superspeed_pair_result_is_stable_under_input_mapping_order() -> None:
    observed = superspeed_peer_netlist()
    permuted = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )
    first = lint_report(observed)
    second = lint_report(permuted)
    assert first.findings == second.findings
    assert first.usb_peer_reference_coverage == second.usb_peer_reference_coverage

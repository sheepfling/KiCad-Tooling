"""Bounded USB SuperSpeed connector-to-PHY reference review regressions."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import text_report
from kicad_tooling.hwrepo.models import ComponentContract, DesignLintRuleOverride
from kicad_tooling.hwrepo.reference_bond_models import ReferenceBondRequirement
from kicad_tooling.hwrepo.usb_peer_reference_review import usb_peer_reference_reviews
from kicad_tooling.hwrepo.usb_superspeed_reference_models import (
    UsbSuperspeedReferencePathRequirement,
)
from tests.usb_peer_reference_support import PATH_RULE_ID, RULE_ID, lint_report, usb_data_map
from tests.usb_peer_superspeed_support import (
    SuperspeedPeerNetlistOverrides,
    superspeed_peer_netlist,
    superspeed_reference_bond,
    superspeed_reference_map,
)

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


def test_reference_net_component_evidence_covers_superspeed_review() -> None:
    base = superspeed_peer_netlist()
    observed = base.model_copy(
        update={
            "components": {
                **base.components,
                "JP1": ComponentContract(value="0R", footprint="Synthetic:SJ2"),
            },
            "nets": {
                **base.nets,
                "USB_GND": ("J1.3", "JP1.1"),
                "BOARD_GND": ("U1.3", "JP1.2"),
            },
            "component_symbols": {
                **base.component_symbols,
                "JP1": "Jumper:SolderJumper_2_Open",
            },
            "pin_functions": {
                **base.pin_functions,
                "JP1.1": "PAD_A",
                "JP1.2": "PAD_B",
            },
            "pin_electrical_types": {
                **base.pin_electrical_types,
                "JP1.1": "passive",
                "JP1.2": "passive",
            },
            "component_pin_numbers": {
                **base.component_pin_numbers,
                "JP1": ("1", "2"),
            },
        }
    )

    report = lint_report(observed)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    expected_observation = (
        "JP1: Jumper:SolderJumper_2_Open; value=0R; footprint=Synthetic:SJ2; "
        "DNP metadata=not listed; exact normalized schematic-netlist pin assignments: "
        "JP1.1 (function=PAD_A, type=passive)=USB_GND; "
        "JP1.2 (function=PAD_B, type=passive)=BOARD_GND"
    )
    assert finding.evidence["USB_components_with_pins_on_both_reference_nets"] == (
        expected_observation,
    )

    commoned_nets = {
        name: pins for name, pins in observed.nets.items() if name not in {"USB_GND", "BOARD_GND"}
    }
    commoned_nets["BOARD_GND"] = ("J1.3", "U1.3", "JP1.1", "JP1.2")
    commoned = observed.model_copy(update={"nets": commoned_nets})
    assert RULE_ID not in {item.rule_id for item in lint_report(commoned).findings}


def test_unspecified_vss_phy_return_type_is_supported_for_superspeed_review() -> None:
    base = superspeed_peer_netlist()
    observed = base.model_copy(
        update={
            "pin_functions": {**base.pin_functions, "U1.3": "VSS"},
            "pin_electrical_types": {
                **base.pin_electrical_types,
                "U1.3": "unspecified",
            },
        }
    )

    report = lint_report(observed)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    assert finding.evidence["phy_reference_pin_assignments"] == (
        "U1.3 (VSS, unspecified)=BOARD_GND",
    )


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


def test_exact_separate_superspeed_map_covers_the_review_and_mismatch_check() -> None:
    observed = superspeed_peer_netlist()
    report = lint_report(observed, path_map=superspeed_reference_map())

    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert PATH_RULE_ID not in {item.rule_id for item in report.findings}
    coverage = report.usb_peer_reference_coverage
    assert coverage is not None
    assert coverage.mapped_separate_reference_path_count == 1
    assert coverage.separate_reference_path_count == 1
    assert coverage.candidate_group_count == 0
    usb_map_coverage = next(
        item for item in report.mapped_check_runs if item.rule_id == PATH_RULE_ID
    )
    assert usb_map_coverage.requirement_count == 1


def test_stale_superspeed_reference_map_reports_mismatch_and_keeps_review() -> None:
    observed = superspeed_peer_netlist()
    path_map = superspeed_reference_map(policy="common_net", phy_reference_net="USB_GND")
    report = lint_report(observed, path_map=path_map)

    findings = {item.rule_id: item for item in report.findings}
    assert RULE_ID in findings
    assert PATH_RULE_ID in findings
    mismatch = findings[PATH_RULE_ID]
    assert mismatch.evidence["line"] == ("reference",)
    assert "reference pins or nets differ from the map" in " ".join(mismatch.evidence["issues"])


@pytest.mark.parametrize(
    ("field", "value", "expected_issue"),
    [
        ("positive_net", "STALE_SS_LANE", "positive or negative pin/net assignments"),
        ("expected_connector_footprint", "Synthetic:Wrong-USB", "identity differs"),
    ],
)
def test_stale_superspeed_pin_net_or_identity_map_is_reported(
    field: str, value: str, expected_issue: str
) -> None:
    path_map = superspeed_reference_map()
    interface = path_map.superspeed_interfaces[0]
    stale_interface = interface.model_copy(update={field: value})
    stale_map = path_map.model_copy(update={"superspeed_interfaces": (stale_interface,)})

    report = lint_report(superspeed_peer_netlist(), path_map=stale_map)
    findings = {item.rule_id: item for item in report.findings}
    assert RULE_ID in findings
    assert PATH_RULE_ID in findings
    assert expected_issue in " ".join(findings[PATH_RULE_ID].evidence["issues"])


def test_stale_superspeed_reference_pin_map_is_reported() -> None:
    path_map = superspeed_reference_map()
    interface = path_map.superspeed_interfaces[0]
    stale_interface = interface.model_copy(
        update={
            "connector_reference_pins": (
                interface.connector_reference_pins[0].model_copy(update={"net": "STALE_GND"}),
            )
        }
    )
    report = lint_report(
        superspeed_peer_netlist(),
        path_map=path_map.model_copy(update={"superspeed_interfaces": (stale_interface,)}),
    )
    mismatch = next(item for item in report.findings if item.rule_id == PATH_RULE_ID)
    assert "reference pins or nets differ from the map" in " ".join(mismatch.evidence["issues"])


def test_full_duplex_superspeed_map_covers_both_exact_directions() -> None:
    observed = superspeed_peer_netlist(full_duplex=True)
    path_map = superspeed_reference_map(full_duplex=True)
    report = lint_report(observed, path_map=path_map)

    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert PATH_RULE_ID not in {item.rule_id for item in report.findings}
    coverage = report.usb_peer_reference_coverage
    assert coverage is not None
    assert coverage.supported_data_path_count == 2
    assert coverage.mapped_separate_reference_path_count == 2


def test_exact_bonded_superspeed_map_is_checked_and_covers_the_review() -> None:
    path_map = superspeed_reference_map(
        policy="bonded",
        reference_bond=superspeed_reference_bond(),
    )
    report = lint_report(superspeed_peer_netlist(bond_value="0R"), path_map=path_map)

    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert PATH_RULE_ID not in {item.rule_id for item in report.findings}
    assert report.usb_peer_reference_coverage.mapped_separate_reference_path_count == 1


@pytest.mark.parametrize("bond_value", [None, "10R"])
def test_bonded_superspeed_map_reports_absent_or_wrong_bond(
    bond_value: str | None,
) -> None:
    path_map = superspeed_reference_map(
        policy="bonded",
        reference_bond=superspeed_reference_bond(),
    )
    report = lint_report(superspeed_peer_netlist(bond_value=bond_value), path_map=path_map)

    assert RULE_ID not in {item.rule_id for item in report.findings}
    mismatch = next(item for item in report.findings if item.rule_id == PATH_RULE_ID)
    assert "R3" in " ".join(mismatch.evidence["issues"])


def test_superspeed_reference_models_reject_invalid_path_and_duplicate_ids() -> None:
    path_map = superspeed_reference_map(full_duplex=True)
    first, second = path_map.superspeed_interfaces
    with pytest.raises(ValidationError, match="distinct nets"):
        UsbSuperspeedReferencePathRequirement.model_validate(
            {**first.model_dump(), "negative_net": first.positive_net}
        )
    with pytest.raises(ValidationError, match="reference-pin requirements must be unique"):
        UsbSuperspeedReferencePathRequirement.model_validate(
            {
                **first.model_dump(),
                "connector_reference_pins": (
                    *first.connector_reference_pins,
                    first.connector_reference_pins[0].model_dump(),
                ),
            }
        )

    with pytest.raises(ValidationError, match="IDs must be unique"):
        type(path_map).model_validate(
            {
                **path_map.model_dump(),
                "superspeed_interfaces": (
                    first.model_dump(),
                    {**second.model_dump(), "id": first.id},
                ),
            }
        )


@pytest.mark.parametrize(
    ("policy", "connector_net", "phy_net", "bond", "message"),
    [
        ("common_net", "USB_GND", "BOARD_GND", None, "share one declared net"),
        ("separate_nets", "BOARD_GND", "BOARD_GND", None, "needs distinct nets"),
        ("bonded", "USB_GND", "BOARD_GND", None, "needs one exact bond component"),
    ],
)
def test_superspeed_map_requires_a_consistent_explicit_reference_decision(
    policy: Literal["common_net", "separate_nets", "bonded"],
    connector_net: str,
    phy_net: str,
    bond: ReferenceBondRequirement | None,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        superspeed_reference_map(
            policy=policy,
            connector_reference_net=connector_net,
            phy_reference_net=phy_net,
            reference_bond=bond,
        )


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
    changes: SuperspeedPeerNetlistOverrides, expected_path_count: int
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

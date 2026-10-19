"""Focused USB connector-to-PHY reference lint regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import text_report
from kicad_tooling.hwrepo.models import ComponentContract
from kicad_tooling.hwrepo.usb_data_paths import usb_data_path_mismatches
from kicad_tooling.hwrepo.usb_peer_reference_review import usb_peer_reference_reviews
from tests.usb_c_peer_support import (
    usb_c_peer_netlist,
)
from tests.usb_peer_inline_path_support import usb_inline_peer_case
from tests.usb_peer_reference_support import (
    PATH_RULE_ID,
    RULE_ID,
    lint_report,
    usb_peer_netlist,
    usb_peer_series_netlist,
    usb_series_data_map,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_split_reference_direct_usb_pair_emits_exact_review_evidence() -> None:
    observed = usb_peer_netlist()
    reviews = usb_peer_reference_reviews(observed)
    assert (len(reviews)) == (1)
    review = reviews[0]
    assert ((review.connector_reference, review.phy_reference)) == (("J1", "U1"))
    assert (review.connector_reference_net) == ("USB_GND")
    assert (review.phy_reference_net) == ("BOARD_GND")
    assert (tuple(item.pin for item in review.connector_reference_pins)) == (("J1.3",))
    assert (tuple(item.pin for item in review.phy_reference_pins)) == (("U1.3",))
    report = lint_report(observed)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert (report.status) == ("REVIEW")
    assert (finding.subject) == ("J1 / U1: USB reference-domain review")
    assert (finding.evidence["USB_D+_link"]) == (("J1.1 / U1.1=USB_DP",))
    assert (finding.evidence["USB_D-_link"]) == (("J1.2 / U1.2=USB_DM",))


def test_common_reference_is_a_quiet_control() -> None:
    observed = usb_peer_netlist(connector_reference_net="BOARD_GND", phy_reference_net="BOARD_GND")
    assert (usb_peer_reference_reviews(observed)) == (())
    assert (RULE_ID) not in ({item.rule_id for item in lint_report(observed).findings})


def test_fitted_series_resistors_preserve_usb_peer_reference_review() -> None:
    observed = usb_peer_series_netlist()
    reviews = usb_peer_reference_reviews(observed)
    assert (len(reviews)) == (1)
    link = reviews[0].data_link
    assert (link.connector_positive_net) == ("USB_DP")
    assert (link.phy_positive_net) == ("USB_DP_PHY")
    assert (link.connector_negative_net) == ("USB_DM")
    assert (link.phy_negative_net) == ("USB_DM_PHY")
    assert (link.positive_series_resistor.reference) == ("R1")
    assert (link.positive_series_resistor.connector_pin) == ("R1.1")
    assert (link.positive_series_resistor.phy_pin) == ("R1.2")
    assert (link.negative_series_resistor.reference) == ("R2")

    path = lint_report(observed).usb_peer_reference_coverage.path_entries[0]
    assert (path.data_path.positive.series_resistor.reference) == ("R1")
    assert (path.data_path.positive.series_resistor.connector_net) == "USB_DP"
    assert (path.data_path.positive.series_resistor.phy_net) == "USB_DP_PHY"
    assert (path.data_path.negative.series_resistor.reference) == "R2"

    report = lint_report(observed)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert (finding.evidence["USB_D+_link"]) == (("J1.1 / U1.1=USB_DP to USB_DP_PHY through R1",))
    assert (finding.evidence["USB_D+_series_resistor"]) == (
        ("R1 (Device:R, 27R; R1.1=USB_DP, R1.2=USB_DP_PHY)",)
    )

    mapped = lint_report(observed, path_map=usb_series_data_map())
    assert (RULE_ID) not in ({item.rule_id for item in mapped.findings})
    assert (PATH_RULE_ID) not in ({item.rule_id for item in mapped.findings})

    stale_map = lint_report(
        observed,
        path_map=usb_series_data_map(positive_resistor="R9"),
    )
    assert (RULE_ID) in ({item.rule_id for item in stale_map.findings})
    assert (PATH_RULE_ID) in ({item.rule_id for item in stale_map.findings})

    common = usb_peer_series_netlist(
        connector_reference_net="BOARD_GND", phy_reference_net="BOARD_GND"
    )
    assert (usb_peer_reference_reviews(common)) == (())
    assert (RULE_ID) not in ({item.rule_id for item in lint_report(common).findings})


def test_exact_mapped_inline_component_path_reviews_split_references() -> None:
    observed, path_map = usb_inline_peer_case()
    assert path_map.interfaces[0].inline_component.pins[4].net == "BOARD_GND"
    mismatches = usb_data_path_mismatches(path_map, observed)
    assert not mismatches, tuple((item.line, item.issues) for item in mismatches)
    report = lint_report(observed, path_map=path_map)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert len(findings) == 1
    assert PATH_RULE_ID not in {item.rule_id for item in report.findings}
    assert findings[0].evidence["USB_D+_link"] == (
        "J1.1 / U1.1=USB_DP_PORT to USB_DP_PHY through mapped inline component U2",
    )
    assert findings[0].evidence["USB_inline_component"] == (
        "U2 (Synthetic:UsbProtection; Synthetic:QFN)",
    )
    assert findings[0].evidence["USB_reference_policy_state"] == ("not_configured",)
    assert "U2.5=BOARD_GND" in findings[0].evidence["USB_inline_component_pin_assignments"]
    path = report.usb_peer_reference_coverage.path_entries[0]
    assert path.data_path.positive.inline_component.reference == "U2"
    assert path.data_path.positive.inline_component.connector_pin == "U2.1"
    assert path.data_path.negative.inline_component.connector_pin == "U2.3"
    assert "via U2.1 -> U2.2 (U2, mapped inline component)" in text_report(report)

    shunted_observed, shunted_map = usb_inline_peer_case(data_shunt=True)
    shunted_report = lint_report(shunted_observed, path_map=shunted_map)
    shunted_finding = next(item for item in shunted_report.findings if item.rule_id == RULE_ID)
    assert shunted_finding.evidence["USB_D+_shunt_branches"] == (
        "D1.2 (Synthetic:TVS) to D1.1=USB_GND",
    )

    named_inline_observed, named_inline_map = usb_inline_peer_case(inline_has_usb_names=True)
    named_inline_report = lint_report(named_inline_observed, path_map=named_inline_map)
    named_inline_findings = tuple(
        item for item in named_inline_report.findings if item.rule_id == RULE_ID
    )
    assert tuple(item.subject for item in named_inline_findings) == (
        "J1 / U1: USB reference-domain review (port 1)",
    )

    separate_observed, separate_map = usb_inline_peer_case(reference_policy="separate_nets")
    separate_report = lint_report(separate_observed, path_map=separate_map)
    assert RULE_ID not in {item.rule_id for item in separate_report.findings}
    assert separate_report.usb_peer_reference_coverage.mapped_separate_reference_path_count == 1

    common_observed, common_map = usb_inline_peer_case(reference_policy="common_net")
    common_report = lint_report(common_observed, path_map=common_map)
    assert RULE_ID not in {item.rule_id for item in common_report.findings}
    assert common_report.usb_peer_reference_coverage.common_reference_path_count == 1

    unmapped_report = lint_report(observed)
    assert RULE_ID not in {item.rule_id for item in unmapped_report.findings}
    assert unmapped_report.usb_peer_reference_coverage.supported_data_path_count == 0
    unsupported = unmapped_report.usb_peer_reference_coverage.unsupported_multi_pin_paths
    assert unsupported is not None
    assert len(unsupported) == 1
    assert (
        unsupported[0].connector_reference,
        unsupported[0].phy_reference,
        unsupported[0].component_reference,
        unsupported[0].component_pin_count,
    ) == ("J1", "U1", "U2", 6)
    assert unsupported[0].positive_connector_net == "USB_DP_PORT"
    assert unsupported[0].positive_phy_net == "USB_DP_PHY"
    assert unsupported[0].positive_connector_component_pins == ("U2.1",)
    assert unsupported[0].positive_phy_component_pins == ("U2.2",)
    assert unsupported[0].negative_connector_net == "USB_DM_PORT"
    assert unsupported[0].negative_phy_net == "USB_DM_PHY"
    assert unsupported[0].negative_connector_component_pins == ("U2.3",)
    assert unsupported[0].negative_phy_component_pins == ("U2.4",)
    reordered = observed.model_copy(update={"nets": dict(reversed(tuple(observed.nets.items())))})
    reordered_coverage = lint_report(reordered).usb_peer_reference_coverage
    assert reordered_coverage.unsupported_multi_pin_paths == unsupported
    assert (
        "Unsupported multi-pin topology candidates (coverage only; not a confirmed path or defect):"
        in text_report(unmapped_report)
    )
    assert "An exact project-authored data-path map is required" in text_report(unmapped_report)

    assert report.usb_peer_reference_coverage.unsupported_multi_pin_paths == ()

    peer_observed, peer_map = usb_inline_peer_case(extra_data_peer=True)
    peer_report = lint_report(peer_observed, path_map=peer_map)
    assert RULE_ID not in {item.rule_id for item in peer_report.findings}
    assert peer_report.usb_peer_reference_coverage.supported_data_path_count == 0
    assert peer_report.usb_peer_reference_coverage.unsupported_multi_pin_paths == ()


def test_series_resistor_recognition_rejects_dnp_incomplete_and_extra_peers() -> None:
    observed = usb_peer_series_netlist()
    dnp = observed.model_copy(update={"dnp_components": ("R1",)})
    assert (usb_peer_reference_reviews(dnp)) == (())

    incomplete = observed.model_copy(
        update={
            "component_pin_numbers": {
                **observed.component_pin_numbers,
                "R1": ("1", "2", "3"),
            }
        }
    )
    assert (usb_peer_reference_reviews(incomplete)) == (())

    extra_peer = observed.model_copy(
        update={
            "components": {
                **observed.components,
                "TP1": ComponentContract(
                    value="Synthetic test point", footprint="Synthetic:TestPoint"
                ),
            },
            "component_symbols": {**observed.component_symbols, "TP1": "Connector:TestPoint"},
            "component_pin_numbers": {
                **observed.component_pin_numbers,
                "TP1": ("1",),
            },
            "pin_functions": {**observed.pin_functions, "TP1.1": "TestPoint"},
            "pin_electrical_types": {
                **observed.pin_electrical_types,
                "TP1.1": "passive",
            },
            "nets": {
                **observed.nets,
                "USB_DP": (*observed.nets["USB_DP"], "TP1.1"),
            },
        }
    )
    assert (usb_peer_reference_reviews(extra_peer)) == (())


def test_usb_c_duplicate_contacts_and_two_pin_diode_shunts_emit_exact_review() -> None:
    observed = usb_c_peer_netlist()
    reviews = usb_peer_reference_reviews(observed)
    assert (len(reviews)) == (1)
    link = reviews[0].data_link
    assert (link.connector_positive_pins) == (("J1.A6", "J1.B6"))
    assert (link.connector_negative_pins) == (("J1.A7", "J1.B7"))
    assert (link.phy_positive_pins) == (("U1.1",))
    assert (link.phy_negative_pins) == (("U1.2",))
    assert (
        (
            link.positive_shunt_branches[0].data_pin,
            link.positive_shunt_branches[0].reference_pin,
        )
    ) == (("D1.2", "D1.1"))
    report = lint_report(observed)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert (finding.evidence["USB_D+_link"]) == (("J1.A6, J1.B6 / U1.1=USB_DP",))
    assert (finding.evidence["USB_D+_shunt_branches"]) == (
        ("D1.2 (Synthetic:TVS) to D1.1=USB_GND",)
    )


def test_usb_c_common_reference_with_duplicate_contacts_and_diodes_is_control() -> None:
    observed = usb_c_peer_netlist(
        connector_reference_net="BOARD_GND", phy_reference_net="BOARD_GND"
    )
    assert (usb_peer_reference_reviews(observed)) == (())
    assert (RULE_ID) not in ({item.rule_id for item in lint_report(observed).findings})


def test_usb_c_does_not_accept_extra_peers_incomplete_or_non_diode_branches() -> None:
    base = usb_c_peer_netlist()
    extra_peer = base.model_copy(
        update={
            "components": {
                **base.components,
                "TP1": ComponentContract(
                    value="Synthetic test point", footprint="Synthetic:TestPoint"
                ),
            },
            "component_symbols": {**base.component_symbols, "TP1": "Connector:TestPoint"},
            "component_pin_numbers": {**base.component_pin_numbers, "TP1": ("1",)},
            "pin_functions": {**base.pin_functions, "TP1.1": "TestPoint"},
            "pin_electrical_types": {**base.pin_electrical_types, "TP1.1": "passive"},
            "nets": {
                **base.nets,
                "USB_DP": (*base.nets["USB_DP"], "TP1.1"),
            },
        }
    )
    assert (usb_peer_reference_reviews(extra_peer)) == (())

    resistor_branch = base.model_copy(
        update={
            "components": {
                **base.components,
                "R1": ComponentContract(value="Synthetic resistor", footprint="Synthetic:0603"),
            },
            "component_symbols": {**base.component_symbols, "R1": "Device:R"},
            "component_pin_numbers": {**base.component_pin_numbers, "R1": ("1", "2")},
            "pin_functions": {**base.pin_functions, "R1.1": "~", "R1.2": "~"},
            "pin_electrical_types": {
                **base.pin_electrical_types,
                "R1.1": "passive",
                "R1.2": "passive",
            },
            "nets": {
                **base.nets,
                "USB_DP": (*base.nets["USB_DP"], "R1.2"),
                "USB_GND": (*base.nets["USB_GND"], "R1.1"),
            },
        }
    )
    assert (usb_peer_reference_reviews(resistor_branch)) == (())

    incomplete_diode = base.model_copy(
        update={
            "component_pin_numbers": {
                **base.component_pin_numbers,
                "D1": ("1", "2", "3"),
            }
        }
    )
    assert (usb_peer_reference_reviews(incomplete_diode)) == (())

    split_contacts = base.model_copy(
        update={
            "nets": {
                **base.nets,
                "USB_DP": ("J1.A6", "U1.1", "D1.2"),
                "USB_DP_B": ("J1.B6",),
            }
        }
    )
    assert (usb_peer_reference_reviews(split_contacts)) == (())

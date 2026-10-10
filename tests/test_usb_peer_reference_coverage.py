"""Focused USB connector-to-PHY reference lint regressions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.bus_heuristics import usb_data_function_identity, usb_data_function_side
from kicad_tooling.hwrepo.design_lint import text_report
from kicad_tooling.hwrepo.models import (
    NetlistContract,
    UsbPeerReferenceCoverageReport,
)
from kicad_tooling.hwrepo.usb_peer_reference_review import (
    scan_usb_peer_reference_reviews,
    usb_peer_reference_reviews,
)
from tests.usb_peer_reference_support import (
    PATH_RULE_ID,
    RULE_ID,
    lint_report,
    usb_data_map,
    usb_multiport_data_map,
    usb_multiport_peer_netlist,
    usb_peer_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_coverage_binds_common_split_and_mapped_peer_paths() -> None:
    split = lint_report(usb_peer_netlist())
    split_coverage = split.usb_peer_reference_coverage
    assert (split_coverage) is not None
    assert split_coverage is not None
    assert (split_coverage.status) == ("EVALUATED")
    assert (split_coverage.netlist_sha256) == (split.netlist_sha256)
    assert (split_coverage.recognized_connector_group_count) == (1)
    assert (split_coverage.supported_connector_group_count) == (1)
    assert (split_coverage.recognized_phy_group_count) == (1)
    assert (split_coverage.supported_phy_group_count) == (1)
    assert (split_coverage.supported_data_path_count) == (1)
    assert (split_coverage.separate_reference_path_count) == (1)
    assert (split_coverage.candidate_group_count) == (1)
    split_path = split_coverage.path_entries[0]
    assert (split_path.connector_reference, split_path.phy_reference) == ("J1", "U1")
    assert (split_path.reference_disposition) == ("SEPARATE_REFERENCE_REVIEW")
    assert (split_path.connector_reference_net, split_path.phy_reference_net) == (
        "USB_GND",
        "BOARD_GND",
    )
    assert tuple(item.pin for item in split_path.connector_reference_pins) == ("J1.3",)
    assert tuple(item.pin for item in split_path.phy_reference_pins) == ("U1.3",)
    assert (split_path.data_path.positive.connector_pins) == ("J1.1",)
    assert (split_path.data_path.positive.phy_pins) == ("U1.1",)
    assert (split_path.data_path.positive.connector_net) == "USB_DP"
    assert (split_path.data_path.negative.connector_net) == "USB_DM"
    assert ("USB peer-reference heuristic coverage:") in (text_report(split))
    assert ("At least one supported connector-to-PHY path was checked.") in (text_report(split))
    assert ("J1 -> U1 (unnumbered port): SEPARATE_REFERENCE_REVIEW") in (text_report(split))

    common = lint_report(
        usb_peer_netlist(connector_reference_net="BOARD_GND", phy_reference_net="BOARD_GND")
    )
    common_coverage = common.usb_peer_reference_coverage
    assert (common_coverage) is not None
    assert common_coverage is not None
    assert (common_coverage.common_reference_path_count) == (1)
    assert (common_coverage.separate_reference_path_count) == (0)
    assert (common_coverage.candidate_group_count) == (0)
    assert (common_coverage.path_entries[0].reference_disposition) == ("COMMON_REFERENCE")
    assert (
        common_coverage.path_entries[0].connector_reference_net
        == common_coverage.path_entries[0].phy_reference_net
    )

    mapped = lint_report(
        usb_peer_netlist(), path_map=usb_data_map(reference_policy="separate_nets")
    )
    mapped_coverage = mapped.usb_peer_reference_coverage
    assert (mapped_coverage) is not None
    assert mapped_coverage is not None
    assert (mapped_coverage.usb_data_path_map_sha256) is not None
    assert (mapped_coverage.mapped_separate_reference_path_count) == (1)
    assert (mapped_coverage.candidate_group_count) == (0)
    assert mapped_coverage.path_entries[0].reference_disposition == "MAP_COVERED_SEPARATE_REFERENCE"


def test_coverage_marks_missing_usb_endpoints_and_incomplete_groups() -> None:
    empty = NetlistContract(components={}, nets={})
    empty_scan = scan_usb_peer_reference_reviews(empty)
    assert (empty_scan.coverage.recognized_connector_group_count) == (0)
    assert (empty_scan.coverage.recognized_phy_group_count) == (0)
    empty_coverage = lint_report(empty).usb_peer_reference_coverage
    assert (empty_coverage) is not None
    assert empty_coverage is not None
    assert (empty_coverage.status) == ("NO_USB_ENDPOINTS")
    assert (empty_coverage.path_entries) == ()
    assert ("No supported USB data-pin function groups were recognized") in (
        text_report(lint_report(empty))
    )

    incomplete = usb_peer_netlist(incomplete=True)
    incomplete_coverage = lint_report(incomplete).usb_peer_reference_coverage
    assert (incomplete_coverage) is not None
    assert incomplete_coverage is not None
    assert (incomplete_coverage.status) == ("INCOMPLETE")
    assert (incomplete_coverage.incomplete_group_count) == (1)
    assert (incomplete_coverage.path_entries) == ()
    assert (
        tuple(
            (item.endpoint_role, item.reference, item.port_group, item.disposition)
            for item in incomplete_coverage.endpoint_groups or ()
        )
    ) == (
        (
            ("connector", "J1", None, "SUPPORTED"),
            ("phy", "U1", None, "INCOMPLETE"),
        )
    )
    incomplete_text = text_report(lint_report(incomplete))
    assert ("lacked complete evidence") in (incomplete_text)
    assert ("PHY U1 (unnumbered port): INCOMPLETE") in (incomplete_text)

    legacy_payload = incomplete_coverage.model_dump()
    legacy_payload.pop("endpoint_groups")
    legacy_payload.pop("path_entries")
    legacy = UsbPeerReferenceCoverageReport.model_validate(legacy_payload)
    assert (legacy.endpoint_groups) is None
    assert (legacy.path_entries) is None
    inconsistent_payload = incomplete_coverage.model_dump()
    inconsistent_payload["incomplete_group_count"] = 0
    with pytest.raises(ValidationError, match="incomplete group count"):
        UsbPeerReferenceCoverageReport.model_validate(inconsistent_payload)
    inconsistent_paths = incomplete_coverage.model_dump(mode="python")
    inconsistent_paths["supported_data_path_count"] = 1
    with pytest.raises(ValidationError, match="path coverage entries"):
        UsbPeerReferenceCoverageReport.model_validate(inconsistent_paths)


def test_coverage_distinguishes_unsupported_paths_and_dnp_endpoints() -> None:
    observed = usb_peer_netlist()
    uncoupled = observed.model_copy(
        update={
            "nets": {
                **observed.nets,
                "USB_DP": ("J1.1",),
                "USB_DP_PHY": ("U1.1",),
            }
        }
    )
    uncoupled_coverage = lint_report(uncoupled).usb_peer_reference_coverage
    assert (uncoupled_coverage) is not None
    assert uncoupled_coverage is not None
    assert (uncoupled_coverage.status) == ("NO_SUPPORTED_PEER_PATHS")
    assert (uncoupled_coverage.supported_connector_group_count) == (1)
    assert (uncoupled_coverage.supported_phy_group_count) == (1)
    assert (uncoupled_coverage.incomplete_group_count) == (0)
    assert (uncoupled_coverage.supported_data_path_count) == (0)
    assert (uncoupled_coverage.path_entries) == ()
    assert ("No direct or single-resistor USB D+/D− connector-to-PHY path matched") in (
        text_report(lint_report(uncoupled))
    )

    dnp_coverage = lint_report(usb_peer_netlist(dnp=("U1",))).usb_peer_reference_coverage
    assert (dnp_coverage) is not None
    assert dnp_coverage is not None
    assert (dnp_coverage.status) == ("NO_SUPPORTED_PEER_PATHS")
    assert (dnp_coverage.dnp_group_count) == (1)
    assert (dnp_coverage.incomplete_group_count) == (0)
    assert (dnp_coverage.supported_phy_group_count) == (0)
    assert (dnp_coverage.path_entries) == ()
    assert (
        tuple(
            (item.endpoint_role, item.reference, item.port_group, item.disposition)
            for item in dnp_coverage.endpoint_groups or ()
        )
    ) == (
        (
            ("connector", "J1", None, "SUPPORTED"),
            ("phy", "U1", None, "DNP"),
        )
    )


def test_single_port_numbered_usb_data_functions_are_recognized() -> None:
    assert (usb_data_function_side("DP1")) == ("positive")
    assert (usb_data_function_side("DM1")) == ("negative")
    assert (usb_data_function_side("DP2")) == ("positive")
    assert (usb_data_function_side("DM2")) == ("negative")
    assert (usb_data_function_identity("USB_DP3")) == (("3", "positive"))
    assert (usb_data_function_identity("DP2")) == (("2", "positive"))
    assert (usb_data_function_identity("USB1D+")) == (("1", "positive"))
    assert (usb_data_function_identity("USB2D-")) == (("2", "negative"))
    assert (usb_data_function_identity("USB0D+")) == (None)
    assert (usb_data_function_identity("1D+")) == (None)
    assert (usb_data_function_identity("D-")) == ((None, "negative"))


@pytest.mark.parametrize(
    ("function", "expected_identity"),
    (("UD+", (None, "positive")), ("UD-", (None, "negative"))),
)
def test_ud_pin_function_aliases_are_recognized_as_usb_data(
    function: str, expected_identity: tuple[str | None, str]
) -> None:
    assert usb_data_function_identity(function) == expected_identity


def test_ud_phy_aliases_retain_split_fault_and_common_reference_control() -> None:
    split = lint_report(usb_peer_netlist(phy_positive_function="UD+", phy_negative_function="UD-"))
    split_coverage = split.usb_peer_reference_coverage
    assert split_coverage is not None
    assert split_coverage.recognized_phy_group_count == 1
    assert split_coverage.supported_phy_group_count == 1
    assert split_coverage.supported_data_path_count == 1
    assert split_coverage.separate_reference_path_count == 1
    assert split_coverage.path_entries[0].reference_disposition == "SEPARATE_REFERENCE_REVIEW"
    assert sum(item.rule_id == RULE_ID for item in split.findings) == 1

    common = lint_report(
        usb_peer_netlist(
            connector_reference_net="BOARD_GND",
            phy_reference_net="BOARD_GND",
            phy_positive_function="UD+",
            phy_negative_function="UD-",
        )
    )
    common_coverage = common.usb_peer_reference_coverage
    assert common_coverage is not None
    assert common_coverage.common_reference_path_count == 1
    assert common_coverage.separate_reference_path_count == 0
    assert RULE_ID not in {item.rule_id for item in common.findings}


def test_numbered_multiport_hub_groups_each_connector_with_its_usb_port() -> None:
    observed = usb_multiport_peer_netlist()
    reviews = usb_peer_reference_reviews(observed)
    assert (
        tuple(
            (
                item.connector_reference,
                item.phy_reference,
                item.data_link.port_group,
                item.data_link.phy_positive_pins,
                item.data_link.phy_negative_pins,
            )
            for item in reviews
        )
    ) == (
        (
            ("J1", "U1", "1", ("U1.1",), ("U1.2",)),
            ("J2", "U1", "2", ("U1.4",), ("U1.5",)),
        )
    )
    report = lint_report(observed)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    coverage = report.usb_peer_reference_coverage
    assert (coverage) is not None
    assert coverage is not None
    assert (
        tuple(
            (item.endpoint_role, item.reference, item.port_group, item.disposition)
            for item in coverage.endpoint_groups or ()
        )
    ) == (
        (
            ("connector", "J1", None, "SUPPORTED"),
            ("connector", "J2", None, "SUPPORTED"),
            ("phy", "U1", "1", "SUPPORTED"),
            ("phy", "U1", "2", "SUPPORTED"),
        )
    )
    assert (report.status) == ("REVIEW")
    assert tuple(
        (
            item.connector_reference,
            item.phy_reference,
            item.data_path.port_group,
            item.reference_disposition,
            item.connector_reference_net,
            item.phy_reference_net,
        )
        for item in coverage.path_entries
    ) == (
        (
            ("J1", "U1", "1", "SEPARATE_REFERENCE_REVIEW", "USB1_GND", "PHY_GND"),
            ("J2", "U1", "2", "SEPARATE_REFERENCE_REVIEW", "USB2_GND", "PHY_GND"),
        )
    )
    assert tuple(
        tuple(item.pin for item in path.phy_reference_pins) for path in coverage.path_entries
    ) == (("U1.3", "U1.6"), ("U1.3", "U1.6"))
    assert (tuple((item.subject, item.evidence["USB_port_group"]) for item in findings)) == (
        (
            ("J1 / U1: USB reference-domain review (port 1)", ("1",)),
            ("J2 / U1: USB reference-domain review (port 2)", ("2",)),
        )
    )
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )
    assert (lint_report(observed)) == (lint_report(reordered))

    common = usb_multiport_peer_netlist(common_references=True)
    assert (usb_peer_reference_reviews(common)) == (())
    common_report = lint_report(common)
    assert (RULE_ID) not in ({item.rule_id for item in common_report.findings})
    assert tuple(
        item.reference_disposition
        for item in common_report.usb_peer_reference_coverage.path_entries
    ) == (
        "COMMON_REFERENCE",
        "COMMON_REFERENCE",
    )

    exact_map = usb_multiport_data_map()
    mapped = lint_report(observed, path_map=exact_map)
    assert (RULE_ID) not in ({item.rule_id for item in mapped.findings})
    assert (PATH_RULE_ID) not in ({item.rule_id for item in mapped.findings})
    assert tuple(
        item.reference_disposition for item in mapped.usb_peer_reference_coverage.path_entries
    ) == (
        "MAP_COVERED_SEPARATE_REFERENCE",
        "MAP_COVERED_SEPARATE_REFERENCE",
    )

    stale_map = lint_report(
        observed,
        path_map=usb_multiport_data_map(second_port_group="3"),
    )
    stale_peer_findings = tuple(item for item in stale_map.findings if item.rule_id == RULE_ID)
    assert (tuple(item.subject for item in stale_peer_findings)) == (
        ("J2 / U1: USB reference-domain review (port 2)",)
    )
    assert tuple(
        item.reference_disposition for item in stale_map.usb_peer_reference_coverage.path_entries
    ) == (
        "MAP_COVERED_SEPARATE_REFERENCE",
        "SEPARATE_REFERENCE_REVIEW",
    )
    assert (PATH_RULE_ID) in ({item.rule_id for item in stale_map.findings})


def test_numbered_multiport_pairing_rejects_crossed_and_incomplete_channels() -> None:
    observed = usb_multiport_peer_netlist()
    crossed = observed.model_copy(
        update={
            "nets": {
                **observed.nets,
                "USB1_DM": ("J1.2", "U1.5"),
                "USB2_DM": ("J2.2", "U1.2"),
            }
        }
    )
    assert (usb_peer_reference_reviews(crossed)) == (())

    one_channel_open = observed.model_copy(
        update={
            "nets": {
                name: tuple(pin for pin in pins if pin != "U1.5")
                for name, pins in observed.nets.items()
            }
        }
    )
    reviews = usb_peer_reference_reviews(one_channel_open)
    assert (tuple((item.connector_reference, item.data_link.port_group) for item in reviews)) == (
        (("J1", "1"),)
    )

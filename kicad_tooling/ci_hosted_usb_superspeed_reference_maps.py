"""Pinned native acceptance for exact USB SuperSpeed reference maps."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .hwrepo.usb_data_path_models import UsbDataPathMap
from .hwrepo.usb_reference_pin_models import UsbReferencePinRequirement
from .hwrepo.usb_superspeed_reference_models import UsbSuperspeedReferencePathRequirement
from .validate import read_netlist

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

_SignalFamily = Literal["USB SuperSpeed TX", "USB SuperSpeed RX"]


def _reference_map(case: Literal["fault", "control"]) -> UsbDataPathMap:
    connector_reference_net, phy_reference_net, reference_policy = (
        ("USB_GND", "PHY_GND", "separate_nets")
        if case == "fault"
        else ("BOARD_GND", "BOARD_GND", "common_net")
    )
    pairs: tuple[tuple[str, _SignalFamily, _SignalFamily, str, str, str, str, str, str], ...] = (
        (
            "ss-tx-to-rx",
            "USB SuperSpeed TX",
            "USB SuperSpeed RX",
            "J1.1",
            "U1.1",
            "SS_TX_P",
            "J1.2",
            "U1.2",
            "SS_TX_N",
        ),
        (
            "ss-rx-to-tx",
            "USB SuperSpeed RX",
            "USB SuperSpeed TX",
            "J1.3",
            "U1.3",
            "SS_RX_P",
            "J1.4",
            "U1.4",
            "SS_RX_N",
        ),
    )
    return UsbDataPathMap(
        basis="Synthetic native USB SuperSpeed reference-map control",
        superspeed_interfaces=tuple(
            UsbSuperspeedReferencePathRequirement(
                id=interface_id,
                basis="Synthetic connector and PHY pin map",
                connector_reference="J1",
                expected_connector_symbol="Synthetic:UsbSuperSpeedConnector",
                expected_connector_footprint="Synthetic:UsbSuperSpeedConnector",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbSuperSpeedPhy",
                expected_phy_footprint="Synthetic:QFN",
                connector_signal_family=connector_family,
                phy_signal_family=phy_family,
                connector_positive_pin=connector_positive,
                phy_positive_pin=phy_positive,
                positive_net=positive_net,
                connector_negative_pin=connector_negative,
                phy_negative_pin=phy_negative,
                negative_net=negative_net,
                connector_reference_pins=(
                    UsbReferencePinRequirement(pin="J1.5", net=connector_reference_net),
                ),
                phy_reference_pins=(UsbReferencePinRequirement(pin="U1.5", net=phy_reference_net),),
                reference_policy=reference_policy,
            )
            for (
                interface_id,
                connector_family,
                phy_family,
                connector_positive,
                phy_positive,
                positive_net,
                connector_negative,
                phy_negative,
                negative_net,
            ) in pairs
        ),
    )


def usb_superspeed_reference_map_fixture_lane(
    *,
    project: str,
    kicad_version: str,
    image: str,
    output: Path,
    source_hashes: dict[str, str],
    normalized_hashes: dict[tuple[str, str], str],
    raw_hashes: dict[tuple[str, str], str],
    log: HostedLog,
) -> None:
    """Verify exact split/common maps and a stale-map fault on native exports."""
    maps = {case: _reference_map(case) for case in ("fault", "control")}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    for case, path_map in maps.items():
        for run in ("first", "repeat"):
            observed = read_netlist(output / f"{case}.{run}.netlist.xml")
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-usb-superspeed-reference-map-{case}",
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(
                coach.project_id,
                coach,
                DesignLintPolicy(usb_data_path_map=path_map),
            )

    for case, path_map in maps.items():
        first = reports[(case, "first")]
        if first.findings != reports[(case, "repeat")].findings:
            raise ValueError(f"Native USB SuperSpeed {case} mapped findings are not repeatable")
        reference_findings = sum(
            item.rule_id == "bus.usb_peer_reference_review" for item in first.findings
        )
        path_mismatches = sum(
            item.rule_id == "bus.usb_data_path_mismatch" for item in first.findings
        )
        coverage = first.usb_peer_reference_coverage
        if coverage is None:
            raise ValueError(f"Native {case} mapped path did not produce USB coverage")
        if reference_findings or path_mismatches:
            raise ValueError(f"Exact native {case} map produced unexpected USB findings")
        expected_mapped_paths = 2 if case == "fault" else 0
        if coverage.mapped_separate_reference_path_count != expected_mapped_paths:
            raise ValueError(f"Native {case} map did not cover its reference relationships")
        requirement_count = next(
            item.requirement_count
            for item in first.mapped_check_runs
            if item.rule_id == "bus.usb_data_path_mismatch"
        )
        if requirement_count != 2:
            raise ValueError(f"Native {case} map coverage counted {requirement_count} requirements")

        log.event(
            f"usb-superspeed-peer-reference-fixture/mapped-{case}",
            "PASS",
            project=project,
            kicad_version=kicad_version,
            image=image,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            map_sha256=hashlib.sha256(path_map.model_dump_json().encode("utf-8")).hexdigest(),
            reference_policy=path_map.superspeed_interfaces[0].reference_policy,
            reference_findings=reference_findings,
            path_mismatches=path_mismatches,
            mapped_separate_paths=coverage.mapped_separate_reference_path_count,
            requirement_count=requirement_count,
            repeatable="true",
        )

    stale_map_report = evaluate(
        "synthetic-usb-superspeed-stale-map-control",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-usb-superspeed-stale-map-control",
            observed=read_netlist(output / "control.first.netlist.xml"),
            netlist_sha256=raw_hashes[("control", "first")],
        ),
        DesignLintPolicy(usb_data_path_map=maps["fault"]),
    )
    stale_path_mismatches = sum(
        item.rule_id == "bus.usb_data_path_mismatch" for item in stale_map_report.findings
    )
    stale_reference_findings = sum(
        item.rule_id == "bus.usb_peer_reference_review" for item in stale_map_report.findings
    )
    if stale_path_mismatches != 2 or stale_reference_findings:
        raise ValueError("Stale split-reference map did not report both common-net mismatches")
    log.event(
        "usb-superspeed-peer-reference-fixture/stale-map-control",
        "PASS",
        project=project,
        kicad_version=kicad_version,
        image=image,
        source_sha256=source_hashes["control"],
        normalized_netlist_sha256=normalized_hashes[("control", "first")],
        path_mismatches=stale_path_mismatches,
        reference_findings=stale_reference_findings,
        repeatable="true",
    )

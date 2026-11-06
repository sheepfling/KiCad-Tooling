"""Validate native exact-part evidence for the synthetic storage hold-up contract."""

from __future__ import annotations

import hashlib
import json

from .ci_hosted_component_rating_context import ComponentRatingFixtureContext
from .ci_hosted_support import HostedLog
from .hwrepo.contracts import read_kicad_erc_report
from .hwrepo.energy_storage_hold_up import energy_storage_hold_up_checks
from .hwrepo.energy_storage_models import EnergyStorageAnalysis, EnergyStorageHoldUpRequirement
from .hwrepo.evidence import digest
from .hwrepo.native_report_parsing import read_netlist
from .hwrepo.netlist_contract_models import NetlistContract


def verify_energy_storage_hold_up_fixture(
    context: ComponentRatingFixtureContext, log: HostedLog
) -> None:
    """Compare the synthetic hold-up envelope with repeatable native netlist evidence."""
    fixture = context.energy_storage_fixture
    fixture_sha256 = context.energy_storage_fixture_sha256
    output = context.output
    normalized_netlist_hashes: dict[str, str] = {}
    normalized_erc_hashes: dict[str, str] = {}
    native_erc_types: dict[str, tuple[str, ...]] = {}
    native_erc_error_types: dict[str, tuple[str, ...]] = {}
    parsed: dict[str, NetlistContract] = {}
    for run in ("first", "repeat"):
        netlist_path = output / f"energy-storage.{run}.netlist.xml"
        erc_path = output / f"energy-storage.{run}.erc.json"
        if not netlist_path.is_file() or not erc_path.is_file():
            raise ValueError(
                "Native energy-storage export omitted a repeated netlist or ERC report"
            )
        observed = read_netlist(netlist_path)
        parsed[run] = observed
        normalized_netlist = json.dumps(
            observed.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        normalized_netlist_hashes[run] = hashlib.sha256(normalized_netlist).hexdigest()
        erc_report = read_kicad_erc_report(erc_path)
        if erc_report.kicad_version != context.config.kicad_version:
            raise ValueError(
                "Native energy-storage ERC version differs from the selected toolchain"
            )
        violations = tuple(
            sorted(
                (
                    item.type,
                    item.severity,
                    item.description,
                    tuple(
                        sorted((detail.description, detail.x, detail.y) for detail in item.items)
                    ),
                )
                for item in erc_report.violations
            )
        )
        normalized_erc = json.dumps(
            {"kicad_version": erc_report.kicad_version, "violations": violations},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        normalized_erc_hashes[run] = hashlib.sha256(normalized_erc).hexdigest()
        native_erc_types[run] = tuple(sorted(item.type for item in erc_report.violations))
        native_erc_error_types[run] = tuple(
            sorted(item.type for item in erc_report.violations if item.severity == "error")
        )
        if native_erc_error_types[run]:
            raise ValueError(
                f"Synthetic energy-storage schematic has native ERC errors: "
                f"{native_erc_error_types[run]}"
            )
    if normalized_netlist_hashes["first"] != normalized_netlist_hashes["repeat"]:
        raise ValueError("Native energy-storage netlists differ after normalization")
    if normalized_erc_hashes["first"] != normalized_erc_hashes["repeat"]:
        raise ValueError("Native energy-storage ERC reports differ after normalization")
    observed = parsed["first"]
    requirement = EnergyStorageHoldUpRequirement(
        id="controller-rail-hold-up",
        reference="C1",
        expected_symbol="Device:C",
        expected_footprint="Synthetic:Radial_Supercap",
        expected_part_id="SUPER-CAP-0P1F",
        pins=("C1.1", "C1.2"),
        nets=("VLOAD", "GND"),
        minimum_start_voltage_v=1.8,
        minimum_operating_voltage_v=1.2,
        maximum_constant_load_current_a=0.05,
        minimum_hold_up_time_s=0.5,
        minimum_effective_capacitance_fraction=0.6,
        maximum_utilization_fraction=0.8,
        capacitance_source="Synthetic supercapacitor data table, Rev A",
        effective_capacitance_basis=(
            "Synthetic lower-bound factor including stated tolerance and temperature range"
        ),
        load_current_basis="Synthetic maximum constant-current load calculation",
        voltage_window_basis="Synthetic minimum start and regulated-load voltage corners",
        hold_up_basis="Synthetic minimum backup duration requirement",
    )

    def evaluate(duration_s: float) -> tuple[str, float]:
        spec = EnergyStorageAnalysis(
            basis="Synthetic exact-part constant-current hold-up comparison",
            requirements=(requirement.model_copy(update={"minimum_hold_up_time_s": duration_s}),),
        )
        checks = energy_storage_hold_up_checks(spec, observed)
        by_suffix = {item.id.rsplit("/", maxsplit=1)[-1]: item for item in checks}
        if any(by_suffix[name].status != "PASS" for name in ("identity", "pin-1", "pin-2")):
            raise ValueError("Native storage identity or exact pin/net assignments differ")
        hold_up = by_suffix["hold-up"]
        if hold_up.observed is None:
            raise ValueError("Native storage hold-up check omitted its calculated utilization")
        return hold_up.status, hold_up.observed

    control_status, control_utilization = evaluate(0.5)
    fault_status, fault_utilization = evaluate(0.6)
    if control_status != "PASS" or fault_status != "FAIL":
        raise ValueError("Energy-storage hold-up control/fault did not produce PASS/FAIL")
    log.event(
        "energy-storage-hold-up-fixture/native-export",
        "PASS",
        project=context.project,
        kicad_version=context.config.kicad_version,
        image=context.pinned,
        fixture_sha256=fixture_sha256,
        normalized_netlist_sha256=normalized_netlist_hashes["first"],
        repeat_normalized_netlist_sha256=normalized_netlist_hashes["repeat"],
        normalized_erc_sha256=normalized_erc_hashes["first"],
        repeat_normalized_erc_sha256=normalized_erc_hashes["repeat"],
        native_erc_types=",".join(native_erc_types["first"]) or "none",
        native_erc_error_types=",".join(native_erc_error_types["first"]) or "none",
        repeatable="true",
        repeatability_basis="normalized_netlist_and_erc",
    )
    for case, duration_s, status, utilization in (
        ("control", 0.5, control_status, control_utilization),
        ("over-limit-fault", 0.6, fault_status, fault_utilization),
    ):
        log.event(
            f"energy-storage-hold-up-fixture/{case}",
            "PASS",
            project=context.project,
            kicad_version=context.config.kicad_version,
            image=context.pinned,
            fixture_sha256=fixture_sha256,
            normalized_erc_sha256=normalized_erc_hashes["first"],
            native_erc_error_types=",".join(native_erc_error_types["first"]) or "none",
            minimum_hold_up_time_s=duration_s,
            utilization=utilization,
            utilization_status=status,
            repeatable="true",
        )
    if digest(fixture) != fixture_sha256:
        raise ValueError("Synthetic energy-storage fixture changed during native export")

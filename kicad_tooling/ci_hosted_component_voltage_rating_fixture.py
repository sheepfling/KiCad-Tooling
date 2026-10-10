"""Validate native voltage rating fixture evidence and controls."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from .ci_hosted_component_rating_context import ComponentRatingFixtureContext
from .hwrepo.contracts import read_kicad_erc_report
from .hwrepo.evidence import digest
from .validate import read_netlist

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


from .hwrepo.component_voltage_ratings import component_voltage_rating_checks
from .hwrepo.models import (
    ComponentVoltageRatingAnalysis,
    ComponentVoltageRatingRequirement,
    NetlistContract,
)


def verify_component_voltage_rating_fixture(
    context: ComponentRatingFixtureContext, log: HostedLog
) -> None:
    root = context.root
    project = context.project
    config = context.config
    pinned = context.pinned
    fixture = context.fixture
    fixture_sha256 = context.fixture_sha256
    scratch = context.scratch
    output = context.output
    raw_hashes: dict[str, str] = {}
    normalized_hashes: dict[str, str] = {}
    normalized_erc_hashes: dict[str, str] = {}
    erc_types: dict[str, tuple[str, ...]] = {}
    erc_error_types: dict[str, tuple[str, ...]] = {}
    parsed: dict[str, NetlistContract] = {}
    for run in ("first", "repeat"):
        netlist_path = output / f"rating.{run}.netlist.xml"
        if not netlist_path.is_file():
            raise ValueError(f"Native component-rating export omitted {netlist_path.name}")
        raw_hashes[run] = digest(netlist_path)
        observed = read_netlist(netlist_path)
        normalized = json.dumps(
            observed.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        normalized_hashes[run] = hashlib.sha256(normalized).hexdigest()
        parsed[run] = observed
        erc_path = output / f"rating.{run}.erc.json"
        if not erc_path.is_file():
            raise ValueError(f"Native component-rating export omitted {erc_path.name}")
        erc_report = read_kicad_erc_report(erc_path)
        if erc_report.kicad_version != config.kicad_version:
            raise ValueError(
                f"Native component-rating ERC version differs from KiCad {config.kicad_version}"
            )
        erc_types[run] = tuple(sorted(item.type for item in erc_report.violations))
        erc_error_types[run] = tuple(
            sorted(item.type for item in erc_report.violations if item.severity == "error")
        )
        if erc_error_types[run]:
            raise ValueError(
                f"Synthetic component-rating schematic has native ERC errors: "
                f"{erc_error_types[run]}"
            )
        normalized_erc = json.dumps(
            {
                "kicad_version": erc_report.kicad_version,
                "violations": sorted(
                    [
                        (
                            item.type,
                            item.severity,
                            item.description,
                            tuple(
                                sorted(
                                    [
                                        (detail.description, detail.x, detail.y)
                                        for detail in item.items
                                    ],
                                    key=lambda detail: json.dumps(
                                        detail,
                                        sort_keys=True,
                                        separators=(",", ":"),
                                        ensure_ascii=False,
                                    ),
                                )
                            ),
                        )
                        for item in erc_report.violations
                    ],
                    key=lambda item: json.dumps(
                        item,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ),
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        normalized_erc_hashes[run] = hashlib.sha256(normalized_erc).hexdigest()
    if normalized_hashes["first"] != normalized_hashes["repeat"]:
        raise ValueError("Native component-rating exports differ after netlist normalization")
    if normalized_erc_hashes["first"] != normalized_erc_hashes["repeat"]:
        raise ValueError("Native component-rating ERC reports differ after normalization")

    observed = parsed["first"]
    c1 = observed.components.get("C1")
    if (
        c1 is None
        or c1.footprint != "Synthetic:0603"
        or c1.part_id != "CAP-0603-16V"
        or observed.component_symbols.get("C1") != "Device:C"
        or set(observed.component_pin_numbers.get("C1", ())) != {"1", "2"}
    ):
        raise ValueError("Native C1 component identity or exact two-pin inventory differs")
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    if pin_nets.get("c1.1") != {"VLOAD"} or pin_nets.get("c1.2") != {"GND"}:
        raise ValueError("Native C1 pin-to-net assignments differ from the synthetic map")

    def check(maximum_expected_voltage_v: float) -> tuple[str, tuple[str, ...]]:
        requirement = ComponentVoltageRatingRequirement(
            id="load-capacitor",
            reference="C1",
            expected_symbol="Device:C",
            expected_footprint="Synthetic:0603",
            expected_part_id="CAP-0603-16V",
            pins=("C1.1", "C1.2"),
            nets=("VLOAD", "GND"),
            rated_working_voltage_v=24.0,
            maximum_expected_voltage_v=maximum_expected_voltage_v,
            maximum_utilization_fraction=0.8,
            rating_source="Synthetic capacitor datasheet Rev A, working-voltage table",
            rating_conditions="DC working voltage over the stated temperature range",
            stress_basis="Synthetic reviewed worst-case steady-state rail envelope",
        )
        spec = ComponentVoltageRatingAnalysis(
            basis="Synthetic exact-part rating comparison", requirements=(requirement,)
        )
        checks = component_voltage_rating_checks(spec, observed)
        margin = next(item for item in checks if item.id.endswith("/utilization"))
        if any(item.status != "PASS" for item in checks if not item.id.endswith("/utilization")):
            raise ValueError("Native component identity and pin-map checks did not pass")
        return margin.status, tuple(item.id for item in checks if item.status != "PASS")

    control_status, control_open = check(15.0)
    fault_status, fault_open = check(20.0)
    if control_status != "PASS" or control_open:
        raise ValueError("Native component voltage-rating control did not pass")
    if fault_status != "FAIL" or len(fault_open) != 1:
        raise ValueError("Native over-utilization fault was not detected")
    log.event(
        "component-voltage-rating-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        fixture_sha256=fixture_sha256,
        first_netlist_sha256=raw_hashes["first"],
        repeat_netlist_sha256=raw_hashes["repeat"],
        normalized_netlist_sha256=normalized_hashes["first"],
        repeat_normalized_netlist_sha256=normalized_hashes["repeat"],
        normalized_erc_sha256=normalized_erc_hashes["first"],
        repeat_normalized_erc_sha256=normalized_erc_hashes["repeat"],
        native_erc_types=",".join(erc_types["first"]) or "none",
        native_erc_error_types=",".join(erc_error_types["first"]) or "none",
        repeatable="true",
        repeatability_basis="normalized_netlist_and_erc",
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
    for case, stress, status in (
        ("control", 15.0, control_status),
        ("over-limit-fault", 20.0, fault_status),
    ):
        log.event(
            f"component-voltage-rating-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            fixture_sha256=fixture_sha256,
            netlist_sha256=raw_hashes["first"],
            normalized_erc_sha256=normalized_erc_hashes["first"],
            native_erc_types=",".join(erc_types["first"]) or "none",
            native_erc_error_types=",".join(erc_error_types["first"]) or "none",
            maximum_expected_voltage_v=stress,
            utilization_status=status,
            repeatable="true",
        )
    if digest(fixture) != fixture_sha256:
        raise ValueError("Synthetic component voltage-rating fixture changed during native export")

"""Validate native power rating fixture evidence and controls."""

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


from .hwrepo.component_power_ratings import component_power_rating_checks
from .hwrepo.models import (
    ComponentPowerRatingAnalysis,
    ComponentPowerRatingRequirement,
    NetlistContract,
)


def verify_component_power_rating_fixture(
    context: ComponentRatingFixtureContext, log: HostedLog
) -> None:
    root = context.root
    project = context.project
    config = context.config
    pinned = context.pinned
    power_fixture = context.power_fixture
    power_fixture_sha256 = context.power_fixture_sha256
    scratch = context.scratch
    output = context.output
    power_raw_hashes: dict[str, str] = {}
    power_normalized_hashes: dict[str, str] = {}
    power_erc_hashes: dict[str, str] = {}
    power_erc_types: dict[str, tuple[tuple[str, str], ...]] = {}
    power_parsed: dict[str, NetlistContract] = {}
    for run in ("first", "repeat"):
        netlist_path = output / f"power.{run}.netlist.xml"
        if not netlist_path.is_file():
            raise ValueError(f"Native component power-rating export omitted {netlist_path.name}")
        power_raw_hashes[run] = digest(netlist_path)
        observed_power = read_netlist(netlist_path)
        normalized_power = json.dumps(
            observed_power.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        power_normalized_hashes[run] = hashlib.sha256(normalized_power).hexdigest()
        power_parsed[run] = observed_power

        erc_path = output / f"power.{run}.erc.json"
        if not erc_path.is_file():
            raise ValueError(f"Native component power-rating export omitted {erc_path.name}")
        erc_report = read_kicad_erc_report(erc_path)
        if erc_report.kicad_version != config.kicad_version:
            raise ValueError(
                f"Native component power-rating ERC version differs from KiCad {config.kicad_version}"
            )
        power_erc_types[run] = tuple(
            sorted((item.type, item.severity) for item in erc_report.violations)
        )
        errors = tuple(item for item in power_erc_types[run] if item[1] == "error")
        if errors:
            raise ValueError(
                f"Synthetic component power-rating schematic has native ERC errors: {errors}"
            )
        power_erc_hashes[run] = hashlib.sha256(
            json.dumps(power_erc_types[run], separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
    if power_normalized_hashes["first"] != power_normalized_hashes["repeat"]:
        raise ValueError("Native component power-rating exports differ after netlist normalization")
    if power_erc_hashes["first"] != power_erc_hashes["repeat"]:
        raise ValueError("Native component power-rating ERC results differ after normalization")

    power_observed = power_parsed["first"]
    resistor = power_observed.components.get("R1")
    if (
        resistor is None
        or resistor.footprint != "Synthetic:R_0603"
        or resistor.part_id != "RES-SYNTHETIC-0603"
        or power_observed.component_symbols.get("R1") != "Device:R"
        or set(power_observed.component_pin_numbers.get("R1", ())) != {"1", "2"}
    ):
        raise ValueError("Native R1 component identity or exact two-pin inventory differs")
    power_pin_nets: dict[str, set[str]] = {}
    for net, pins in power_observed.nets.items():
        for pin in pins:
            power_pin_nets.setdefault(pin.casefold(), set()).add(net)
    if power_pin_nets.get("r1.1") != {"INPUT"} or power_pin_nets.get("r1.2") != {"OUTPUT"}:
        raise ValueError("Native R1 pin-to-net assignments differ from the synthetic map")

    def power_check(maximum_expected_power_w: float) -> tuple[str, tuple[str, ...]]:
        requirement = ComponentPowerRatingRequirement(
            id="sense-resistor",
            reference="R1",
            expected_symbol="Device:R",
            expected_footprint="Synthetic:R_0603",
            expected_part_id="RES-SYNTHETIC-0603",
            pins=("R1.1", "R1.2"),
            nets=("INPUT", "OUTPUT"),
            rated_power_w=0.5,
            derated_allowable_power_w=0.25,
            maximum_expected_power_w=maximum_expected_power_w,
            maximum_utilization_fraction=0.8,
            rating_source="Synthetic resistor specification, power table",
            rating_conditions="Synthetic declared board-temperature conditions",
            derating_basis="Synthetic reviewed derating curve at the fixture temperature",
            stress_basis="Synthetic reviewed worst-case dissipation calculation",
        )
        spec = ComponentPowerRatingAnalysis(
            basis="Synthetic exact-part power-rating comparison", requirements=(requirement,)
        )
        checks = component_power_rating_checks(spec, power_observed)
        margin = next(item for item in checks if item.id.endswith("/utilization"))
        if any(item.status != "PASS" for item in checks if not item.id.endswith("/utilization")):
            raise ValueError("Native component power identity and pin-map checks did not pass")
        return margin.status, tuple(item.id for item in checks if item.status != "PASS")

    power_control_status, power_control_open = power_check(0.1)
    power_fault_status, power_fault_open = power_check(0.21)
    if power_control_status != "PASS" or power_control_open:
        raise ValueError("Native component power-rating control did not pass")
    if power_fault_status != "FAIL" or len(power_fault_open) != 1:
        raise ValueError("Native over-utilization power fault was not detected")

    power_receipt = (scratch / "native.command.json").relative_to(root).as_posix()
    log.event(
        "component-power-rating-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        fixture_sha256=power_fixture_sha256,
        first_netlist_sha256=power_raw_hashes["first"],
        repeat_netlist_sha256=power_raw_hashes["repeat"],
        normalized_netlist_sha256=power_normalized_hashes["first"],
        repeat_normalized_netlist_sha256=power_normalized_hashes["repeat"],
        normalized_erc_sha256=power_erc_hashes["first"],
        repeat_normalized_erc_sha256=power_erc_hashes["repeat"],
        native_erc_types=";".join(
            f"{kind}:{severity}" for kind, severity in power_erc_types["first"]
        )
        or "none",
        native_erc_error_types="none",
        repeatable="true",
        repeatability_basis="normalized_netlist_and_erc_types",
        command_receipt=power_receipt,
    )
    for case, stress, status in (
        ("control", 0.1, power_control_status),
        ("over-limit-fault", 0.21, power_fault_status),
    ):
        log.event(
            f"component-power-rating-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            fixture_sha256=power_fixture_sha256,
            netlist_sha256=power_raw_hashes["first"],
            normalized_netlist_sha256=power_normalized_hashes["first"],
            normalized_erc_sha256=power_erc_hashes["first"],
            native_erc_types=";".join(
                f"{kind}:{severity}" for kind, severity in power_erc_types["first"]
            )
            or "none",
            native_erc_error_types="none",
            maximum_expected_power_w=stress,
            utilization_status=status,
            repeatable="true",
        )
    if digest(power_fixture) != power_fixture_sha256:
        raise ValueError("Synthetic component power-rating fixture changed during native export")

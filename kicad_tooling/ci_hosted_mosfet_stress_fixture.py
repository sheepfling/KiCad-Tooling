"""Validate native mosfet rating fixture evidence and controls."""

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


from .hwrepo.models import (
    NetlistContract,
)
from .hwrepo.mosfet_stress import mosfet_stress_checks
from .hwrepo.mosfet_stress_models import (
    MosfetOperatingState,
    MosfetStressAnalysis,
    MosfetStressRequirement,
    MosfetVoltageInterval,
)


def verify_mosfet_stress_fixture(context: ComponentRatingFixtureContext, log: HostedLog) -> None:
    root = context.root
    project = context.project
    config = context.config
    pinned = context.pinned
    mosfet_fixture = context.mosfet_fixture
    mosfet_fixture_sha256 = context.mosfet_fixture_sha256
    scratch = context.scratch
    output = context.output
    mosfet_parsed: dict[str, NetlistContract] = {}
    mosfet_normalized_hashes: dict[str, str] = {}
    mosfet_erc_hashes: dict[str, str] = {}
    mosfet_erc_types: dict[str, tuple[tuple[str, str], ...]] = {}
    for run in ("first", "repeat"):
        netlist_path = output / f"mosfet.{run}.netlist.xml"
        erc_path = output / f"mosfet.{run}.erc.json"
        if not netlist_path.is_file() or not erc_path.is_file():
            raise ValueError("Native MOSFET stress fixture omitted a repeated export or ERC report")
        observed_mosfet = read_netlist(netlist_path)
        normalized = json.dumps(
            observed_mosfet.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        mosfet_normalized_hashes[run] = hashlib.sha256(normalized).hexdigest()
        mosfet_parsed[run] = observed_mosfet
        erc_report = read_kicad_erc_report(erc_path)
        if erc_report.kicad_version != config.kicad_version:
            raise ValueError("Native MOSFET ERC version differs from its pinned KiCad version")
        mosfet_erc_types[run] = tuple(
            sorted((item.type, item.severity) for item in erc_report.violations)
        )
        errors = tuple(item for item in mosfet_erc_types[run] if item[1] == "error")
        if errors:
            raise ValueError(f"Synthetic MOSFET schematic has native ERC errors: {errors}")
        mosfet_erc_hashes[run] = hashlib.sha256(
            json.dumps(mosfet_erc_types[run], separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
    if mosfet_normalized_hashes["first"] != mosfet_normalized_hashes["repeat"]:
        raise ValueError("Native MOSFET exports differ after netlist normalization")
    if mosfet_erc_hashes["first"] != mosfet_erc_hashes["repeat"]:
        raise ValueError("Native MOSFET ERC reports differ after normalization")

    mosfet_observed = mosfet_parsed["first"]
    mosfet_component = mosfet_observed.components.get("Q1")
    if (
        mosfet_component is None
        or mosfet_component.footprint != "Synthetic:TO-220"
        or mosfet_component.part_id != "SYN-NMOS-001"
        or mosfet_observed.component_symbols.get("Q1") != "Synthetic:Q_NMOS_GDS"
        or set(mosfet_observed.component_pin_numbers.get("Q1", ())) != {"1", "2", "3"}
        or {pin: mosfet_observed.pin_functions.get(pin) for pin in ("Q1.1", "Q1.2", "Q1.3")}
        != {"Q1.1": "D", "Q1.2": "G", "Q1.3": "S"}
    ):
        raise ValueError("Native MOSFET identity, pin functions, or exact inventory differs")
    mosfet_pin_nets: dict[str, set[str]] = {}
    for net, pins in mosfet_observed.nets.items():
        for pin in pins:
            mosfet_pin_nets.setdefault(pin.casefold(), set()).add(net)
    if any(
        mosfet_pin_nets.get(pin.casefold()) != {net}
        for pin, net in (("Q1.1", "D_NET"), ("Q1.2", "G_NET"), ("Q1.3", "S_NET"))
    ):
        raise ValueError("Native MOSFET terminal-to-net assignments differ from the synthetic map")

    def mosfet_check(drain_v: float, gate_v: float) -> tuple[str, tuple[str, ...]]:
        states = (
            MosfetOperatingState(
                id="off",
                net_potentials={
                    name: MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0)
                    for name in ("D_NET", "G_NET", "S_NET")
                },
            ),
            MosfetOperatingState(
                id="on",
                net_potentials={
                    "D_NET": MosfetVoltageInterval(minimum_v=drain_v, maximum_v=drain_v),
                    "G_NET": MosfetVoltageInterval(minimum_v=gate_v, maximum_v=gate_v),
                    "S_NET": MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0),
                },
            ),
        )
        requirement = MosfetStressRequirement(
            id="main-switch",
            reference="Q1",
            expected_symbol="Synthetic:Q_NMOS_GDS",
            expected_footprint="Synthetic:TO-220",
            expected_part_id="SYN-NMOS-001",
            drain_pin="Q1.1",
            drain_function="D",
            drain_net="D_NET",
            gate_pin="Q1.2",
            gate_function="G",
            gate_net="G_NET",
            source_pin="Q1.3",
            source_function="S",
            source_net="S_NET",
            rated_maximum_vds_v=60.0,
            rated_maximum_vgs_v=20.0,
            maximum_utilization_fraction=0.8,
            rating_source="Synthetic MOSFET specification, absolute maximum ratings table",
            rating_conditions="Synthetic declared operating conditions",
            stress_basis="Synthetic required steady-state off and on potential bounds",
        )
        spec = MosfetStressAnalysis(
            basis="Synthetic per-state MOSFET terminal stress comparison",
            required_states=("off", "on"),
            states=states,
            requirements=(requirement,),
        )
        checks = mosfet_stress_checks(spec, mosfet_observed)
        unexpected = tuple(
            item.id
            for item in checks
            if item.status != "PASS" and not (item.id.endswith("/vds") or item.id.endswith("/vgs"))
        )
        if unexpected:
            raise ValueError(
                f"Native MOSFET identity, terminal, or state checks failed: {unexpected}"
            )
        stress = tuple(
            item for item in checks if item.id.endswith("/vds") or item.id.endswith("/vgs")
        )
        if drain_v == 48.0 and gate_v == 16.0:
            if any(item.status != "PASS" for item in stress):
                raise ValueError("Native MOSFET equality-at-project-limit control failed")
            return "PASS", ()
        expected_failed = {
            "mosfet-stress/main-switch/state-on/vds",
            "mosfet-stress/main-switch/state-on/vgs",
        }
        failed = tuple(sorted(item.id for item in stress if item.status == "FAIL"))
        unexpected_statuses = tuple(
            item.id
            for item in stress
            if item.status != ("FAIL" if item.id in expected_failed else "PASS")
        )
        if set(failed) != expected_failed or unexpected_statuses:
            raise ValueError("Native MOSFET over-stress fault was not detected for both ratings")
        return "FAIL", failed

    mosfet_control_status, mosfet_control_open = mosfet_check(48.0, 16.0)
    mosfet_fault_status, mosfet_fault_open = mosfet_check(49.0, 17.0)
    if mosfet_control_status != "PASS" or mosfet_control_open:
        raise ValueError("Native MOSFET control at the project utilization limit did not pass")
    if mosfet_fault_status != "FAIL" or len(mosfet_fault_open) != 2:
        raise ValueError("Native MOSFET over-utilization fault was not detected")

    mosfet_receipt = (scratch / "native.command.json").relative_to(root).as_posix()
    log.event(
        "component-mosfet-stress-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        fixture_sha256=mosfet_fixture_sha256,
        first_netlist_sha256=digest(output / "mosfet.first.netlist.xml"),
        repeat_netlist_sha256=digest(output / "mosfet.repeat.netlist.xml"),
        normalized_netlist_sha256=mosfet_normalized_hashes["first"],
        repeat_normalized_netlist_sha256=mosfet_normalized_hashes["repeat"],
        normalized_erc_sha256=mosfet_erc_hashes["first"],
        repeat_normalized_erc_sha256=mosfet_erc_hashes["repeat"],
        native_erc_types=";".join(
            f"{kind}:{severity}" for kind, severity in mosfet_erc_types["first"]
        )
        or "none",
        native_erc_error_types="none",
        repeatable="true",
        repeatability_basis="normalized_netlist_and_erc_types",
        command_receipt=mosfet_receipt,
    )
    for case, drain_v, gate_v, status in (
        ("control", 48.0, 16.0, mosfet_control_status),
        ("over-limit-fault", 49.0, 17.0, mosfet_fault_status),
    ):
        log.event(
            f"component-mosfet-stress-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            fixture_sha256=mosfet_fixture_sha256,
            normalized_netlist_sha256=mosfet_normalized_hashes["first"],
            normalized_erc_sha256=mosfet_erc_hashes["first"],
            native_erc_error_types="none",
            drain_potential_v=drain_v,
            gate_potential_v=gate_v,
            utilization_status=status,
            repeatable="true",
        )
    if digest(mosfet_fixture) != mosfet_fixture_sha256:
        raise ValueError("Synthetic MOSFET stress fixture changed during native export")

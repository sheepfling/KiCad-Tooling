"""Digest-pinned native export lane for Ethernet pin/net-label review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

RULE_ID = "bus.ethernet_data_label_mismatch"
MANAGEMENT_RULE_ID = "bus.ethernet_management_label_mismatch"
MANAGEMENT_NAMED_RAIL_RULE_ID = "bus.ethernet_management_signal_on_named_rail"
MANAGEMENT_UNCONNECTED_RULE_ID = "bus.ethernet_management_unconnected_pin"
ETHERNET_LABEL_NATIVE_TOOLCHAINS = (
    (
        "10.0.0",
        (
            "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
        ),
    ),
    (
        "10.0.5",
        (
            "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
        ),
    ),
)


@dataclass(frozen=True)
class _EthernetLabelFixture:
    directory: str
    rule_id: str
    stage_prefix: str
    source_hashes: dict[str, str]
    expected_subjects: tuple[str, ...]
    expected_pins: dict[str, dict[str, tuple[str, str | None]]]
    complete_data_pairs: bool = False


_FIXTURES: dict[str, _EthernetLabelFixture] = {
    "data": _EthernetLabelFixture(
        directory="ethernet-data-label-native",
        rule_id=RULE_ID,
        stage_prefix="ethernet-label-fixture",
        source_hashes={
            "control": "9fae1afdb0395354f6e61eae17623f5d940b2f90bf82d452ff8339bfed1e421e",
            "fault": "8b42bc11362cedc71519b7ffb2477da399c52374efcf44bcb69d35149f9a1b92",
        },
        expected_subjects=(
            "U1.1: TDP on ETH_RX_P",
            "U1.2: TDN on ETH_RX_N",
            "U1.3: RDP on ETH_TX_P",
            "U1.4: RDN on ETH_TX_N",
        ),
        expected_pins={
            "control": {
                "U1.1": ("TDP", "ETH_TX_P"),
                "U1.2": ("TDN", "ETH_TX_N"),
                "U1.3": ("RDP", "ETH_RX_P"),
                "U1.4": ("RDN", "ETH_RX_N"),
            },
            "fault": {
                "U1.1": ("TDP", "ETH_RX_P"),
                "U1.2": ("TDN", "ETH_RX_N"),
                "U1.3": ("RDP", "ETH_TX_P"),
                "U1.4": ("RDN", "ETH_TX_N"),
            },
        },
        complete_data_pairs=True,
    ),
    "management": _EthernetLabelFixture(
        directory="ethernet-management-label-native",
        rule_id=MANAGEMENT_RULE_ID,
        stage_prefix="ethernet-management-label-fixture",
        source_hashes={
            "control": "3ddd8d2919eade8a6bb8f7a8c059dafbe9b348aacbb5a6bb8398b0c62944d31b",
            "fault": "f63b39e17d68c36202e323534f2ea58b63247a2e55b0188bc048056d26cf1495",
        },
        expected_subjects=("U1.5: MDC on ETH_MDIO", "U1.6: MDIO on ETH_MDC"),
        expected_pins={
            "control": {"U1.5": ("MDC", "ETH_MDC"), "U1.6": ("MDIO", "ETH_MDIO")},
            "fault": {"U1.5": ("MDC", "ETH_MDIO"), "U1.6": ("MDIO", "ETH_MDC")},
        },
    ),
    "management_named_rail": _EthernetLabelFixture(
        directory="ethernet-management-named-rail",
        rule_id=MANAGEMENT_NAMED_RAIL_RULE_ID,
        stage_prefix="ethernet-management-named-rail-fixture",
        source_hashes={
            "control": "3ddd8d2919eade8a6bb8f7a8c059dafbe9b348aacbb5a6bb8398b0c62944d31b",
            "fault": "6ab770da2bd563b08152d89a12f10f1eb872550233815e3f1b398c4e290fc86a",
        },
        expected_subjects=("U1.5: MDC on return-like net GND",),
        expected_pins={
            "control": {"U1.5": ("MDC", "ETH_MDC"), "U1.6": ("MDIO", "ETH_MDIO")},
            "fault": {"U1.5": ("MDC", "GND"), "U1.6": ("MDIO", "ETH_MDIO")},
        },
    ),
    "management_unconnected": _EthernetLabelFixture(
        directory="ethernet-management-unconnected-native",
        rule_id=MANAGEMENT_UNCONNECTED_RULE_ID,
        stage_prefix="ethernet-management-unconnected-fixture",
        source_hashes={
            "control": "c3c259a0ce8d0b4be736be63bb106096657b4c596985557460351a88a0e326d6",
            "fault": "d2324d82038d896ed81727d7934c80e0549e7605c369adabd5c5f2ca81604988",
        },
        expected_subjects=("U1.5: MDC is open while MDIO U1.6 is assigned to ETH_MDIO",),
        expected_pins={
            "control": {
                "U1.5": ("MDC", "ETH_MDC"),
                "U1.6": ("MDIO", "ETH_MDIO"),
            },
            "fault": {
                "U1.5": ("MDC", None),
                "U1.6": ("MDIO", "ETH_MDIO"),
            },
        },
    ),
    "named_rail": _EthernetLabelFixture(
        directory="ethernet-signal-named-rail",
        rule_id="bus.ethernet_signal_on_named_rail",
        stage_prefix="ethernet-signal-named-rail-fixture",
        source_hashes={
            "control": "b8460f781f7f3ef341b375656ae487ed926cd3a3824098180c5b7460fe61fecd",
            "fault": "1db5c1e1efa99eaf09df7f9a853fe37f4c621afb56481ccc7f909fa0d96c3531",
        },
        expected_subjects=("U1.1: TDP on return-like net GND",),
        expected_pins={
            "control": {
                "U1.1": ("TDP", "ETH_TX_P"),
                "U1.2": ("TDN", "ETH_TX_N"),
                "U1.3": ("RDP", "ETH_RX_P"),
                "U1.4": ("RDN", "ETH_RX_N"),
            },
            "fault": {
                "U1.1": ("TDP", "GND"),
                "U1.2": ("TDN", "ETH_TX_N"),
                "U1.3": ("RDP", "ETH_RX_P"),
                "U1.4": ("RDN", "ETH_RX_N"),
            },
        },
    ),
}


def ethernet_label_fixture_lane(
    root: Path,
    *,
    project: str | None = None,
    version: str | None = None,
    image: str,
    log: HostedLog,
    feature: Literal[
        "data", "management", "named_rail", "management_named_rail", "management_unconnected"
    ] = "data",
) -> None:
    """Export source-hashed Ethernet label controls and evaluate one focused rule."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.design_lint_report_models import DesignLintReport
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy, NetlistContract
    from .validate import read_netlist

    root = root.resolve()
    fixture = _FIXTURES[feature]
    if project is None:
        if version is None or (version, image) not in ETHERNET_LABEL_NATIVE_TOOLCHAINS:
            raise ValueError("Ethernet native fixture requires a configured KiCad 10 toolchain")
        selected_version = version
        project_label = f"kicad-{version}"
    else:
        config = selected_config(root, project)
        if config.image != image:
            raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
        if version is not None and config.kicad_version != version:
            raise ValueError(
                f"{project}: native fixture version differs from its reviewed toolchain"
            )
        if config.kicad_version not in {"10.0.0", "10.0.5"}:
            raise ValueError(f"Ethernet label fixtures do not cover KiCad {config.kicad_version}")
        selected_version = config.kicad_version
        project_label = project
    pinned = pinned_image(image)
    repository = Path(__file__).resolve().parents[1]
    sources = {
        case: repository / f"tests/fixtures/design_lint/{fixture.directory}/{case}.kicad_sch"
        for case in ("control", "fault")
    }
    source_hashes = {case: digest(path) for case, path in sources.items()}
    if source_hashes != fixture.source_hashes:
        raise ValueError("Ethernet label fixtures differ from their reviewed source hashes")

    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"ethernet-{feature}-label-{project_label}-", dir=log.directory.resolve()
        )
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        target = inputs / f"{case}.kicad_sch"
        shutil.copyfile(source, target)
        if digest(target) != source_hashes[case]:
            raise ValueError(f"Synthetic Ethernet {case} schematic changed during preparation")
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{selected_version}"\n'
        "for case in control fault; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
        '      "/fixtures/${case}.kicad_sch"\n'
        "  done\n"
        "done\n"
    )
    argv = (
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",
        *user,
        "-e",
        "HOME=/tmp/kicad-ethernet-label-fixtures",
        "-v",
        f"{inputs}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        script,
    )
    log.event(
        f"{fixture.stage_prefix}/native-export",
        "START",
        project=project_label,
        kicad_version=selected_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            f"{fixture.stage_prefix}/native-export",
            "FAIL",
            project=project_label,
            kicad_version=selected_version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native Ethernet label export failed: {command.stderr or command.error}")
    log.event(
        f"{fixture.stage_prefix}/native-export",
        "PASS",
        project=project_label,
        kicad_version=selected_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in sorted(sources)),
        command_receipt=receipt.relative_to(root).as_posix(),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    observations: dict[tuple[str, str], NetlistContract] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native Ethernet export omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            observations[(case, run)] = observed
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            project_id = f"synthetic-ethernet-{feature}-label-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, DesignLintPolicy())

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]
        for case in sources
    ):
        raise ValueError("Native Ethernet exports differ after netlist normalization")

    control = reports[("control", "first")]
    fault = reports[("fault", "first")]
    control_findings = tuple(item for item in control.findings if item.rule_id == fixture.rule_id)
    fault_findings = tuple(item for item in fault.findings if item.rule_id == fixture.rule_id)
    if control_findings:
        raise ValueError("Native Ethernet label control produced an unexpected finding")
    if tuple(item.subject for item in fault_findings) != fixture.expected_subjects:
        raise ValueError(
            f"Native Ethernet label fault produced "
            f"{tuple(item.subject for item in fault_findings)!r}; "
            f"expected {fixture.expected_subjects!r}"
        )
    if fixture.complete_data_pairs and any(
        item.rule_id == "bus.complementary_pair_assignment" for item in fault.findings
    ):
        raise ValueError("Complete Ethernet pairs should remain outside pair-completeness findings")

    for case, report, findings in (
        ("control", control, control_findings),
        ("fault", fault, fault_findings),
    ):
        observed = observations[(case, "first")]
        for pin, (function, net) in fixture.expected_pins[case].items():
            assigned_nets = tuple(
                sorted(
                    name
                    for name, members in observed.nets.items()
                    if any(member.casefold() == pin.casefold() for member in members)
                )
            )
            expected_nets = () if net is None else (net,)
            if observed.pin_functions.get(pin) != function or assigned_nets != expected_nets:
                raise ValueError(f"Native Ethernet {feature} {case} evidence changed for {pin}")
            if net is None:
                unconnected_pins = {
                    pin.casefold()
                    for members in observed.unconnected_nets.values()
                    for pin in members
                }
                if pin.casefold() not in unconnected_pins:
                    raise ValueError(
                        f"Native Ethernet {feature} {case} omitted the open-pin evidence for {pin}"
                    )
        log.event(
            f"{fixture.stage_prefix}/{case}",
            "PASS",
            project=project_label,
            kicad_version=selected_version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            repeatable="true",
            lint_status=report.status,
            findings=";".join(item.subject for item in findings) if findings else "none",
        )
    log.finish()

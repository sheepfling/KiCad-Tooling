"""USB-C port fixture analysis and native acceptance."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Literal, TypeAlias

from .ci_hosted_native_fixture_models import (
    FixtureSourceEvidence,
    NativeNetlistFixtureEvidence,
    NativeNetlistRunEvidence,
    NativeRun,
    NativeRunPair,
)
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.analysis_state_models import AnalysisNotApplicable
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .hwrepo.usb_c_models import (
    UsbCAnalysis,
    UsbCcLineRequirement,
    UsbCcResistorAttachment,
    UsbCNetPinAssignment,
    UsbCPortRequirement,
    UsbCVbusCapacitanceRequirement,
    UsbCVbusCapacitorRequirement,
)
from .hwrepo.usb_c_ports import UsbCPortRosterContext
from .hwrepo.usb_c_vbus import usb_c_vbus_capacitance_check
from .validate import read_netlist

UsbCPortFixtureCase: TypeAlias = Literal[
    "connector",
    "source-rp-control",
    "sink-rd-control",
    "vbus-capacitance-control",
    "vbus-capacitance-fault",
]
UsbCPortControlFixtureCase: TypeAlias = Literal["source-rp-control", "sink-rd-control"]
UsbCPortRosterScenario: TypeAlias = Literal["unmapped", "mapped"]
UsbCPortReviewCase: TypeAlias = UsbCPortControlFixtureCase | UsbCPortRosterScenario
_FIXTURE_CASES: tuple[UsbCPortFixtureCase, ...] = (
    "connector",
    "source-rp-control",
    "sink-rd-control",
    "vbus-capacitance-control",
    "vbus-capacitance-fault",
)
_CONTROL_FIXTURE_CASES: tuple[UsbCPortControlFixtureCase, ...] = (
    "source-rp-control",
    "sink-rd-control",
)
_ROSTER_SCENARIOS: tuple[UsbCPortRosterScenario, ...] = ("unmapped", "mapped")


def usb_c_port_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Verify USB-C CC pin-function coverage from repeated pinned native exports."""
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"USB-C port fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint"
    fixtures: dict[UsbCPortFixtureCase, Path] = {
        "connector": fixture_root / "usb-c-port-native/connector.kicad_sch",
        "source-rp-control": fixture_root / "cohort-usb-c-roles/source-rp-control.kicad_sch",
        "sink-rd-control": fixture_root / "cohort-usb-c-roles/sink-rd-control.kicad_sch",
        "vbus-capacitance-control": (
            fixture_root / "usb-c-vbus-capacitance-native/control.kicad_sch"
        ),
        "vbus-capacitance-fault": (fixture_root / "usb-c-vbus-capacitance-native/fault.kicad_sch"),
    }
    source_hashes: dict[UsbCPortFixtureCase, str] = {
        case: digest(path) for case, path in fixtures.items()
    }
    scratch = Path(tempfile.mkdtemp(prefix=f"usb-c-port-{project}-", dir=log.directory.resolve()))
    inputs = scratch / "input"
    inputs.mkdir()
    for case, fixture in fixtures.items():
        source = inputs / f"{case}.kicad_sch"
        shutil.copyfile(fixture, source)
        if digest(source) != source_hashes[case]:
            raise ValueError(f"Synthetic USB-C {case} fixture changed while preparing native input")
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")

    fixture_case_list = " ".join(_FIXTURE_CASES)
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{config.kicad_version}"\n'
        f"for case in {fixture_case_list}; do\n"
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
        "HOME=/tmp/kicad-usb-c-fixtures",
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
        "usb-c-port-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "usb-c-port-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native USB-C fixture command failed: {command.stderr or command.error}")
    log.event(
        "usb-c-port-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_sha256=source_hashes["connector"],
        fixture_source_sha256s=";".join(f"{case}:{source_hashes[case]}" for case in fixtures),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
    if any(
        digest(fixture) != source_hashes[case]
        or digest(inputs / f"{case}.kicad_sch") != source_hashes[case]
        for case, fixture in fixtures.items()
    ):
        raise ValueError("Synthetic USB-C fixture source changed during native export")

    def load_netlist_run(
        fixture_case: UsbCPortFixtureCase, run: NativeRun
    ) -> NativeNetlistRunEvidence:
        netlist_path = output / f"{fixture_case}.{run}.netlist.xml"
        if not netlist_path.is_file():
            raise ValueError(f"Native USB-C fixture omitted {netlist_path.name}")
        parsed = read_netlist(netlist_path)
        normalized = json.dumps(
            parsed.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return NativeNetlistRunEvidence(
            contract=parsed,
            netlist_sha256=digest(netlist_path),
            normalized_sha256=hashlib.sha256(normalized).hexdigest(),
        )

    fixture_evidence: dict[UsbCPortFixtureCase, NativeNetlistFixtureEvidence] = {}
    for fixture_case in _FIXTURE_CASES:
        fixture_evidence[fixture_case] = NativeNetlistFixtureEvidence(
            source=FixtureSourceEvidence(
                path=fixtures[fixture_case], sha256=source_hashes[fixture_case]
            ),
            netlists=NativeRunPair(
                first=load_netlist_run(fixture_case, "first"),
                repeat=load_netlist_run(fixture_case, "repeat"),
            ),
        )
        netlists = fixture_evidence[fixture_case].netlists
        if netlists.first.normalized_sha256 != netlists.repeat.normalized_sha256:
            raise ValueError(
                f"Native USB-C {fixture_case} exports differ after normalization to the typed netlist"
            )

    observed = fixture_evidence["connector"].netlists.first.contract
    expected_functions = {"J1.4": "CC1", "J1.5": "CC2"}
    if observed.pin_functions != expected_functions:
        raise ValueError(
            "Native netlist no longer preserves exact USB-C CC pin functions: "
            f"{observed.pin_functions}"
        )
    if observed.component_symbols != {"J1": "Synthetic:TypeCConnector"}:
        raise ValueError("Native netlist changed the synthetic USB-C connector identity")

    expected_control_symbols: dict[UsbCPortControlFixtureCase, str] = {
        "source-rp-control": "Connector:USB_C_Receptacle",
        "sink-rd-control": "Connector:USB_C_Receptacle",
    }
    for case, expected_symbol in expected_control_symbols.items():
        control = fixture_evidence[case].netlists.first.contract
        if control.pin_functions != expected_functions:
            raise ValueError(
                f"Native USB-C {case} fixture lost its CC pin functions: {control.pin_functions}"
            )
        if control.component_symbols.get("J1") != expected_symbol:
            raise ValueError(f"Native USB-C {case} fixture changed connector symbol identity")
    source_control = fixture_evidence["source-rp-control"].netlists.first.contract
    if (
        set(source_control.components) != {"J1", "R1", "R2"}
        or source_control.dnp_components
        or source_control.component_symbols.get("R1") != "Device:R"
        or source_control.component_symbols.get("R2") != "Device:R"
        or source_control.components.get("R1") is None
        or source_control.components["R1"].value != "56k"
        or source_control.components.get("R2") is None
        or source_control.components["R2"].value != "56k"
        or set(source_control.nets.get("CC1_NET", ())) != {"J1.4", "R1.1"}
        or set(source_control.nets.get("CC2_NET", ())) != {"J1.5", "R2.1"}
        or set(source_control.nets.get("+5V", ())) != {"R1.2", "R2.2"}
    ):
        raise ValueError("Native USB-C source control no longer has its synthetic 56 kΩ Rp paths")
    sink_control = fixture_evidence["sink-rd-control"].netlists.first.contract
    if (
        set(sink_control.components) != {"J1", "R1", "R2"}
        or sink_control.dnp_components
        or sink_control.component_symbols.get("R1") != "Device:R"
        or sink_control.component_symbols.get("R2") != "Device:R"
        or sink_control.components.get("R1") is None
        or sink_control.components["R1"].value != "5.1k"
        or sink_control.components.get("R2") is None
        or sink_control.components["R2"].value != "5.1k"
        or set(sink_control.nets.get("CC1_NET", ())) != {"J1.4", "R1.1"}
        or set(sink_control.nets.get("CC2_NET", ())) != {"J1.5", "R2.1"}
        or set(sink_control.nets.get("GND", ())) != {"R1.2", "R2.2"}
    ):
        raise ValueError("Native USB-C sink control no longer has its synthetic 5.1 kΩ Rd paths")

    capacitance_requirement = UsbCVbusCapacitanceRequirement(
        basis="Synthetic fixture contract with an explicit nominal capacitance window",
        minimum_nf=4500,
        maximum_nf=5000,
        capacitors=(
            UsbCVbusCapacitorRequirement(
                reference="C1",
                symbol="Device:C",
                footprint="Synthetic:C_0603",
                pins=(
                    UsbCNetPinAssignment(pin="C1.1", net="VBUS_PORT"),
                    UsbCNetPinAssignment(pin="C1.2", net="GND"),
                ),
            ),
        ),
    )
    expected_capacitance: dict[UsbCPortFixtureCase, tuple[str, float, str]] = {
        "vbus-capacitance-control": ("PASS", 4700.0, "4.7uF"),
        "vbus-capacitance-fault": ("FAIL", 2200.0, "2.2uF"),
    }
    for case, (expected_status, expected_nf, expected_value) in expected_capacitance.items():
        observed_capacitance = fixture_evidence[case].netlists.first.contract
        if (
            set(observed_capacitance.components) != {"C1"}
            or observed_capacitance.component_symbols != {"C1": "Device:C"}
            or observed_capacitance.components["C1"].value != expected_value
            or observed_capacitance.components["C1"].footprint != "Synthetic:C_0603"
            or set(observed_capacitance.component_pin_numbers.get("C1", ())) != {"1", "2"}
            or set(observed_capacitance.nets.get("VBUS_PORT", ())) != {"C1.1"}
            or set(observed_capacitance.nets.get("GND", ())) != {"C1.2"}
        ):
            raise ValueError(
                f"Native USB-C {case} fixture changed its exact synthetic capacitor map"
            )
        capacitance_check = usb_c_vbus_capacitance_check(
            capacitance_requirement,
            vbus_net="VBUS_PORT",
            ground_net="GND",
            observed=observed_capacitance,
            check_id="usb-c/native-port/vbus-capacitance",
        )
        observed_nf = capacitance_check.observed
        if (
            capacitance_check.status != expected_status
            or observed_nf is None
            or observed_nf != expected_nf
        ):
            raise ValueError(
                f"Native USB-C {case} capacitance result changed: "
                f"{capacitance_check.status}/{capacitance_check.observed}"
            )
        log.event(
            f"usb-c-port-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            fixture_case=case,
            source_sha256=source_hashes[case],
            netlist_sha256=fixture_evidence[case].netlists.first.netlist_sha256,
            repeat_netlist_sha256=fixture_evidence[case].netlists.repeat.netlist_sha256,
            normalized_netlist_sha256=fixture_evidence[case].netlists.first.normalized_sha256,
            repeat_normalized_netlist_sha256=fixture_evidence[
                case
            ].netlists.repeat.normalized_sha256,
            repeatable=str(
                fixture_evidence[case].netlists.first.normalized_sha256
                == fixture_evidence[case].netlists.repeat.normalized_sha256
            ).lower(),
            check_status=capacitance_check.status,
            observed_nf=observed_nf,
            expected_check_status=expected_status,
            detail=capacitance_check.detail,
        )

    analysis = UsbCAnalysis(
        basis="Synthetic exact native netlist comparison for USB-C roster fault/control coverage",
        ports=(
            UsbCPortRequirement(
                id="native-port",
                basis="Synthetic USB-C connector role map control",
                connector="J1",
                role="source",
                cc1=UsbCcLineRequirement(
                    connector_pin="J1.4",
                    net="CC1_NET",
                    attachment=UsbCcResistorAttachment(
                        kind="resistor",
                        behavior="rp",
                        reference="R1",
                        rail_net="+5V",
                        minimum_ohms=50_000,
                        maximum_ohms=60_000,
                    ),
                ),
                cc2=UsbCcLineRequirement(
                    connector_pin="J1.5",
                    net="CC2_NET",
                    attachment=UsbCcResistorAttachment(
                        kind="resistor",
                        behavior="rp",
                        reference="R2",
                        rail_net="+5V",
                        minimum_ohms=50_000,
                        maximum_ohms=60_000,
                    ),
                ),
                vbus_net="VBUS_PORT",
                vbus_pins=(
                    UsbCNetPinAssignment(pin="J1.1", net="VBUS_PORT"),
                    UsbCNetPinAssignment(pin="U1.1", net="VBUS_SYSTEM"),
                ),
                ground_net="GND",
                ground_pins=("J1.2", "U1.2"),
                vbus_capacitance=AnalysisNotApplicable(
                    mode="not_applicable",
                    reason="Native roster fixture does not assess port-side capacitance.",
                ),
                source_rail="+5V",
                protection=AnalysisNotApplicable(
                    mode="not_applicable",
                    reason="Native roster fixture tests membership only.",
                ),
            ),
        ),
    )
    reports: dict[UsbCPortReviewCase, DesignLintReport] = {}
    for case, context in zip(
        _ROSTER_SCENARIOS,
        (
            UsbCPortRosterContext(state="not_configured"),
            UsbCPortRosterContext(state="required", analysis=analysis),
        ),
        strict=True,
    ):
        project_id = f"synthetic-usb-c-port-{case}"
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=project_id,
            observed=observed,
            netlist_sha256=fixture_evidence["connector"].netlists.first.netlist_sha256,
        )
        reports[case] = evaluate(
            project_id,
            coach,
            DesignLintPolicy(),
            usb_c_port_roster=context,
        )

    unmapped = reports["unmapped"]
    cc_findings = tuple(
        item for item in unmapped.findings if item.rule_id == "bus.usb_c_unreviewed_port"
    )
    if unmapped.status != "REVIEW" or tuple(item.subject for item in cc_findings) != (
        "J1: USB-C role-map coverage",
    ):
        raise ValueError("Unmapped native USB-C port no longer produces the expected review hint")
    mapped = reports["mapped"]
    if mapped.status != "PASS" or mapped.findings:
        raise ValueError("The exact USB-C role-map control no longer suppresses review findings")

    for case in _CONTROL_FIXTURE_CASES:
        control = fixture_evidence[case].netlists.first.contract
        project_id = f"synthetic-usb-c-port-{case}-unmapped"
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=project_id,
            observed=control,
            netlist_sha256=fixture_evidence[case].netlists.first.netlist_sha256,
        )
        report = evaluate(
            project_id,
            coach,
            DesignLintPolicy(),
            usb_c_port_roster=UsbCPortRosterContext(state="not_configured"),
        )
        findings = tuple(
            item for item in report.findings if item.rule_id == "bus.usb_c_unreviewed_port"
        )
        if report.status != "REVIEW" or tuple(item.subject for item in findings) != (
            "J1: USB-C role-map coverage",
        ):
            raise ValueError(
                f"Unmapped native USB-C {case} no longer produces the expected role-map prompt"
            )
        reports[case] = report

    for case, report in reports.items():
        if case == "unmapped" or case == "mapped":
            fixture_case: UsbCPortFixtureCase = "connector"
        else:
            fixture_case = case
        observed_case = fixture_evidence[fixture_case].netlists.first.contract
        log.event(
            f"usb-c-port-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            fixture_case=fixture_case,
            source_sha256=source_hashes[fixture_case],
            netlist_sha256=fixture_evidence[fixture_case].netlists.first.netlist_sha256,
            repeat_netlist_sha256=fixture_evidence[fixture_case].netlists.repeat.netlist_sha256,
            normalized_netlist_sha256=fixture_evidence[
                fixture_case
            ].netlists.first.normalized_sha256,
            repeat_normalized_netlist_sha256=fixture_evidence[
                fixture_case
            ].netlists.repeat.normalized_sha256,
            lint_status=report.status,
            findings=";".join(item.subject for item in report.findings) or "none",
            cc_pin_functions=";".join(
                f"{pin}={name}" for pin, name in sorted(observed_case.pin_functions.items())
            ),
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

"""Release electrical evidence rejects stale, incomplete and relabeled receipts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.discovery import load_registry
from kicad_tooling.hwrepo.electrical_evidence import required_projects
from kicad_tooling.hwrepo.electrical_runner import analyze
from kicad_tooling.hwrepo.evidence import digest, source_state
from kicad_tooling.hwrepo.models import (
    ControlBiasResistorRequirement,
    ControlInputsAnalysis,
    ControlLocalBiasRequirement,
    ControlPinRequirement,
    ControlSignalRequirement,
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    PinConnectivityAnalysis,
    PinRelationshipRule,
    ReleaseClass,
    ReleaseEvidence,
    ReleaseManifest,
    ReleaseStatus,
    ValidationSummary,
)
from kicad_tooling.hwrepo.releasing import reference, retained_paths
from tests.electrical_can_support import can_split_termination_requirement
from tests.electrical_evidence_support import (
    ElectricalEvidenceWorkspace,
    reject_omitted_electrical_checks,
)
from tests.electrical_evidence_support import (
    electrical_evidence_workspace as _electrical_evidence_workspace_fixture,  # noqa: F401
)
from tests.electrical_i2c_support import i2c_pullup_window_requirement
from tests.electrical_power_connectivity_support import power_connectivity_requirement
from tests.electrical_rs485_support import rs485_requirement
from tests.electrical_serial_support import serial_peer_requirement
from tests.electrical_simulation_support import (
    ISLAND,
    NA,
    PROJECT,
)
from tests.electrical_spi_support import spi_requirement
from tests.electrical_usb_c_support import usb_c_requirement

pytestmark = [pytest.mark.evidence_lint, pytest.mark.slow, pytest.mark.template_checkout]


def test_exact_saved_requirements_logs_and_waveforms_pass_without_a_simulator(
    electrical_evidence_workspace: ElectricalEvidenceWorkspace,
) -> None:
    electrical_evidence_workspace.simulator.unlink()
    electrical_evidence_workspace.verify()
    result = json.loads(electrical_evidence_workspace.path.read_text())
    assert result["source"]["commit"] == electrical_evidence_workspace.source.commit
    candidate = ReleaseManifest(
        release_id="test",
        release_class=ReleaseClass.ENGINEERING_REVIEW,
        status=ReleaseStatus.CANDIDATE,
        source_commit=electrical_evidence_workspace.source.commit or "",
        toolchain_id="kicad-10.0.0",
        projects=(PROJECT,),
        libraries=(),
        interfaces=(),
        artifacts=(),
        evidence=ReleaseEvidence(
            portable=electrical_evidence_workspace.native,
            native={},
            electrical={
                PROJECT: reference(
                    electrical_evidence_workspace.root, electrical_evidence_workspace.path
                )
            },
        ),
    )
    retained = retained_paths(electrical_evidence_workspace.root, candidate)
    assert (
        electrical_evidence_workspace.path.relative_to(
            electrical_evidence_workspace.root
        ).as_posix()
        in retained
    )
    assert (electrical_evidence_workspace.output / "startup/waveforms.raw").relative_to(
        electrical_evidence_workspace.root
    ).as_posix() in retained


def test_saved_pin_bus_serial_rs485_and_power_maps_are_rechecked_and_cannot_be_omitted(
    electrical_evidence_workspace: ElectricalEvidenceWorkspace,
) -> None:
    requirement = PinConnectivityAnalysis(
        basis="Synthetic independently reviewed pin relationship",
        rules=(
            PinRelationshipRule(
                id="shared-source",
                basis="Two selected pins share the synthetic source net",
                topology="common_net",
                pins=("R1.1", "R3.1"),
                net="PILOT_A",
            ),
        ),
    )
    write_model(
        electrical_evidence_workspace.root / ISLAND / "tests/electrical.json",
        electrical_evidence_workspace.contract.model_copy(
            update={
                "pin_connectivity": requirement,
                "i2c_pullups": i2c_pullup_window_requirement(
                    "R4",
                    "R5",
                    maximum_per_resistor_tolerance_percent=5.0,
                    resistor_tolerance_basis=(
                        "Synthetic maximum tolerance bound for each series pull-up resistor"
                    ),
                ),
                "can_termination": can_split_termination_requirement("R7", "R8"),
                "usb_c": usb_c_requirement(
                    connector="J9",
                    board_component="U9",
                    protection_reference="D9",
                    resistor_references=("R9", "R10"),
                    vbus_path=True,
                ),
                "spi": spi_requirement(
                    device2_miso="not_present",
                    controller_reference="U10",
                    device_references=("U11", "U12"),
                    device2_symbol="Synthetic:SpiWriteOnly",
                ),
                "serial_peers": serial_peer_requirement(
                    endpoint_reference="U30", peer_reference="U31"
                ),
                "rs485": rs485_requirement(),
                "control_inputs": ControlInputsAnalysis(
                    basis="Synthetic control-signal requirements",
                    signals=(
                        ControlSignalRequirement(
                            id="factory-reset",
                            basis="Synthetic controller reset input and one approved driver",
                            signal_net="RESET_TEST",
                            driver_policy="single",
                            endpoints=(
                                ControlPinRequirement(
                                    role="controlled_input",
                                    reference="U50",
                                    symbol="Synthetic:ControlInput",
                                    footprint="Package_QFN:QFN-16",
                                    pin="U50.1",
                                    electrical_type="input",
                                ),
                                ControlPinRequirement(
                                    role="approved_driver",
                                    reference="U51",
                                    symbol="Synthetic:ControlOutput",
                                    footprint="Package_SO:SOIC-8",
                                    pin="U51.1",
                                    electrical_type="output",
                                ),
                                ControlPinRequirement(
                                    role="external_interface",
                                    reference="J50",
                                    symbol="Synthetic:ControlHeader",
                                    footprint="Connector:Dsub-9_Male",
                                    pin="J50.9",
                                    electrical_type="passive",
                                ),
                            ),
                            bias=ControlLocalBiasRequirement(
                                mode="local",
                                basis="Synthetic 10 kΩ reset pull-up requirement",
                                resistors=(
                                    ControlBiasResistorRequirement(
                                        reference="R50",
                                        symbol="Device:R",
                                        footprint="Resistor_SMD:R_0603_1608Metric",
                                        signal_net="RESET_TEST",
                                        bias_net="+3V3",
                                        direction="pull_up",
                                        minimum_ohms=9_000,
                                        maximum_ohms=11_000,
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
                "power_connectivity": power_connectivity_requirement(),
            }
        ),
    )
    native_directory = electrical_evidence_workspace.root / "build/native/controller"
    netlist = native_directory / "netlist.xml"
    fixture_path = (
        Path(__file__).parent / "fixtures/electrical/release-contract-evidence/netlist.xml"
    )
    netlist.write_bytes(fixture_path.read_bytes())
    summary_path = native_directory / "summary.json"
    summary = read_model(summary_path, ValidationSummary)
    write_model(
        summary_path,
        summary.model_copy(
            update={
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "netlist.xml": digest(netlist),
                }
            }
        ),
    )
    electrical_evidence_workspace.native = reference(
        electrical_evidence_workspace.root, summary_path
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(electrical_evidence_workspace.root),
            "-c",
            "user.name=Synthetic fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qam",
            "Synthetic pin relationship",
        ),
        check=True,
        capture_output=True,
    )
    electrical_evidence_workspace.source = source_state(electrical_evidence_workspace.root)
    electrical_evidence_workspace.output = (
        electrical_evidence_workspace.root / "build/electrical/pin-relationship"
    )
    result = analyze(
        electrical_evidence_workspace.root,
        PROJECT,
        electrical_evidence_workspace.output,
        native_summary=summary_path,
        ngspice=str(electrical_evidence_workspace.simulator),
    )
    assert result.status == "PASS", result
    electrical_evidence_workspace.path = electrical_evidence_workspace.output / "electrical.json"
    electrical_evidence_workspace.verify()
    report = read_model(electrical_evidence_workspace.path, ElectricalAnalysisReport)
    checks = {item.id: item for item in report.checks}
    assert checks["can-termination/fieldbus/local"].status == "PASS"
    assert checks["can-termination/fieldbus/local/midpoint-capacitor"].status == "PASS"
    assert checks["usb-c/host-port/vbus-path/input-path"].status == "PASS"
    assert checks["i2c-pullup/series-bus/sda/voltage-compatibility"].status == "PASS"
    assert checks["i2c-pullup/series-bus/scl/voltage-compatibility"].status == "PASS"
    assert (
        checks["i2c-pullup/series-bus/sda/electrical-window/minimum-sink-resistance"].status
        == "PASS"
    )
    assert (
        checks["i2c-pullup/series-bus/sda/electrical-window/maximum-rise-resistance"].status
        == "PASS"
    )
    reject_omitted_electrical_checks(
        electrical_evidence_workspace,
        (
            "pin-connectivity/shared-source",
            "i2c-pullup/series-bus/sda/series/sda-chain",
            "i2c-pullup/series-bus/sda",
            "i2c-pullup/series-bus/sda/voltage-compatibility",
            "i2c-pullup/series-bus/sda/electrical-window/minimum-sink-resistance",
            "i2c-pullup/series-bus/sda/electrical-window/maximum-rise-resistance",
            "i2c-pullup/series-bus/scl/voltage-compatibility",
            "i2c-pullup/series-bus/scl/electrical-window/minimum-sink-resistance",
            "i2c-pullup/series-bus/scl/electrical-window/maximum-rise-resistance",
            "can-termination/fieldbus/local",
            "can-termination/fieldbus/local/midpoint-capacitor",
            "usb-c/host-port/connector-pins",
            "usb-c/host-port/cc1-attachment",
            "usb-c/host-port/vbus-path/input-path",
            "usb-c/host-port/protection/D9",
            "spi/control/device/sensor/route/sck",
            "spi/control/device/memory/route/miso",
            "serial/console-link/route/a_tx_to_b_rx",
            "rs485/fieldbus/pair/shared/membership",
            "rs485/fieldbus/pair/shared/termination/local-end",
            "rs485/fieldbus/pair/shared/bias",
            "control-inputs/factory-reset/endpoints",
            "control-inputs/factory-reset/drivers",
            "control-inputs/factory-reset/bias",
            "power-connectivity/supply/source/approved-inputs",
            "power-connectivity/supply/load/load",
        ),
    )


def test_relabeling_and_rehashing_cannot_hide_missing_or_failed_measurements(
    electrical_evidence_workspace: ElectricalEvidenceWorkspace,
) -> None:
    original = electrical_evidence_workspace.path.read_bytes()
    for change in ("checks", "commands", "inventory", "source", "project", "inputs"):
        value = json.loads(original)
        if change == "checks":
            value["checks"] = []
        elif change == "commands":
            value["commands"].pop("startup")
        elif change == "inventory":
            value["artifacts_sha256"].pop("startup/waveforms.raw")
        elif change == "source":
            value["source"] = None
        elif change == "project":
            value["project_id"] = "another-board"
        else:
            value["input_sha256"] = {}
        electrical_evidence_workspace.path.write_text(json.dumps(value))
        with pytest.raises(ValueError):
            electrical_evidence_workspace.verify()
    electrical_evidence_workspace.path.write_bytes(original)
    command = electrical_evidence_workspace.output / "startup/ngspice.command.json"
    value = json.loads(command.read_text())
    value["stdout"] = "check0 = 9000\n"
    command.write_text(json.dumps(value))
    report = json.loads(original)
    report["commands"]["startup"] = value
    report["artifacts_sha256"]["startup/ngspice.command.json"] = digest(command)
    electrical_evidence_workspace.path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="checks fail"):
        electrical_evidence_workspace.verify()


def test_changed_model_waveform_or_case_deck_cannot_reuse_receipt(
    electrical_evidence_workspace: ElectricalEvidenceWorkspace,
) -> None:
    for name in ("startup/waveforms.raw", "startup/simulation.cir"):
        path = electrical_evidence_workspace.output / name
        original = path.read_bytes()
        path.write_bytes(original + b"\nchanged")
        with pytest.raises(ValueError):
            electrical_evidence_workspace.verify()
        path.write_bytes(original)
    model = electrical_evidence_workspace.root / ISLAND / "tests/electrical/startup.cir"
    model.write_bytes(model.read_bytes() + b"\n* changed\n")
    with pytest.raises(ValueError, match="stale"):
        electrical_evidence_workspace.verify()


def test_declared_contracts_gate_review_and_build_releases_require_applicability(
    electrical_evidence_workspace: ElectricalEvidenceWorkspace,
) -> None:
    projects = tuple(
        p for p in load_registry(electrical_evidence_workspace.root).projects if p.id == PROJECT
    )
    assert required_projects(
        electrical_evidence_workspace.root, projects, ReleaseClass.ENGINEERING_REVIEW
    ) == (PROJECT,)
    path = electrical_evidence_workspace.root / ISLAND / "tests/contract.json"
    value = json.loads(path.read_text())
    value.pop("electrical")
    path.write_text(json.dumps(value))
    assert (
        required_projects(
            electrical_evidence_workspace.root, projects, ReleaseClass.ENGINEERING_REVIEW
        )
        == ()
    )
    with pytest.raises(ValueError, match="build releases require"):
        required_projects(electrical_evidence_workspace.root, projects, ReleaseClass.PROTOTYPE)


def test_all_not_applicable_still_requires_bound_evidence(
    electrical_evidence_workspace: ElectricalEvidenceWorkspace,
) -> None:
    path = electrical_evidence_workspace.root / ISLAND / "tests/electrical.json"
    contract = read_model(path, ElectricalAnalysisContract).model_copy(update={"power": NA})
    write_model(path, contract)
    subprocess.run(
        (
            "git",
            "-C",
            str(electrical_evidence_workspace.root),
            "-c",
            "user.name=Synthetic fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qam",
            "Synthetic applicability",
        ),
        check=True,
        capture_output=True,
    )
    electrical_evidence_workspace.source = source_state(electrical_evidence_workspace.root)
    electrical_evidence_workspace.output = (
        electrical_evidence_workspace.root / "build/electrical/not-applicable"
    )
    result = analyze(
        electrical_evidence_workspace.root,
        PROJECT,
        electrical_evidence_workspace.output,
        ngspice="missing-simulator",
    )
    assert result.status == "PASS"
    assert result.commands == {}
    electrical_evidence_workspace.path = electrical_evidence_workspace.output / "electrical.json"
    electrical_evidence_workspace.verify()

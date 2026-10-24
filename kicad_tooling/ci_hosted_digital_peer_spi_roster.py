"""Verify explicit SPI participant roster coverage and controls."""

from __future__ import annotations

from .ci_hosted_digital_peer_context import DigitalPeerFixtureContext
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
)
from .hwrepo.spi_models import (
    SpiAnalysis,
    SpiBusRequirement,
    SpiControllerRequirement,
    SpiDeviceRequirement,
    SpiMisoConnectedRequirement,
    SpiPinNetRequirement,
)
from .hwrepo.spi_participants import SpiRosterContext


def verify_spi_roster_coverage(ctx: DigitalPeerFixtureContext):
    """Verify explicit SPI participant roster coverage and controls."""
    basis = "Synthetic exact native netlist comparison for roster fault/control coverage"
    controller = SpiControllerRequirement(
        reference="U1",
        symbol="Synthetic:SPI_Node",
        footprint="Synthetic:QFN",
        sck=SpiPinNetRequirement(pin="U1.1", net="SPI_SCK"),
        mosi=SpiPinNetRequirement(pin="U1.2", net="SPI_MOSI"),
        miso=SpiMisoConnectedRequirement(mode="connected", pin="U1.3", net="SPI_MISO"),
        chip_selects=(SpiPinNetRequirement(pin="U1.4", net="SPI_CS"),),
    )
    device = SpiDeviceRequirement(
        id="PERIPHERAL",
        reference="U2",
        symbol="Synthetic:SPI_Node",
        footprint="Synthetic:QFN",
        sck=SpiPinNetRequirement(pin="U2.1", net="SPI_SCK"),
        mosi=SpiPinNetRequirement(pin="U2.2", net="SPI_MOSI"),
        miso=SpiMisoConnectedRequirement(mode="connected", pin="U2.3", net="SPI_MISO"),
        chip_select=SpiPinNetRequirement(pin="U2.4", net="SPI_CS"),
    )
    roster = SpiAnalysis(
        basis=basis,
        buses=(
            SpiBusRequirement(id="MAIN", basis=basis, controller=controller, devices=(device,)),
        ),
    )
    reports: dict[str, DesignLintReport] = {}
    for case, context in (
        ("unrostered", SpiRosterContext(state="not_configured")),
        ("rostered", SpiRosterContext(state="required", analysis=roster)),
    ):
        project_id = f"synthetic-spi-participants-{case}"
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=project_id,
            observed=ctx.observed,
            netlist_sha256=ctx.hashes["multi-device"]["first"],
        )
        reports[case] = evaluate(project_id, coach, DesignLintPolicy(), spi_roster=context)
    unrostered = reports["unrostered"]
    spi_findings = tuple(
        item for item in unrostered.findings if item.rule_id == "bus.spi_unmapped_participant"
    )
    if unrostered.status != "REVIEW" or {item.subject for item in spi_findings} != {
        "U1: SPI roster coverage",
        "U2: SPI roster coverage",
    }:
        raise ValueError(
            "Unrostered native SPI participants no longer produce exact review findings"
        )
    if any(item.evidence["SPI_roster_state"] != ("not_configured",) for item in spi_findings):
        raise ValueError("Native SPI findings lost the unconfigured-roster evidence")
    rostered = reports["rostered"]
    rostered_spi_findings = tuple(
        item for item in rostered.findings if item.rule_id == "bus.spi_unmapped_participant"
    )
    if rostered_spi_findings:
        subjects = ";".join(item.subject for item in rostered_spi_findings)
        raise ValueError(f"The exact SPI roster control still reports candidates: {subjects}")
    for case, report in reports.items():
        case_spi_findings = tuple(
            item for item in report.findings if item.rule_id == "bus.spi_unmapped_participant"
        )
        ctx.log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            image=ctx.pinned,
            source_sha256=ctx.source_hash,
            netlist_sha256=ctx.hashes["multi-device"]["first"],
            repeat_netlist_sha256=ctx.hashes["multi-device"]["repeat"],
            normalized_netlist_sha256=ctx.normalized_hashes["multi-device"]["first"],
            repeat_normalized_netlist_sha256=ctx.normalized_hashes["multi-device"]["repeat"],
            lint_status=report.status,
            findings=";".join(item.subject for item in report.findings) or "none",
            spi_findings=";".join(item.subject for item in case_spi_findings) or "none",
            pin_functions=";".join(
                f"{pin}={name}" for (pin, name) in sorted(ctx.observed.pin_functions.items())
            ),
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )


def verify_spi_composite_alias_coverage(ctx: DigitalPeerFixtureContext) -> None:
    """Verify exact slash-separated SPI aliases survive native export and roster review."""
    from .hwrepo.spi_models import SpiDeviceRequirement

    observed = ctx.contracts["combo-device"]["first"]
    expected_functions = {
        "U1.1": "SCL/SPC",
        "U1.2": "SDA/SDI/SDO",
        "U1.3": "SDO/SA0",
        "U1.4": "CS",
    }
    if observed.pin_functions != expected_functions:
        raise ValueError(f"Native SPI combo aliases changed: {observed.pin_functions}")
    if observed.component_symbols != {"U1": "Synthetic:Combo_SPI_Node"}:
        raise ValueError("Native SPI combo fixture changed its synthetic component identity")
    if (
        ctx.normalized_hashes["combo-device"]["first"]
        != ctx.normalized_hashes["combo-device"]["repeat"]
    ):
        raise ValueError("Native SPI combo fixture differs after normalized repeat exports")

    basis = "Synthetic exact roster for a dual I2C/SPI symbol"
    controller = SpiControllerRequirement(
        reference="U0",
        symbol="Synthetic:SPI_Controller",
        footprint="Synthetic:QFN",
        sck=SpiPinNetRequirement(pin="U0.1", net="SENSOR_CLOCK"),
        mosi=SpiPinNetRequirement(pin="U0.2", net="SENSOR_DATA"),
        miso=SpiMisoConnectedRequirement(mode="connected", pin="U0.3", net="SENSOR_OUT"),
        chip_selects=(SpiPinNetRequirement(pin="U0.4", net="SENSOR_CS"),),
    )
    device = SpiDeviceRequirement(
        id="combo_sensor",
        reference="U1",
        symbol="Synthetic:Combo_SPI_Node",
        footprint="Synthetic:QFN",
        sck=SpiPinNetRequirement(pin="U1.1", net="SENSOR_CLOCK"),
        mosi=SpiPinNetRequirement(pin="U1.2", net="SENSOR_DATA"),
        miso=SpiMisoConnectedRequirement(mode="connected", pin="U1.3", net="SENSOR_OUT"),
        chip_select=SpiPinNetRequirement(pin="U1.4", net="SENSOR_CS"),
    )
    roster = SpiAnalysis(
        basis=basis,
        buses=(
            SpiBusRequirement(
                id="SENSOR_BUS",
                basis=basis,
                controller=controller,
                devices=(device,),
            ),
        ),
    )
    cases = (
        ("composite-unrostered", SpiRosterContext(state="not_configured"), "REVIEW"),
        (
            "composite-rostered",
            SpiRosterContext(state="required", analysis=roster),
            "PASS",
        ),
    )
    for case, context, expected_status in cases:
        report = evaluate(
            f"synthetic-spi-composite-{case}",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-spi-composite-{case}",
                observed=observed,
                netlist_sha256=ctx.hashes["combo-device"]["first"],
            ),
            DesignLintPolicy(),
            spi_roster=context,
        )
        findings = tuple(
            item for item in report.findings if item.rule_id == "bus.spi_unmapped_participant"
        )
        expected_findings = ("U1: SPI roster coverage",) if case == "composite-unrostered" else ()
        observed_subjects = tuple(item.subject for item in findings)
        if report.status != expected_status or observed_subjects != expected_findings:
            raise ValueError(f"Native SPI composite roster result changed for {case}")
        if findings and (
            findings[0].evidence["SCK_pins"] != ("U1.1",)
            or findings[0].evidence["input_data_pins"] != ("U1.2",)
            or findings[0].evidence["output_data_pins"] != ("U1.2", "U1.3")
            or findings[0].evidence["chip_select_pins"] != ("U1.4",)
        ):
            raise ValueError("Native SPI combo finding lost a recognized pin-function alias")
        ctx.log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            image=ctx.pinned,
            source_sha256=ctx.combo_spi_source_hash,
            netlist_sha256=ctx.hashes["combo-device"]["first"],
            repeat_netlist_sha256=ctx.hashes["combo-device"]["repeat"],
            normalized_netlist_sha256=ctx.normalized_hashes["combo-device"]["first"],
            repeat_normalized_netlist_sha256=ctx.normalized_hashes["combo-device"]["repeat"],
            lint_status=report.status,
            findings=";".join(item.subject for item in findings) or "none",
            pin_functions=";".join(
                f"{pin}={name}" for (pin, name) in sorted(observed.pin_functions.items())
            ),
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )

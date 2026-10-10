"""Verify explicit SPI participant roster coverage and controls."""

from __future__ import annotations

from .ci_hosted_digital_peer_context import DigitalPeerFixtureContext
from .hwrepo.design_lint import evaluate
from .hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
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
    if rostered.status != "PASS" or rostered.findings:
        raise ValueError("The exact SPI roster control no longer suppresses all review findings")
    for case, report in reports.items():
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
            pin_functions=";".join(
                f"{pin}={name}" for (pin, name) in sorted(ctx.observed.pin_functions.items())
            ),
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )

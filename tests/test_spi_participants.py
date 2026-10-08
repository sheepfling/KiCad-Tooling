"""Synthetic SPI roster-coverage hints and project rule decisions."""

from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.design_lint import _spi_roster_context, evaluate
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    AnalysisPending,
    ComponentContract,
    ComponentIdentity,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ElectricalAnalysisContract,
    IgnoredChecks,
    NetlistContract,
    ProjectConfig,
    ProjectKind,
    SchematicValidationContract,
    SpiAnalysis,
    SpiBusRequirement,
    SpiControllerRequirement,
    SpiDeviceRequirement,
    SpiMisoConnectedRequirement,
    SpiPinNetRequirement,
)
from kicad_tooling.hwrepo.spi_participants import SpiRosterContext, unmapped_spi_participants

_NETLIST_SHA256 = "a" * 64
_CONTRACT_SHA256 = "b" * 64


def spi_netlist(
    *,
    dnp: tuple[str, ...] = (),
    include_connector: bool = False,
    partial_ic: bool = False,
) -> NetlistContract:
    components = {
        "U1": ComponentContract(value="Synthetic controller", footprint="Synthetic:QFN"),
        "U2": ComponentContract(value="Synthetic peripheral", footprint="Synthetic:SOIC"),
        "U3": ComponentContract(value="Synthetic second peripheral", footprint="Synthetic:SOIC"),
        "U4": ComponentContract(value="Synthetic non-SPI IC", footprint="Synthetic:SOIC"),
    }
    symbols = {reference: f"Synthetic:{reference}" for reference in components}
    functions = {
        "U1.1": "SCK",
        "U1.2": "MOSI",
        "U1.3": "MISO",
        "U1.4": "CS",
        "U1.5": "CS",
        "U2.1": "SCK",
        "U2.2": "MOSI",
        "U2.3": "MISO",
        "U2.4": "CS",
        "U3.1": "SPI1_SCLK",
        "U3.2": "SPI1_COPI",
        "U3.3": "SPI1_CIPO",
        "U3.4": "SPI1_NSS",
        "U4.1": "SCK",
        "U4.2": "MOSI",
    }
    nets: dict[str, tuple[str, ...]] = {
        "SPI_SCK": ("U1.1", "U2.1", "U3.1", "U4.1"),
        "SPI_MOSI": ("U1.2", "U2.2", "U3.2", "U4.2"),
        "SPI_MISO": ("U1.3", "U2.3", "U3.3"),
        "SPI_CS0": ("U1.4", "U2.4"),
        "SPI_CS1": ("U1.5", "U3.4"),
    }
    if partial_ic:
        functions.pop("U4.2")
    if include_connector:
        components["J1"] = ComponentContract(
            value="Synthetic connector", footprint="Synthetic:Header"
        )
        symbols["J1"] = "Synthetic:Connector"
        functions.update({"J1.1": "SCK", "J1.2": "MOSI", "J1.3": "CS"})
        nets["SPI_SCK"] = (*nets["SPI_SCK"], "J1.1")
        nets["SPI_MOSI"] = (*nets["SPI_MOSI"], "J1.2")
        nets["SPI_CS0"] = (*nets["SPI_CS0"], "J1.3")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=functions,
        component_pin_numbers={
            reference: tuple(
                pin.rsplit(".", 1)[1] for pin in functions if pin.startswith(f"{reference}.")
            )
            for reference in components
        },
    )


def spi_roster(*, device_references: tuple[str, ...] = ("U2", "U3")) -> SpiAnalysis:
    controller = SpiControllerRequirement(
        reference="U1",
        symbol="Synthetic:U1",
        footprint="Synthetic:QFN",
        sck=SpiPinNetRequirement(pin="U1.1", net="SPI_SCK"),
        mosi=SpiPinNetRequirement(pin="U1.2", net="SPI_MOSI"),
        miso=SpiMisoConnectedRequirement(mode="connected", pin="U1.3", net="SPI_MISO"),
        chip_selects=tuple(
            SpiPinNetRequirement(pin=f"U1.{4 + index}", net=f"SPI_CS{index}")
            for index, _reference in enumerate(device_references)
        ),
    )
    devices = tuple(
        SpiDeviceRequirement(
            id=f"device_{index}",
            reference=reference,
            symbol=f"Synthetic:{reference}",
            footprint="Synthetic:SOIC",
            sck=SpiPinNetRequirement(pin=f"{reference}.1", net="SPI_SCK"),
            mosi=SpiPinNetRequirement(pin=f"{reference}.2", net="SPI_MOSI"),
            miso=SpiMisoConnectedRequirement(
                mode="connected", pin=f"{reference}.3", net="SPI_MISO"
            ),
            chip_select=SpiPinNetRequirement(pin=f"{reference}.4", net=f"SPI_CS{index}"),
        )
        for index, reference in enumerate(device_references)
    )
    return SpiAnalysis(
        basis="Synthetic independently authored controller and device roster",
        buses=(
            SpiBusRequirement(
                id="MAIN",
                basis="Synthetic SPI roster fixture",
                controller=controller,
                devices=devices,
            ),
        ),
    )


def coach(observed: NetlistContract, netlist_sha256: str = _NETLIST_SHA256) -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-spi-roster",
        observed=observed,
        netlist_sha256=netlist_sha256,
    )


def test_unlisted_participant_is_order_stable_and_roster_entry_clears_it() -> None:
    source = spi_netlist()
    rule_id = "bus.spi_unmapped_participant"
    omitted_device_roster = spi_roster(device_references=("U2",))
    complete_roster = spi_roster()

    def lint(netlist: NetlistContract, analysis: SpiAnalysis) -> tuple[str, str, DesignLintReport]:
        netlist_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
        roster_hash = hashlib.sha256(analysis.model_dump_json().encode("utf-8")).hexdigest()
        context = SpiRosterContext(
            state="required",
            analysis=analysis,
            source_path="projects/synthetic-spi-roster/electrical.json",
            source_sha256=roster_hash,
        )
        report = evaluate(
            "synthetic-spi-roster",
            coach(netlist, netlist_hash),
            DesignLintPolicy(),
            spi_roster=context,
        )
        return netlist_hash, roster_hash, report

    source_hash, roster_hash, original = lint(source, omitted_device_roster)
    assert original.netlist_sha256 == source_hash
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == rule_id
    }
    assert tuple(original_findings) == ("U3: SPI roster coverage",)
    original_finding = original_findings["U3: SPI roster coverage"]
    assert original_finding[1]["electrical_contract_sha256"] == (roster_hash,)

    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered_hash, reordered_roster_hash, reordered = lint(reordered_source, omitted_device_roster)
    assert source_hash != reordered_hash
    assert roster_hash == reordered_roster_hash
    assert reordered.netlist_sha256 == reordered_hash
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == rule_id
    }
    assert reordered_findings == original_findings

    mapped_hash, mapped_roster_hash, mapped = lint(source, complete_roster)
    assert mapped_hash == source_hash
    assert mapped_roster_hash != roster_hash
    assert rule_id not in {item.rule_id for item in mapped.findings}


def test_unmapped_spi_ic_without_roster_is_review_candidate() -> None:
    report = evaluate(
        "synthetic-spi-roster",
        coach(spi_netlist()),
        DesignLintPolicy(),
    )
    findings = [item for item in report.findings if item.rule_id == "bus.spi_unmapped_participant"]
    assert report.status == "REVIEW"
    assert {item.subject for item in findings} == {
        "U1: SPI roster coverage",
        "U2: SPI roster coverage",
        "U3: SPI roster coverage",
    }
    assert "no configured project SPI device map" in findings[0].message
    assert findings[2].evidence["SCK_pins"] == ("U3.1",)
    assert findings[2].evidence["input_data_pins"] == ("U3.2",)
    assert findings[2].evidence["output_data_pins"] == ("U3.3",)
    assert findings[2].evidence["chip_select_pins"] == ("U3.4",)


def test_unlisted_spi_peer_is_found_when_roster_covers_another_device() -> None:
    context = SpiRosterContext(
        state="required",
        analysis=spi_roster(device_references=("U2",)),
        source_path="projects/synthetic-spi-roster/electrical.json",
        source_sha256=_CONTRACT_SHA256,
    )
    report = evaluate(
        "synthetic-spi-roster",
        coach(spi_netlist()),
        DesignLintPolicy(),
        spi_roster=context,
    )
    findings = [item for item in report.findings if item.rule_id == "bus.spi_unmapped_participant"]
    assert tuple(item.subject for item in findings) == ("U3: SPI roster coverage",)
    finding = findings[0]
    assert "not listed in the project SPI device map" in finding.message
    assert finding.evidence["electrical_contract_path"] == (
        "projects/synthetic-spi-roster/electrical.json",
    )
    assert finding.evidence["electrical_contract_sha256"] == (_CONTRACT_SHA256,)


def test_rostered_spi_device_and_controller_are_suppressed() -> None:
    report = evaluate(
        "synthetic-spi-roster",
        coach(spi_netlist()),
        DesignLintPolicy(),
        spi_roster=SpiRosterContext(state="required", analysis=spi_roster()),
    )
    assert not any(item.rule_id == "bus.spi_unmapped_participant" for item in report.findings)


def test_inspection_context_loads_and_hashes_the_project_electrical_contract() -> None:
    with TemporaryDirectory(prefix="synthetic-spi-roster-") as temporary:
        root = Path(temporary).resolve()
        contract_path = root / "projects/synthetic-spi-roster/electrical.json"
        contract = ElectricalAnalysisContract(
            project_id="synthetic-spi-roster",
            ngspice_version="synthetic",
            grounding=AnalysisPending(reason="Synthetic grounding review pending."),
            power=AnalysisPending(reason="Synthetic power review pending."),
            high_frequency=AnalysisPending(reason="Synthetic frequency review pending."),
            spi=spi_roster(device_references=("U2",)),
        )
        contract_path.parent.mkdir(parents=True)
        write_model(contract_path, contract)
        source_sha256 = digest(contract_path)
        config = ProjectConfig(
            schema_version="1",
            kind=ProjectKind.SCHEMATIC,
            assurance_profile="development",
            not_for_manufacture=True,
            project_id="synthetic-spi-roster",
            component_identity=ComponentIdentity(required=False, part_ids=()),
            toolchain_id="synthetic-kicad-10",
            kicad_version="10.0.6",
            image="example.invalid/kicad@sha256:" + "c" * 64,
            project="projects/synthetic-spi-roster/design.kicad_pro",
            source_roots=(),
            required_inputs=(),
            validation=SchematicValidationContract(
                kind=ProjectKind.SCHEMATIC,
                expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
            ),
            electrical="projects/synthetic-spi-roster/electrical.json",
        )

        context = _spi_roster_context(root, config)

    assert context.state == "required"
    assert context.analysis == contract.spi
    assert context.source_path == "projects/synthetic-spi-roster/electrical.json"
    assert context.source_sha256 == source_sha256


def test_dnp_non_ic_and_incomplete_signal_patterns_are_excluded() -> None:
    observed = spi_netlist(dnp=("U3",), include_connector=True, partial_ic=True)
    candidates = unmapped_spi_participants(observed, SpiRosterContext(state="not_configured"))
    assert {item.reference for item in candidates} == {"U1", "U2"}


def test_candidate_obeys_review_block_off_and_exact_ignore_decisions() -> None:
    observed = spi_netlist()
    review = evaluate("synthetic-spi-roster", coach(observed), DesignLintPolicy())
    finding = next(
        item for item in review.findings if item.rule_id == "bus.spi_unmapped_participant"
    )
    assert finding.mode == "review"

    blocked = evaluate(
        "synthetic-spi-roster",
        coach(observed),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.spi_unmapped_participant",
                    mode="block",
                    reason="Every fitted SPI-capable IC needs a reviewed roster disposition",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = evaluate(
        "synthetic-spi-roster",
        coach(observed),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.spi_unmapped_participant",
                    mode="off",
                    reason="This project records SPI membership elsewhere",
                ),
            )
        ),
    )
    disabled_finding = next(
        item for item in disabled.findings if item.rule_id == "bus.spi_unmapped_participant"
    )
    assert disabled.status == "PASS"
    assert disabled_finding.disposition == "RULE_OFF"

    ignored = evaluate(
        "synthetic-spi-roster",
        coach(observed),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="This synthetic controller is intentionally outside the roster",
                ),
            )
        ),
    )
    ignored_finding = next(
        item
        for item in ignored.findings
        if item.rule_id == "bus.spi_unmapped_participant"
        and item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"

"""Synthetic USB-C port-role coverage hints and project rule decisions."""

from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.design_lint import (
    evaluate,
)
from kicad_tooling.hwrepo.design_lint_project_contexts import usb_c_port_roster_context
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    AnalysisNotApplicable,
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
    UsbCAnalysis,
    UsbCcLineRequirement,
    UsbCcResistorAttachment,
    UsbCNetPinAssignment,
    UsbCPortRequirement,
)
from kicad_tooling.hwrepo.usb_c_ports import UsbCPortRosterContext, unmapped_usb_c_ports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]

_NETLIST_SHA256 = "a" * 64
_CONTRACT_SHA256 = "b" * 64


def usb_c_analysis(connector: str = "J1") -> UsbCAnalysis:
    """Reviewed, synthetic source-port control used only for roster membership."""
    return UsbCAnalysis(
        basis="Synthetic USB-C port-role map",
        ports=(
            UsbCPortRequirement(
                id="source-port",
                basis="Synthetic approved source-port role",
                connector=connector,
                role="source",
                cc1=UsbCcLineRequirement(
                    connector_pin=f"{connector}.4",
                    net="CC1",
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
                    connector_pin=f"{connector}.5",
                    net="CC2",
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
                    UsbCNetPinAssignment(pin=f"{connector}.1", net="VBUS_PORT"),
                    UsbCNetPinAssignment(pin="U1.1", net="VBUS_SYSTEM"),
                ),
                ground_net="GND",
                ground_pins=(f"{connector}.2", "U1.5"),
                vbus_capacitance=AnalysisNotApplicable(
                    mode="not_applicable",
                    reason="Synthetic roster test does not assess port-side capacitance.",
                ),
                source_rail="+5V",
                protection=AnalysisNotApplicable(
                    mode="not_applicable", reason="Synthetic protection is tested separately."
                ),
            ),
        ),
    )


def usb_c_netlist(*, dnp: tuple[str, ...] = ()) -> NetlistContract:
    components = {
        reference: ComponentContract(value="Synthetic component", footprint="Synthetic:Part")
        for reference in ("J1", "J2", "J3", "J4", "U1")
    }
    functions = {
        "J1.4": "CC1",
        "J1.5": "CC2",
        "J2.4": "CC1",
        "J2.5": "CC2",
        "J3.4": "CC1",
        "J3.5": "CC2",
        "J4.4": "CC1",
        "U1.1": "CC1",
        "U1.2": "CC2",
    }
    return NetlistContract(
        components=components,
        nets={
            "CC1_NET": ("J1.4", "J2.4"),
            "CC2_NET": ("J1.5", "J2.5"),
        },
        unconnected_nets={"unconnected-(J3-CC1-Pad4)": ("J3.4",)},
        dnp_components=dnp,
        component_symbols={
            reference: "Synthetic:Connector" if reference.startswith("J") else "Synthetic:IC"
            for reference in components
        },
        pin_functions=functions,
        component_pin_numbers={
            "J1": ("4", "5"),
            "J2": ("4", "5"),
            "J3": ("4", "5"),
            "J4": ("4",),
            "U1": ("1", "2"),
        },
    )


def coach(observed: NetlistContract, netlist_sha256: str = _NETLIST_SHA256) -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-usb-c-ports",
        observed=observed,
        netlist_sha256=netlist_sha256,
    )


def test_unreviewed_port_prompt_is_order_stable_and_complete_map_clears_it() -> None:
    rule_id = "bus.usb_c_unreviewed_port"
    source = usb_c_netlist(dnp=("J3",))
    source_nets = dict(source.nets)
    source_nets["CC1_NET"] = ("J1.4",)
    source_nets["CC2_NET"] = ("J1.5",)
    source_nets["J2_CC1"] = ("J2.4",)
    source_nets["J2_CC2"] = ("J2.5",)
    source = source.model_copy(update={"nets": source_nets})

    j1_base = usb_c_analysis("J1").ports[0]
    j1_port = j1_base.model_copy(
        update={
            "cc1": j1_base.cc1.model_copy(update={"net": "CC1_NET"}),
            "cc2": j1_base.cc2.model_copy(update={"net": "CC2_NET"}),
        }
    )
    j2_base = usb_c_analysis("J2").ports[0]
    j2_port = j2_base.model_copy(
        update={
            "id": "second-source-port",
            "basis": "Synthetic approved source-port role for J2",
            "cc1": j2_base.cc1.model_copy(update={"net": "J2_CC1"}),
            "cc2": j2_base.cc2.model_copy(update={"net": "J2_CC2"}),
        }
    )
    j1_only_map = UsbCAnalysis(
        basis="Synthetic project USB-C map covers J1 only",
        ports=(j1_port,),
    )
    complete_map = UsbCAnalysis(
        basis="Synthetic project USB-C map covers J1 and J2",
        ports=(j1_port, j2_port),
    )

    def lint(analysis: UsbCAnalysis) -> tuple[str, str, DesignLintReport]:
        netlist_hash = hashlib.sha256(source.model_dump_json().encode("utf-8")).hexdigest()
        roster_hash = hashlib.sha256(analysis.model_dump_json().encode("utf-8")).hexdigest()
        context = UsbCPortRosterContext(
            state="required",
            analysis=analysis,
            source_path="projects/synthetic-usb-c-ports/electrical.json",
            source_sha256=roster_hash,
        )
        report = evaluate(
            "synthetic-usb-c-ports",
            coach(source, netlist_hash),
            DesignLintPolicy(),
            usb_c_port_roster=context,
        )
        return netlist_hash, roster_hash, report

    source_hash, roster_hash, original = lint(j1_only_map)
    assert original.netlist_sha256 == source_hash
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == rule_id
    }
    assert tuple(original_findings) == ("J2: USB-C role-map coverage",)
    assert original_findings["J2: USB-C role-map coverage"][1]["electrical_contract_sha256"] == (
        roster_hash,
    )

    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "unconnected_nets": dict(reversed(tuple(source.unconnected_nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered_hash = hashlib.sha256(reordered_source.model_dump_json().encode("utf-8")).hexdigest()
    reordered_report = evaluate(
        "synthetic-usb-c-ports",
        coach(reordered_source, reordered_hash),
        DesignLintPolicy(),
        usb_c_port_roster=UsbCPortRosterContext(
            state="required",
            analysis=j1_only_map,
            source_path="projects/synthetic-usb-c-ports/electrical.json",
            source_sha256=roster_hash,
        ),
    )
    assert source_hash != reordered_hash
    assert reordered_report.netlist_sha256 == reordered_hash
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered_report.findings
        if item.rule_id == rule_id
    }
    assert reordered_findings == original_findings

    mapped_hash, mapped_roster_hash, mapped = lint(complete_map)
    assert mapped_hash == source_hash
    assert mapped_roster_hash != roster_hash
    assert rule_id not in {item.rule_id for item in mapped.findings}


def test_unmapped_usb_c_port_without_role_map_is_review_candidate() -> None:
    observed = usb_c_netlist(dnp=("J3",))
    ports = unmapped_usb_c_ports(
        observed,
        UsbCPortRosterContext(state="not_configured"),
    )

    assert tuple(item.reference for item in ports) == ("J1", "J2")
    assert ports[0].cc1_pins == ("J1.4",)
    assert ports[0].cc2_pins == ("J1.5",)
    assert ports[0].signal_assignments == ("J1.4=CC1_NET", "J1.5=CC2_NET")

    report = evaluate(
        "synthetic-usb-c-ports",
        coach(observed),
        DesignLintPolicy(),
    )
    findings = [item for item in report.findings if item.rule_id == "bus.usb_c_unreviewed_port"]
    assert tuple(item.subject for item in findings) == (
        "J1: USB-C role-map coverage",
        "J2: USB-C role-map coverage",
    )
    assert "no configured project USB-C port role map" in findings[0].message
    assert findings[0].evidence["USB_C_roster_state"] == ("not_configured",)


def test_standard_or_project_reviewed_connector_identity_extends_usb_c_candidates() -> None:
    base = usb_c_netlist()
    standard_symbol = base.model_copy(
        update={
            "component_symbols": {
                **base.component_symbols,
                "U1": "Connector_Generic:Conn_02x01",
            }
        }
    )
    automatic = unmapped_usb_c_ports(
        standard_symbol,
        UsbCPortRosterContext(state="not_configured"),
    )
    assert "U1" in {item.reference for item in automatic}

    custom_symbol = base.model_copy(
        update={
            "component_symbols": {
                **base.component_symbols,
                "U1": "Custom:UsbInterface",
            }
        }
    )
    unreviewed = unmapped_usb_c_ports(
        custom_symbol,
        UsbCPortRosterContext(state="not_configured"),
    )
    assert "U1" not in {item.reference for item in unreviewed}
    reviewed = unmapped_usb_c_ports(
        custom_symbol,
        UsbCPortRosterContext(state="not_configured"),
        declared_connector_references=("U1",),
    )
    assert "U1" in {item.reference for item in reviewed}


def test_unlisted_usb_c_port_is_found_when_electrical_contract_maps_another_port() -> None:
    context = UsbCPortRosterContext(
        state="required",
        analysis=usb_c_analysis(),
        source_path="projects/synthetic-usb-c-ports/electrical.json",
        source_sha256=_CONTRACT_SHA256,
    )
    report = evaluate(
        "synthetic-usb-c-ports",
        coach(usb_c_netlist(dnp=("J3",))),
        DesignLintPolicy(),
        usb_c_port_roster=context,
    )

    findings = [item for item in report.findings if item.rule_id == "bus.usb_c_unreviewed_port"]
    assert tuple(item.subject for item in findings) == ("J2: USB-C role-map coverage",)
    assert "not listed in the project USB-C port role map" in findings[0].message
    assert findings[0].evidence["electrical_contract_path"] == (
        "projects/synthetic-usb-c-ports/electrical.json",
    )
    assert findings[0].evidence["electrical_contract_sha256"] == (_CONTRACT_SHA256,)


def test_mapped_usb_c_port_is_suppressed() -> None:
    report = evaluate(
        "synthetic-usb-c-ports",
        coach(usb_c_netlist(dnp=("J3",))),
        DesignLintPolicy(),
        usb_c_port_roster=UsbCPortRosterContext(
            state="required",
            analysis=usb_c_analysis(),
        ),
    )
    findings = [item for item in report.findings if item.rule_id == "bus.usb_c_unreviewed_port"]
    assert tuple(item.subject for item in findings) == ("J2: USB-C role-map coverage",)


def test_candidate_excludes_dnp_nonconnector_and_incomplete_pin_function_controls() -> None:
    ports = unmapped_usb_c_ports(
        usb_c_netlist(dnp=("J3",)),
        UsbCPortRosterContext(state="not_configured"),
    )
    assert {item.reference for item in ports} == {"J1", "J2"}
    assert "J3" not in {item.reference for item in ports}
    assert "J4" not in {item.reference for item in ports}
    assert "U1" not in {item.reference for item in ports}


def test_candidate_obeys_review_block_off_and_exact_ignore_decisions() -> None:
    observed = usb_c_netlist(dnp=("J3",))
    review = evaluate("synthetic-usb-c-ports", coach(observed), DesignLintPolicy())
    finding = next(item for item in review.findings if item.rule_id == "bus.usb_c_unreviewed_port")
    assert finding.mode == "review"

    blocked = evaluate(
        "synthetic-usb-c-ports",
        coach(observed),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.usb_c_unreviewed_port",
                    mode="block",
                    reason="Review each mapped USB-C connector role",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = evaluate(
        "synthetic-usb-c-ports",
        coach(observed),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.usb_c_unreviewed_port",
                    mode="off",
                    reason="USB-C port roles are reviewed in another controlled record",
                ),
            )
        ),
    )
    disabled_finding = next(
        item for item in disabled.findings if item.rule_id == "bus.usb_c_unreviewed_port"
    )
    assert disabled_finding.disposition == "RULE_OFF"

    ignored = evaluate(
        "synthetic-usb-c-ports",
        coach(observed),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="This candidate connector is intentionally not USB-C",
                ),
            )
        ),
    )
    ignored_finding = next(
        item
        for item in ignored.findings
        if item.rule_id == "bus.usb_c_unreviewed_port" and item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_inspection_context_loads_and_hashes_the_project_electrical_contract() -> None:
    with TemporaryDirectory(prefix="synthetic-usb-c-roster-") as temporary:
        root = Path(temporary).resolve()
        contract_path = root / "projects/synthetic-usb-c-ports/electrical.json"
        contract = ElectricalAnalysisContract(
            project_id="synthetic-usb-c-ports",
            ngspice_version="synthetic",
            grounding=AnalysisPending(reason="Synthetic grounding review pending."),
            power=AnalysisPending(reason="Synthetic power review pending."),
            high_frequency=AnalysisPending(reason="Synthetic frequency review pending."),
            usb_c=usb_c_analysis(),
        )
        contract_path.parent.mkdir(parents=True)
        write_model(contract_path, contract)
        source_sha256 = digest(contract_path)
        config = ProjectConfig(
            schema_version="1",
            kind=ProjectKind.SCHEMATIC,
            assurance_profile="development",
            not_for_manufacture=True,
            project_id="synthetic-usb-c-ports",
            component_identity=ComponentIdentity(required=False, part_ids=()),
            toolchain_id="synthetic-kicad-10",
            kicad_version="10.0.6",
            image="example.invalid/kicad@sha256:" + "c" * 64,
            project="projects/synthetic-usb-c-ports/design.kicad_pro",
            source_roots=(),
            required_inputs=(),
            validation=SchematicValidationContract(
                kind=ProjectKind.SCHEMATIC,
                expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
            ),
            electrical="projects/synthetic-usb-c-ports/electrical.json",
        )

        context = usb_c_port_roster_context(root, config)

    assert context.state == "required"
    assert context.analysis == contract.usb_c
    assert context.source_path == "projects/synthetic-usb-c-ports/electrical.json"
    assert context.source_sha256 == source_sha256

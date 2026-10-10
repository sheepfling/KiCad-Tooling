"""Verify component peer power-pin assignment and ERC controls."""

from __future__ import annotations

from .ci_hosted_digital_peer_context import DigitalPeerFixtureContext
from .hwrepo.design_lint import evaluate
from .hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
)


def verify_component_peer_power_cases(ctx: DigitalPeerFixtureContext):
    """Verify component peer power-pin assignment and ERC controls."""
    component_peer_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="bus.spi_unmapped_participant",
                mode="off",
                reason="Isolate the synthetic component peer power-pin fixture.",
            ),
            DesignLintRuleOverride(
                rule_id="power.ic_rail_without_fitted_capacitor",
                mode="off",
                reason="Isolate peer pin assignment review from decoupling coverage.",
            ),
        )
    )
    for case, expected_status, expected_count in (
        ("component-peer-control", "PASS", 0),
        ("component-peer-fault", "REVIEW", 2),
    ):
        peer_contracts = ctx.contracts[case]
        peer_observed = peer_contracts["first"]
        if ctx.normalized_hashes[case]["first"] != ctx.normalized_hashes[case]["repeat"]:
            raise ValueError(
                f"Native component peer {case} exports differ after typed-netlist normalization"
            )
        if ctx.normalized_erc_hashes[case]["first"] != ctx.normalized_erc_hashes[case]["repeat"]:
            raise ValueError(f"Native component peer {case} ERC reports are not repeatable")
        expected_pin_functions = {
            "U1.1": "IO",
            "U1.2": "VDD",
            "U1.3": "GND",
            "U2.1": "IO",
            "U2.2": "VDD",
            "U2.3": "GND",
        }
        expected_pin_types = {
            "U1.1": "passive",
            "U1.2": "power_in",
            "U1.3": "power_in",
            "U2.1": "passive",
            "U2.2": "power_in",
            "U2.3": "power_in",
        }
        if peer_observed.pin_functions != expected_pin_functions:
            raise ValueError(
                f"Native component peer {case} export changed pin functions: {peer_observed.pin_functions}"
            )
        if peer_observed.pin_electrical_types != expected_pin_types:
            raise ValueError(
                f"Native component peer {case} export changed pin types: {peer_observed.pin_electrical_types}"
            )
        if peer_observed.component_symbols != {
            "U1": "Synthetic:PeerModule",
            "U2": "Synthetic:PeerModule",
        }:
            raise ValueError(f"Native component peer {case} lost the shared exact symbol identity")
        if peer_observed.component_pin_numbers != {"U1": ("1", "2", "3"), "U2": ("1", "2", "3")}:
            raise ValueError(f"Native component peer {case} changed the complete pin inventory")
        reports: dict[str, DesignLintReport] = {}
        for run in ("first", "repeat"):
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-component-peer-power-{case}",
                observed=peer_contracts[run],
                netlist_sha256=ctx.hashes[case][run],
            )
            reports[run] = evaluate(coach.project_id, coach, component_peer_policy)
        findings = tuple(
            item
            for item in reports["first"].findings
            if item.rule_id == "component.peer_power_pin_assignment_divergence"
        )
        active_findings = tuple(item for item in reports["first"].findings if item.mode != "off")
        first_findings = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports["first"].findings
        )
        repeat_findings = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports["repeat"].findings
        )
        if (
            reports["first"].status != expected_status
            or reports["repeat"].status != expected_status
            or len(active_findings) != expected_count
            or any(
                item.rule_id != "component.peer_power_pin_assignment_divergence"
                for item in active_findings
            )
            or (len(findings) != expected_count)
            or (first_findings != repeat_findings)
            or any(item.mode != "review" for item in findings)
        ):
            raise ValueError(
                f"Native component peer {case} no longer matches its power-pin review case"
            )
        divergence_roles = tuple(
            sorted(
                (
                    item.evidence["pin_number"][0],
                    item.evidence["pin_function"][0],
                    item.evidence["peer_role"][0],
                )
                for item in findings
            )
        )
        expected_roles = (
            (("2", "VDD", "supply"), ("3", "GND", "ground/return"))
            if case == "component-peer-fault"
            else ()
        )
        if divergence_roles != expected_roles:
            raise ValueError(
                f"Native component peer {case} changed its exact divergent pin roles: {divergence_roles}"
            )
        pin_assignments = {
            pin: net
            for (net, pins) in peer_observed.nets.items()
            for pin in pins
            if pin.startswith(("U1.", "U2."))
        }
        ctx.log.event(
            f"component-peer-power-fixture/{case.removeprefix('component-peer-')}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            image=ctx.pinned,
            source_sha256=ctx.component_peer_source_hashes[case],
            netlist_sha256=ctx.hashes[case]["first"],
            repeat_netlist_sha256=ctx.hashes[case]["repeat"],
            normalized_netlist_sha256=ctx.normalized_hashes[case]["first"],
            repeat_normalized_netlist_sha256=ctx.normalized_hashes[case]["repeat"],
            erc_report_version=ctx.erc_report_versions[case]["first"],
            normalized_erc_sha256=ctx.normalized_erc_hashes[case]["first"],
            repeat_normalized_erc_sha256=ctx.normalized_erc_hashes[case]["repeat"],
            erc_warning_types=";".join(ctx.erc_warning_types[case]["first"]) or "none",
            erc_error_types=";".join(ctx.erc_error_types[case]["first"]) or "none",
            lint_status=reports["first"].status,
            peer_power_findings=";".join(item.rule_id for item in findings) or "none",
            divergent_pin_roles=";".join(
                f"{pin}:{function}:{role}" for (pin, function, role) in divergence_roles
            )
            or "none",
            pin_assignments=";".join(
                f"{pin}={net}" for (pin, net) in sorted(pin_assignments.items())
            ),
            pin_functions=";".join(
                f"{pin}={name}" for (pin, name) in sorted(peer_observed.pin_functions.items())
            ),
            pin_types=";".join(
                f"{pin}={name}"
                for (pin, name) in sorted(peer_observed.pin_electrical_types.items())
            ),
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )

"""Verify connector peer-scope findings and controls."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_connector_peer_scope(ctx: ConnectorReturnFixtureContext):
    """Verify connector peer-scope findings and controls."""
    from .hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ConnectorInterfaceReview,
        ConnectorInventoryReview,
        ContractCoachReport,
        DesignLintPolicy,
        InterfacePin,
        InterfaceRecord,
    )

    peer_scope_interface = InterfaceRecord(
        id="synthetic-peer-return",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="2",
                signal="RETURN",
                role="return",
                direction="bidirectional",
                voltage_domain="signal-return",
                mating="RETURN",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    peer_scope_catalog_path = ctx.scratch / "peer-scope-interface-catalog.json"
    peer_scope_catalog_path.write_text(
        json.dumps(
            {"schema_version": "1", "interfaces": [peer_scope_interface.model_dump(mode="json")]},
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    peer_scope_catalog_sha256 = digest(peer_scope_catalog_path)
    for report_name, source_case, shared_group in (
        ("separate-fault", "peer-scope-split-return-fault", False),
        ("shared-fault", "peer-scope-split-return-fault", True),
        ("shared-control", "generic-placeholder-control", True),
    ):
        observed = ctx.observed_contracts[source_case, "first"]
        peer_scope_reviews = tuple(
            ConnectorInterfaceReview(
                reference=f"J{reference}",
                disposition="interface",
                basis=f"Synthetic review maps J{reference} return contact",
                interface_id="synthetic-peer-return",
                pin_map={"2": "2"},
                unlisted_pin_reasons={
                    "1": "Generic Pin_1 signal contact has no reviewed role in this fixture"
                },
                peer_assignment_group="uart-peer-set" if shared_group else f"uart-port-{reference}",
                peer_assignment_basis="Reviewed generic signal contacts as one UART peer set"
                if shared_group
                else f"Reviewed J{reference} as an independent UART interface",
            )
            for reference in range(1, 4)
        )
        peer_scope_coverage = evaluate_connector_coverage(
            observed,
            ("synthetic-peer-return",),
            peer_scope_reviews,
            interfaces={"synthetic-peer-return": peer_scope_interface},
            interface_catalog_path=peer_scope_catalog_path.relative_to(ctx.root).as_posix(),
            interface_catalog_sha256=peer_scope_catalog_sha256,
            inventory_review=ConnectorInventoryReview(
                basis="Synthetic regression reviewed the complete connector inventory"
            ),
        )
        if peer_scope_coverage.status != "COMPLETE" or any(
            entry.status != "COVERED" for entry in peer_scope_coverage.entries
        ):
            raise ValueError("Peer-scope fixture did not produce complete interface coverage")
        project_id = f"synthetic-peer-scope-{report_name}"
        peer_scope_report = evaluate(
            project_id,
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=ctx.netlist_hashes[source_case, "first"],
            ),
            DesignLintPolicy(),
            connector_coverage=peer_scope_coverage,
        )
        expected_peer_scope_findings = {
            "separate-fault": {"connector.repeated_pin_function"},
            "shared-fault": {
                "connector.repeated_pin_function",
                "connector.peer_pin_assignment_divergence",
            },
            "shared-control": set[str](),
        }[report_name]
        peer_scope_findings = {item.rule_id: item for item in peer_scope_report.findings}
        if (
            peer_scope_report.status != ("REVIEW" if expected_peer_scope_findings else "PASS")
            or set(peer_scope_findings) != expected_peer_scope_findings
        ):
            raise ValueError(
                f"Peer-assignment scope changed unexpected {report_name} result: {peer_scope_report.status} {tuple(peer_scope_findings)}"
            )
        if report_name != "shared-control":
            return_finding = peer_scope_findings["connector.repeated_pin_function"]
            if {pin: return_finding.evidence[pin] for pin in ("J1.2", "J2.2", "J3.2")} != {
                "J1.2": ("RETURN_A",),
                "J2.2": ("RETURN_B",),
                "J3.2": ("RETURN_C",),
            }:
                raise ValueError("Peer grouping suppressed or changed cross-port return evidence")
        if report_name == "shared-fault":
            divergence = peer_scope_findings["connector.peer_pin_assignment_divergence"]
            if (
                divergence.evidence.get("peer_assignment_group") != ("uart-peer-set",)
                or len(divergence.evidence.get("peer_assignment_basis", ())) != 3
            ):
                raise ValueError("Shared peer divergence omitted its reviewed group evidence")
        ctx.log.event(
            f"connector-return-fixture/peer-scope-{report_name}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            image=ctx.pinned,
            catalog_sha256=peer_scope_catalog_sha256,
            source_case=source_case,
            netlist_sha256=ctx.netlist_hashes[source_case, "first"],
            normalized_netlist_sha256=ctx.normalized_netlist_hashes[source_case, "first"],
            repeat_normalized_netlist_sha256=ctx.normalized_netlist_hashes[source_case, "repeat"],
            coverage_status=peer_scope_coverage.status,
            lint_status=peer_scope_report.status,
            findings=",".join(peer_scope_findings) or "none",
            subjects=";".join(item.subject for item in peer_scope_report.findings) or "none",
            group_scope="shared uart-peer-set" if shared_group else "separate per-port groups",
            repeatable="true"
            if ctx.normalized_netlist_hashes[source_case, "first"]
            == ctx.normalized_netlist_hashes[source_case, "repeat"]
            else "false",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )

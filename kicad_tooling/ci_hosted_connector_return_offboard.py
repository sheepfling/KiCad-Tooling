"""Verify inventory and authored interface coverage for off-board connectors."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_offboard_connector_interfaces(ctx: ConnectorReturnFixtureContext):
    """Verify inventory and authored interface coverage for off-board connectors."""
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

    offboard_interface = InterfaceRecord(
        id="synthetic-offboard-power-port",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="External 5 V supply",
                role="supply",
                direction="input",
                voltage_domain="5V",
                mating="Synthetic external regulated supply",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal="External return",
                role="return",
                direction="bidirectional",
                voltage_domain="0V",
                mating="Synthetic external supply return",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    offboard_catalog_path = ctx.scratch / "synthetic-offboard-interface-catalog.json"
    offboard_catalog_path.write_text(
        json.dumps(
            {"schema_version": "1", "interfaces": [offboard_interface.model_dump(mode="json")]},
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    offboard_catalog_sha256 = digest(offboard_catalog_path)
    offboard_observed = ctx.observed_contracts["single-offboard-port-control", "first"]
    offboard_coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-single-offboard-port-control",
        observed=offboard_observed,
        netlist_sha256=ctx.netlist_hashes["single-offboard-port-control", "first"],
    )
    offboard_unreviewed_coverage = evaluate_connector_coverage(offboard_observed, (), ())
    offboard_unreviewed_report = evaluate(
        offboard_coach.project_id,
        offboard_coach,
        DesignLintPolicy(),
        connector_coverage=offboard_unreviewed_coverage,
    )
    if (
        offboard_unreviewed_coverage.status != "UNDECLARED"
        or offboard_unreviewed_report.status != "REVIEW"
        or offboard_unreviewed_report.findings
    ):
        raise ValueError(
            "Unmapped off-board connector must require inventory review without electrical findings"
        )
    ctx.log.event(
        "connector-return-fixture/offboard-inventory-unreviewed",
        "PASS",
        project=ctx.project,
        kicad_version=ctx.config.kicad_version,
        image=ctx.pinned,
        source_sha256=ctx.source_hashes["single-offboard-port-control"],
        normalized_netlist_sha256=ctx.normalized_netlist_hashes[
            "single-offboard-port-control", "first"
        ],
        coverage_status=offboard_unreviewed_coverage.status,
        lint_status=offboard_unreviewed_report.status,
        findings="none",
        repeatable="true",
        review_basis="candidate connector J1 is undeclared in the project interface map",
        command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
    )
    offboard_review = ConnectorInterfaceReview(
        reference="J1",
        disposition="interface",
        basis="Synthetic project map declares J1.1 as an external 5 V input and J1.2 as its off-board return endpoint",
        interface_id=offboard_interface.id,
        pin_map={"1": "1", "2": "2"},
    )
    offboard_coverage = evaluate_connector_coverage(
        offboard_observed,
        (offboard_interface.id,),
        (offboard_review,),
        interfaces={offboard_interface.id: offboard_interface},
        interface_catalog_path=offboard_catalog_path.relative_to(ctx.root).as_posix(),
        interface_catalog_sha256=offboard_catalog_sha256,
        inventory_review=ConnectorInventoryReview(
            basis="Synthetic project map reviewed the complete connector inventory"
        ),
    )
    if offboard_coverage.status != "COMPLETE" or any(
        item.status != "COVERED" for item in offboard_coverage.entries
    ):
        raise ValueError("Synthetic off-board connector control lacks complete pinout coverage")
    offboard_report = evaluate(
        offboard_coach.project_id,
        offboard_coach,
        DesignLintPolicy(),
        connector_coverage=offboard_coverage,
    )
    if (
        offboard_observed.nets != {"+5V": ("J1.1",), "GND": ("J1.2",)}
        or offboard_report.status != "PASS"
        or offboard_report.findings
    ):
        raise ValueError(
            "Complete off-board supply/return map no longer passes without local lint findings"
        )
    ctx.log.event(
        "connector-return-fixture/offboard-interface-control",
        "PASS",
        project=ctx.project,
        kicad_version=ctx.config.kicad_version,
        image=ctx.pinned,
        source_sha256=ctx.source_hashes["single-offboard-port-control"],
        netlist_sha256=ctx.netlist_hashes["single-offboard-port-control", "first"],
        repeat_netlist_sha256=ctx.netlist_hashes["single-offboard-port-control", "repeat"],
        normalized_netlist_sha256=ctx.normalized_netlist_hashes[
            "single-offboard-port-control", "first"
        ],
        repeat_normalized_netlist_sha256=ctx.normalized_netlist_hashes[
            "single-offboard-port-control", "repeat"
        ],
        interface_catalog_sha256=offboard_catalog_sha256,
        coverage_status=offboard_coverage.status,
        lint_status=offboard_report.status,
        findings="none",
        repeatable="true",
        repeatability_basis="normalized_netlist_contract",
        command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
    )

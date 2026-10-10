"""Verify reviewed return-role mappings against native netlists."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_mapped_return_interfaces(ctx: ConnectorReturnFixtureContext):
    """Verify reviewed return-role mappings against native netlists."""
    from .hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ConnectorInterfaceReview,
        ConnectorInventoryReview,
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        InterfacePin,
        InterfaceRecord,
    )

    mapped_return_interface = InterfaceRecord(
        id="synthetic-db9",
        revision="synthetic-1",
        pins=tuple(
            InterfacePin(
                number=str(number),
                signal=f"Contact {number}",
                role="return" if number in {7, 9} else "signal",
                direction="bidirectional",
                voltage_domain="synthetic-domain",
                mating=f"Contact {number}",
                orientation="straight",
                mechanical_clearance="synthetic",
            )
            for number in range(1, 10)
        ),
    )
    mapped_return_catalog_path = ctx.scratch / "synthetic-interface-catalog.json"
    mapped_return_catalog_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "interfaces": [mapped_return_interface.model_dump(mode="json")],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    mapped_return_catalog_sha256 = digest(mapped_return_catalog_path)
    mapped_return_reviews = tuple(
        ConnectorInterfaceReview(
            reference=f"J{reference}",
            disposition="interface",
            basis="Synthetic interface contact-role map reviewed for the native regression",
            interface_id="synthetic-db9",
            pin_map={str(number): str(number) for number in range(1, 10)},
        )
        for reference in range(1, 5)
    )
    mapped_return_reports: dict[str, DesignLintReport] = {}
    for case in ("four-db9-neutral-fault", "four-db9-neutral-control"):
        observed = ctx.observed_contracts[case, "first"]
        connector_coverage = evaluate_connector_coverage(
            observed,
            ("synthetic-db9",),
            mapped_return_reviews,
            interfaces={"synthetic-db9": mapped_return_interface},
            interface_catalog_path=mapped_return_catalog_path.relative_to(ctx.root).as_posix(),
            interface_catalog_sha256=mapped_return_catalog_sha256,
            inventory_review=ConnectorInventoryReview(
                basis="Synthetic fixture reviewed the complete connector inventory"
            ),
        )
        if connector_coverage.status != "COMPLETE" or any(
            entry.status != "COVERED" for entry in connector_coverage.entries
        ):
            raise ValueError("Synthetic mapped-return fixture did not produce complete coverage")
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=f"synthetic-mapped-returns-{case}",
            observed=observed,
            netlist_sha256=ctx.netlist_hashes[case, "first"],
        )
        mapped_report = evaluate(
            coach.project_id, coach, DesignLintPolicy(), connector_coverage=connector_coverage
        )
        mapped_return_reports[case] = mapped_report
        expected_finding_ids: set[str] = (
            {"connector.repeated_pin_function"} if case == "four-db9-neutral-fault" else set()
        )
        if (
            mapped_report.status != ("REVIEW" if expected_finding_ids else "PASS")
            or {item.rule_id for item in mapped_report.findings} != expected_finding_ids
        ):
            raise ValueError(
                f"Reviewed contact roles changed unexpected {case} result: {mapped_report.status} {tuple(item.rule_id for item in mapped_report.findings)}"
            )
        if case == "four-db9-neutral-fault":
            repeated = next(
                item
                for item in mapped_report.findings
                if item.rule_id == "connector.repeated_pin_function"
            )
            expected_pin_evidence: dict[str, tuple[str, ...]] = {
                f"J{reference}.{pin}": (f"NET_{chr(64 + reference)}",)
                for reference in range(1, 5)
                for pin in (7, 9)
            }
            expected_pin_evidence["role_classification_sources"] = tuple(
                f"J{reference}.{pin}: project interface catalog role=return; native symbol function={pin}"
                for reference in range(1, 5)
                for pin in (7, 9)
            )
            if dict(repeated.evidence) != expected_pin_evidence:
                raise ValueError(
                    "Mapped DB9 returns lost exact native pin and role-source evidence"
                )
        ctx.log.event(
            f"connector-return-fixture/reviewed-role-{case.removeprefix('four-db9-neutral-')}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            image=ctx.pinned,
            catalog_sha256=mapped_return_catalog_sha256,
            netlist_sha256=ctx.netlist_hashes[case, "first"],
            normalized_netlist_sha256=ctx.normalized_netlist_hashes[case, "first"],
            repeat_normalized_netlist_sha256=ctx.normalized_netlist_hashes[case, "repeat"],
            coverage_status=connector_coverage.status,
            lint_status=mapped_report.status,
            findings=",".join(item.rule_id for item in mapped_report.findings) or "none",
            subjects=";".join(item.subject for item in mapped_report.findings) or "none",
            source_role_classification="7=signal-number; 9=signal-number; catalog roles classify both as return",
            repeatable="true"
            if ctx.normalized_netlist_hashes[case, "first"]
            == ctx.normalized_netlist_hashes[case, "repeat"]
            else "false",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )

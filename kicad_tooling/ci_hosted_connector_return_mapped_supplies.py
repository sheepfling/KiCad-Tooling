"""Verify reviewed supply-domain mappings against native netlists."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_mapped_supply_interfaces(ctx: ConnectorReturnFixtureContext):
    """Verify reviewed supply-domain mappings against native netlists."""
    from .hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ConnectorInterfaceReview,
        ConnectorInventoryReview,
        ConnectorPinRole,
        ContractCoachReport,
        DesignLintPolicy,
        InterfacePin,
        InterfaceRecord,
    )

    def mapped_supply_catalog(serial_voltage_domain: str) -> dict[str, InterfaceRecord]:
        definitions: dict[str, tuple[tuple[str, str, ConnectorPinRole, str], ...]] = {
            "synthetic-usb-port": (
                ("4", "RETURN", "return", "signal-return"),
                ("1", "POWER", "supply", "external-5v"),
            ),
            "synthetic-serial-port": (
                ("7", "RETURN", "return", "signal-return"),
                ("9", "POWER", "supply", serial_voltage_domain),
            ),
            "synthetic-shield-port": (("1", "SHIELD", "shield", "chassis"),),
        }
        return {
            interface_id: InterfaceRecord(
                id=interface_id,
                revision="synthetic-1",
                pins=tuple(
                    InterfacePin(
                        number=number,
                        signal=signal,
                        role=role,
                        direction="passive",
                        voltage_domain=voltage_domain,
                        mating=signal,
                        orientation="straight",
                        mechanical_clearance="synthetic",
                    )
                    for (number, signal, role, voltage_domain) in pins
                ),
            )
            for (interface_id, pins) in definitions.items()
        }

    mapped_supply_reviews = (
        ConnectorInterfaceReview(
            reference="J1",
            disposition="interface",
            basis="Synthetic USB return and supply contacts reviewed",
            interface_id="synthetic-usb-port",
            pin_map={"4": "4", "1": "1"},
        ),
        ConnectorInterfaceReview(
            reference="J2",
            disposition="interface",
            basis="Synthetic serial return and supply contacts reviewed",
            interface_id="synthetic-serial-port",
            pin_map={"7": "7", "9": "9"},
        ),
        ConnectorInterfaceReview(
            reference="J3",
            disposition="interface",
            basis="Synthetic shield contact reviewed separately",
            interface_id="synthetic-shield-port",
            pin_map={"1": "1"},
        ),
    )
    for case, serial_voltage_domain in (
        ("mapped-supply-fault", "external-5v"),
        ("mapped-supply-control", "external-5v"),
        ("mapped-supply-fault", "isolated-5v"),
    ):
        domain_control = serial_voltage_domain == "isolated-5v"
        report_key = "mapped-supply-domain-control" if domain_control else case
        observed = ctx.observed_contracts[case, "first"]
        interfaces = mapped_supply_catalog(serial_voltage_domain)
        catalog_path = ctx.scratch / f"{report_key}-interface-catalog.json"
        catalog_path.write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "interfaces": [item.model_dump(mode="json") for item in interfaces.values()],
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        catalog_sha256 = digest(catalog_path)
        connector_coverage = evaluate_connector_coverage(
            observed,
            tuple(interfaces),
            mapped_supply_reviews,
            interfaces=interfaces,
            interface_catalog_path=catalog_path.relative_to(ctx.root).as_posix(),
            interface_catalog_sha256=catalog_sha256,
            inventory_review=ConnectorInventoryReview(
                basis="Synthetic fixture reviewed the complete connector inventory"
            ),
        )
        if connector_coverage.status != "COMPLETE" or any(
            entry.status != "COVERED" for entry in connector_coverage.entries
        ):
            raise ValueError("Synthetic mapped-supply fixture did not produce complete coverage")
        project_id = f"synthetic-mapped-supply-{report_key}"
        mapped_report = evaluate(
            project_id,
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=ctx.netlist_hashes[case, "first"],
            ),
            DesignLintPolicy(),
            connector_coverage=connector_coverage,
        )
        expected_finding_ids: set[str] = (
            {"connector.repeated_pin_function"}
            if case == "mapped-supply-fault" and (not domain_control)
            else set()
        )
        if (
            mapped_report.status != ("REVIEW" if expected_finding_ids else "PASS")
            or {item.rule_id for item in mapped_report.findings} != expected_finding_ids
        ):
            raise ValueError(
                f"Reviewed supply domains changed unexpected {report_key} result: {mapped_report.status} {tuple(item.rule_id for item in mapped_report.findings)}"
            )
        if expected_finding_ids:
            repeated = next(
                item
                for item in mapped_report.findings
                if item.rule_id == "connector.repeated_pin_function"
            )
            expected_evidence = {
                "J1.1": ("SUPPLY_ALPHA",),
                "J2.9": ("SUPPLY_BETA",),
                "role_classification_sources": (
                    "J1.1: project interface catalog role=supply; voltage_domain=external-5v; native symbol function=Pin_1",
                    "J2.9: project interface catalog role=supply; voltage_domain=external-5v; native symbol function=Pin_9",
                ),
                "reviewed_voltage_domain": ("external-5v",),
            }
            if dict(repeated.evidence) != expected_evidence:
                raise ValueError("Mapped supply fault lost exact pin, domain, or role evidence")
        event_name = (
            "domain-control"
            if domain_control
            else "fault"
            if case == "mapped-supply-fault"
            else "control"
        )
        ctx.log.event(
            f"connector-return-fixture/reviewed-supply-{event_name}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            image=ctx.pinned,
            catalog_sha256=catalog_sha256,
            netlist_sha256=ctx.netlist_hashes[case, "first"],
            normalized_netlist_sha256=ctx.normalized_netlist_hashes[case, "first"],
            repeat_normalized_netlist_sha256=ctx.normalized_netlist_hashes[case, "repeat"],
            coverage_status=connector_coverage.status,
            lint_status=mapped_report.status,
            findings=",".join(item.rule_id for item in mapped_report.findings) or "none",
            subjects=";".join(item.subject for item in mapped_report.findings) or "none",
            source_role_classification=f"role=supply; USB domain=external-5v; serial domain={serial_voltage_domain}; native supply functions are generic Pin_1 and Pin_9",
            repeatable="true"
            if ctx.normalized_netlist_hashes[case, "first"]
            == ctx.normalized_netlist_hashes[case, "repeat"]
            else "false",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )

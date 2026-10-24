"""Verify reviewed supply-domain mappings against native netlists."""

from __future__ import annotations

import json

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_mapped_supply_interfaces(ctx: ConnectorReturnFixtureContext):
    """Verify reviewed supply-domain mappings against native netlists."""
    from .hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
    from .hwrepo.connector_coverage_models import (
        ConnectorInterfaceReview,
        ConnectorInventoryReview,
    )
    from .hwrepo.connector_peer_pin_models import ConnectorPinRole
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
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
    for case, serial_voltage_domain, supply_groups in (
        ("mapped-supply-fault", "external-5v", None),
        ("mapped-supply-control", "external-5v", None),
        ("mapped-supply-fault", "isolated-5v", None),
        ("mapped-supply-control", "isolated-5v", None),
        (
            "mapped-supply-fault",
            "external-5v",
            {"J1": "usb-supply", "J2": "serial-supply"},
        ),
    ):
        domain_sharing_fault = (
            case == "mapped-supply-control" and serial_voltage_domain == "isolated-5v"
        )
        domain_control = serial_voltage_domain == "isolated-5v" and not domain_sharing_fault
        scope_review = case == "mapped-supply-fault" and supply_groups is not None
        report_key = (
            "mapped-supply-scope-review"
            if scope_review
            else "mapped-supply-domain-sharing-fault"
            if domain_sharing_fault
            else "mapped-supply-domain-control"
            if domain_control
            else case
        )
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
        reviews = tuple(
            review.model_copy(
                update={
                    "supply_comparison_group": (
                        None if supply_groups is None else supply_groups.get(review.reference)
                    ),
                    "supply_comparison_basis": (
                        None
                        if supply_groups is None or review.reference not in supply_groups
                        else f"Reviewed {review.reference} in supply group "
                        f"{supply_groups[review.reference]}"
                    ),
                }
            )
            for review in mapped_supply_reviews
        )
        connector_coverage = evaluate_connector_coverage(
            observed,
            tuple(interfaces),
            reviews,
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
            {"connector.return_supply_scope_singleton"}
            if scope_review
            else {"connector.mapped_supply_domains_share_net"}
            if domain_sharing_fault
            else {"connector.repeated_pin_function"}
            if case == "mapped-supply-fault" and not domain_control
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
            finding = next(
                item for item in mapped_report.findings if item.rule_id in expected_finding_ids
            )
            if scope_review:
                expected_evidence = {
                    "comparison_role": ("supply in voltage domain external-5v",),
                    "comparable_references": ("J1", "J2"),
                    "isolated_references": ("J1", "J2"),
                    "scope_evidence": (
                        "J1: supply_comparison_group=usb-supply; Reviewed J1 in supply group usb-supply",
                        "J2: supply_comparison_group=serial-supply; Reviewed J2 in supply group serial-supply",
                    ),
                    "mapped_pin_assignments": (
                        "J1.1=SUPPLY_ALPHA; supply_comparison_group=usb-supply",
                        "J2.9=SUPPLY_BETA; supply_comparison_group=serial-supply",
                    ),
                    "J1.1": ("SUPPLY_ALPHA",),
                    "J2.9": ("SUPPLY_BETA",),
                }
                if any(
                    finding.evidence.get(key) != value for key, value in expected_evidence.items()
                ):
                    raise ValueError(
                        "Mapped supply-scope review lost its exact groups or pin evidence"
                    )
                if finding.evidence.get("interface_catalog_sha256") != (catalog_sha256,):
                    raise ValueError("Mapped supply-scope review omitted its catalog digest")
            elif domain_sharing_fault:
                expected_evidence = {
                    "native_shared_net": ("COMMON_SUPPLY",),
                    "reviewed_voltage_domains": ("external-5v", "isolated-5v"),
                    "mapped_supply_assignments": (
                        "J1.1=COMMON_SUPPLY; voltage_domain=external-5v",
                        "J2.9=COMMON_SUPPLY; voltage_domain=isolated-5v",
                    ),
                    "role_classification_sources": (
                        "J1.1: source-matched project interface role=supply; voltage_domain=external-5v; signal=POWER; native function=Pin_1",
                        "J2.9: source-matched project interface role=supply; voltage_domain=isolated-5v; signal=POWER; native function=Pin_9",
                    ),
                    "J1.1": ("COMMON_SUPPLY",),
                    "J2.9": ("COMMON_SUPPLY",),
                }
                if any(
                    finding.evidence.get(key) != value for key, value in expected_evidence.items()
                ):
                    raise ValueError(
                        "Mapped supply-domain short lost its exact net or pin evidence"
                    )
                if finding.evidence.get("interface_catalog_sha256") != (catalog_sha256,):
                    raise ValueError(
                        "Mapped supply-domain short omitted its interface catalog digest"
                    )
            else:
                expected_evidence = {
                    "J1.1": ("SUPPLY_ALPHA",),
                    "J2.9": ("SUPPLY_BETA",),
                    "role_classification_sources": (
                        "J1.1: project interface catalog role=supply; voltage_domain=external-5v; native symbol function=Pin_1",
                        "J2.9: project interface catalog role=supply; voltage_domain=external-5v; native symbol function=Pin_9",
                    ),
                    "reviewed_voltage_domain": ("external-5v",),
                }
                if dict(finding.evidence) != expected_evidence:
                    raise ValueError("Mapped supply fault lost exact pin, domain, or role evidence")
        event_name = (
            "scope-review"
            if scope_review
            else "domain-sharing-fault"
            if domain_sharing_fault
            else "domain-control"
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
            evidence=json.dumps(dict(mapped_report.findings[0].evidence), sort_keys=True)
            if mapped_report.findings
            else "none",
            source_role_classification=f"role=supply; USB domain=external-5v; serial domain={serial_voltage_domain}; native supply functions are generic Pin_1 and Pin_9",
            comparison_scope=(
                "distinct reviewed supply groups"
                if scope_review
                else "global same-voltage-domain comparison"
            ),
            repeatable="true"
            if ctx.normalized_netlist_hashes[case, "first"]
            == ctx.normalized_netlist_hashes[case, "repeat"]
            else "false",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )

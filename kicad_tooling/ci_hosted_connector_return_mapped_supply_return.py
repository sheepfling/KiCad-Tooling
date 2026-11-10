"""Verify mapped supply/return sharing against exact native connector exports."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext
from .hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from .hwrepo.connector_coverage_models import ConnectorInterfaceReview, ConnectorInventoryReview
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.contracts import model_json_bytes
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.models import (
    DesignLintPolicy,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
)

RULE_ID = "connector.mapped_supply_return_share_net"
FAULT_CASE = "mapped-supply-return-share-fault"
CONTROL_CASE = "mapped-supply-return-share-control"


def verify_mapped_supply_return_sharing(ctx: ConnectorReturnFixtureContext) -> None:
    """Require the exact shared-net fault and separate-net control to diverge."""
    interface = InterfaceRecord(
        id="synthetic-supply-return-port",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="SUPPLY_CONTACT",
                role="supply",
                direction="input",
                voltage_domain="synthetic-5v",
                mating="SUPPLY_CONTACT",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal="RETURN_CONTACT",
                role="return",
                direction="passive",
                voltage_domain="synthetic-ground",
                mating="RETURN_CONTACT",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    catalog = InterfacesCatalog(schema_version="1", interfaces=(interface,))
    catalog_path = ctx.scratch / "mapped-supply-return-interface-catalog.json"
    catalog_path.write_bytes(model_json_bytes(catalog))
    catalog_digest = digest(catalog_path)
    catalog_repository_path = catalog_path.relative_to(ctx.root).as_posix()
    review = ConnectorInterfaceReview(
        reference="J1",
        disposition="interface",
        basis="Synthetic independently reviewed connector supply/return pinout",
        interface_id=interface.id,
        pin_map={"1": "1", "2": "2"},
    )

    for case in (FAULT_CASE, CONTROL_CASE):
        observed = ctx.observed_contracts[case, "first"]
        coverage = evaluate_connector_coverage(
            observed,
            (interface.id,),
            (review,),
            interfaces={interface.id: interface},
            interface_catalog_path=catalog_repository_path,
            interface_catalog_sha256=catalog_digest,
            inventory_review=ConnectorInventoryReview(
                basis="Synthetic review covered the complete connector inventory"
            ),
        )
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=f"synthetic-connector-{case}",
            observed=observed,
            netlist_sha256=ctx.netlist_hashes[case, "first"],
        )
        report = evaluate(
            coach.project_id,
            coach,
            DesignLintPolicy(),
            connector_coverage=coverage,
        )
        findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
        if coverage.status != "COMPLETE":
            raise ValueError(f"{case}: synthetic connector map is {coverage.status}")
        if (
            ctx.normalized_netlist_hashes[case, "first"]
            != ctx.normalized_netlist_hashes[case, "repeat"]
        ):
            raise ValueError(f"{case}: repeated native netlist exports differ")

        if case == FAULT_CASE:
            if observed.nets.get("AUX_SHARED_NODE") != ("J1.1", "J1.2") or len(findings) != 1:
                raise ValueError("Mapped supply/return shared-net fault did not produce one review")
        elif (
            observed.nets.get("SUPPLY_SOURCE") != ("J1.1",)
            or observed.nets.get("RETURN_REFERENCE") != ("J1.2",)
            or findings
        ):
            raise ValueError("Mapped supply/return separate-net control produced a review")

        ctx.log.event(
            f"{ctx.stage_prefix}/mapped-supply-return-{case.removeprefix('mapped-supply-return-share-')}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            rule_id=RULE_ID,
            finding_count=str(len(findings)),
            interface_catalog_sha256=catalog_digest,
        )

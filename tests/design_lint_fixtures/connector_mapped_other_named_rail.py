"""Complete source-matched connector coverage for native named-rail tests."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
)
from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
    NetlistContract,
)
from tests.connector_mapped_interface_support import interface_coverage
from tests.design_lint_fixtures.connector_mapped_interface_signal import (
    mapped_interface_netlist,
)


def mapped_other_named_rail_netlist(
    *,
    target_net: str = "GND",
    target_function: str = "2",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Return a minimal netlist with one generic contact mapped as other."""
    observed = mapped_interface_netlist(
        target_net=target_net,
        target_function=target_function,
        target_type="input",
        dnp=dnp,
    )
    nets = dict(observed.nets)
    nets["AUX_REFERENCE"] = nets.pop("SIGNAL_RETURN")
    return observed.model_copy(update={"nets": nets})


def mapped_other_named_rail_report(
    observed: NetlistContract,
    *,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> tuple[DesignLintReport, ConnectorCoverageReport]:
    """Evaluate a complete source-matched synthetic mapped-other case."""
    if coverage is None:
        coverage = interface_coverage(observed, target_role="other")
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-mapped-other-named-rail",
        observed=observed,
        netlist_sha256=sha256(model_json_bytes(observed)).hexdigest(),
    )
    report = evaluate(
        coach.project_id,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage=coverage,
    )
    return report, coverage


def native_return_board_coverage(
    observed: NetlistContract,
    *,
    other_pins: frozenset[str] = frozenset(),
) -> ConnectorCoverageReport:
    """Build a complete, test-authored interface catalog for the synthetic DB9 export."""
    interfaces: dict[str, InterfaceRecord] = {}
    reviews: list[ConnectorInterfaceReview] = []
    for reference, pin_numbers in sorted(observed.component_pin_numbers.items()):
        interface_id = f"synthetic-ret-board-{reference}"
        pins: list[InterfacePin] = []
        for number in sorted(pin_numbers):
            component_pin = f"{reference}.{number}"
            role = (
                "other"
                if component_pin in other_pins
                else "return"
                if number in {"7", "9"}
                else "signal"
            )
            pins.append(
                InterfacePin(
                    number=number,
                    signal=f"PIN_{number}",
                    role=role,
                    direction="passive",
                    voltage_domain="signal-return" if role == "return" else "unspecified",
                    mating=f"PIN_{number}",
                    orientation="straight",
                    mechanical_clearance="synthetic fixture mapping",
                )
            )
        interface = InterfaceRecord(
            id=interface_id,
            revision="synthetic-1",
            pins=tuple(pins),
        )
        interfaces[interface_id] = interface
        reviews.append(
            ConnectorInterfaceReview(
                reference=reference,
                disposition="interface",
                basis="Tooling-authored synthetic complete connector map",
                interface_id=interface_id,
                pin_map={number: number for number in sorted(pin_numbers)},
            )
        )

    records = tuple(interfaces[key] for key in sorted(interfaces))
    catalog = InterfacesCatalog(schema_version="1", interfaces=records)
    return evaluate_connector_coverage(
        observed,
        tuple(record.id for record in records),
        tuple(reviews),
        interfaces=interfaces,
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256=sha256(model_json_bytes(catalog)).hexdigest(),
        inventory_review=ConnectorInventoryReview(
            basis="Synthetic native fixture connector inventory is fully mapped"
        ),
    )

"""Returns report cases for deterministic synthetic verification."""

from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.electrical import grounding_checks, pin_relationship_checks
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintPolicy,
    GroundDomain,
    GroundingAnalysis,
    NetlistContract,
    PinConnectivityAnalysis,
    PinRelationshipRule,
)
from kicad_tooling.validate import read_netlist
from tests.design_lint_fixtures import (
    coach,
    four_db9_return_domains,
)
from tests.design_lint_fixtures.connector_coverage import (
    connector_return_role_catalog,
    connector_return_role_netlist,
    connector_return_role_reviews,
    inventory_review,
)
from tests.test_return_net_lint import lint_report as return_net_lint_report


def reviewed_connector_return_report(*, common_return: bool) -> dict[str, object]:
    observed = connector_return_role_netlist(common_return=common_return)
    coverage = evaluate_connector_coverage(
        observed,
        ("usb-interface", "serial-interface"),
        connector_return_role_reviews(),
        interfaces=connector_return_role_catalog(),
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="b" * 64,
        inventory_review=inventory_review(),
    )
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    report = evaluate(
        "synthetic-reviewed-return-common" if common_return else "synthetic-reviewed-return-split",
        coach(observed, netlist_sha256),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )
    return report.model_dump(mode="json")


def parsed_netlist_pin_metadata() -> dict[str, list[tuple[str, str]]]:
    """Serialize parser maps built from a synthetic, multi-pin library symbol."""
    pin_numbers = tuple(str(number) for number in range(1, 25))
    library_pins = "".join(
        f'<pin num="{number}" name="FUNCTION_{number}" type="passive"/>' for number in pin_numbers
    )
    with TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic-netlist.xml"
        path.write_text(
            f'<export><components><comp ref="J1"><value>Synthetic</value><libsource lib="Synthetic" part="Port"/></comp></components><libparts><libpart lib="Synthetic" part="Port"><pins>{library_pins}</pins></libpart></libparts><nets/></export>',
            encoding="utf-8",
        )
        observed = read_netlist(path)
    return {
        "pin_functions": list(observed.pin_functions.items()),
        "pin_electrical_types": list(observed.pin_electrical_types.items()),
    }


def db9_grounding_check_result(
    *, observed_common: bool, required_common: bool
) -> dict[str, object]:
    """Serialize the same DB9 return netlist against common and isolated requirements."""
    observed = four_db9_return_domains(common=observed_common).model_copy(
        update={
            "components": {
                f"J{reference}": ComponentContract(value="Synthetic DB9", footprint="")
                for reference in range(1, 5)
            }
        }
    )
    all_return_pins = tuple(
        f"J{reference}.{pin_number}" for reference in range(1, 5) for pin_number in (7, 9)
    )
    domains = (
        (GroundDomain(net="COMMON_RETURN", pins=all_return_pins),)
        if required_common
        else tuple(
            GroundDomain(
                net=f"RETURN_PORT_{reference}", pins=(f"J{reference}.7", f"J{reference}.9")
            )
            for reference in range(1, 5)
        )
    )
    requirement = GroundingAnalysis(
        basis="Synthetic reviewed requirement: DB9 returns share one domain"
        if required_common
        else "Synthetic reviewed requirement: each DB9 return remains isolated",
        domains=domains,
    )
    checks = grounding_checks(requirement, observed)
    connectivity_rules = (
        (
            PinRelationshipRule(
                id="db9-common-return",
                basis="Synthetic reviewed requirement for common DB9 returns",
                topology="common_net",
                pins=all_return_pins,
                net="COMMON_RETURN",
            ),
        )
        if required_common
        else tuple(
            PinRelationshipRule(
                id=f"db9-{reference}-isolated-return",
                basis="Synthetic reviewed per-connector isolated return requirement",
                topology="common_net",
                pins=(f"J{reference}.7", f"J{reference}.9"),
                net=f"RETURN_PORT_{reference}",
            )
            for reference in range(1, 5)
        )
    )
    connectivity = PinConnectivityAnalysis(
        basis="Synthetic reviewed pin-connectivity requirement: common DB9 return"
        if required_common
        else "Synthetic reviewed pin-connectivity requirement: isolated DB9 returns",
        rules=connectivity_rules,
    )
    connectivity_checks = pin_relationship_checks(connectivity, observed)
    return {
        "observed_common": observed_common,
        "required_common": required_common,
        "netlist_sha256": hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest(),
        "requirements_sha256": hashlib.sha256(
            requirement.model_dump_json().encode("utf-8")
        ).hexdigest(),
        "checks": [check.model_dump(mode="json") for check in checks],
        "connectivity_requirements_sha256": hashlib.sha256(
            connectivity.model_dump_json().encode("utf-8")
        ).hexdigest(),
        "pin_connectivity_checks": [check.model_dump(mode="json") for check in connectivity_checks],
    }


def unconnected_pin_inventory_check_result() -> dict[str, object]:
    """Compare absent and complete symbol-pin inventories for an unused pin."""
    requirement = PinConnectivityAnalysis(
        basis="Synthetic approved connector pin disposition",
        rules=(
            PinRelationshipRule(
                id="reserved-pin",
                basis="J1.2 is intentionally unused on this assembly",
                topology="unconnected",
                pins=("J1.2",),
            ),
        ),
    )
    missing_inventory = NetlistContract(
        components={"J1": ComponentContract(value="Synthetic port", footprint="")},
        nets={},
        component_symbols={"J1": "Synthetic:Port"},
        component_pin_numbers={},
    )
    complete_inventory = missing_inventory.model_copy(
        update={"component_pin_numbers": {"J1": ("1", "2")}}
    )
    results: dict[str, object] = {
        "requirements_sha256": hashlib.sha256(
            requirement.model_dump_json().encode("utf-8")
        ).hexdigest()
    }
    for name, observed in (
        ("missing_inventory", missing_inventory),
        ("complete_inventory_control", complete_inventory),
    ):
        results[name] = {
            "netlist_sha256": hashlib.sha256(
                observed.model_dump_json().encode("utf-8")
            ).hexdigest(),
            "checks": [
                check.model_dump(mode="json")
                for check in pin_relationship_checks(requirement, observed)
            ],
        }
    return results


def report_cases() -> dict[str, object]:
    return {
        "parsed_netlist_pin_metadata": parsed_netlist_pin_metadata(),
        "fault": evaluate(
            "synthetic-four-db9-hash-seed-fault",
            coach(four_db9_return_domains()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "common_control": evaluate(
            "synthetic-four-db9-hash-seed-common",
            coach(four_db9_return_domains(common=True)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "letter_suffixed_unindexed_return_fault": return_net_lint_report(
            ("GNDA", "GNDD")
        ).model_dump(mode="json"),
        "letter_suffixed_numbered_return_fault": return_net_lint_report(
            ("GNDA1", "GNDA2")
        ).model_dump(mode="json"),
        "letter_suffixed_return_roles_control": return_net_lint_report(
            ("GNDA", "GNDD"), pin_functions=("GND", "RTN")
        ).model_dump(mode="json"),
        "db9_split_against_common_requirement": db9_grounding_check_result(
            observed_common=False, required_common=True
        ),
        "db9_split_against_isolated_requirement": db9_grounding_check_result(
            observed_common=False, required_common=False
        ),
        "db9_common_against_common_requirement": db9_grounding_check_result(
            observed_common=True, required_common=True
        ),
        "db9_common_against_isolated_requirement": db9_grounding_check_result(
            observed_common=True, required_common=False
        ),
        "unconnected_pin_inventory": unconnected_pin_inventory_check_result(),
        "mapped_return_fault": reviewed_connector_return_report(common_return=False),
        "mapped_return_control": reviewed_connector_return_report(common_return=True),
    }

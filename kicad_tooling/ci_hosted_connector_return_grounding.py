"""Verify authored return-domain and pin-connectivity contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext
from .hwrepo.electrical import grounding_checks, pin_relationship_checks
from .hwrepo.grounding_models import GroundDomain, GroundingAnalysis
from .hwrepo.models import ElectricalCheck
from .hwrepo.pin_connectivity_models import PinConnectivityAnalysis, PinRelationshipRule


def _record_grounding_contract(
    ctx: ConnectorReturnFixtureContext,
    *,
    case: str,
    spec: GroundingAnalysis,
    source_case: str,
    relationship: str,
    checks: Mapping[str, str],
) -> None:
    spec_digest = hashlib.sha256(
        json.dumps(
            spec.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    ctx.log.event(
        f"connector-return-fixture/ground-contract-{case}",
        "PASS",
        project=ctx.project,
        kicad_version=ctx.config.kicad_version,
        image=ctx.pinned,
        source_sha256=ctx.source_hashes[source_case],
        netlist_sha256=ctx.netlist_hashes[source_case, "first"],
        repeat_netlist_sha256=ctx.netlist_hashes[source_case, "repeat"],
        normalized_netlist_sha256=ctx.normalized_netlist_hashes[source_case, "first"],
        repeat_normalized_netlist_sha256=ctx.normalized_netlist_hashes[source_case, "repeat"],
        grounding_contract_sha256=spec_digest,
        relationship=relationship,
        contract_status="FAIL" if "FAIL" in checks.values() else "PASS",
        checks=";".join(f"{key}={value}" for key, value in sorted(checks.items())),
        repeatable="true"
        if ctx.normalized_netlist_hashes[source_case, "first"]
        == ctx.normalized_netlist_hashes[source_case, "repeat"]
        else "false",
        command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
    )


def _record_pin_connectivity_contract(
    ctx: ConnectorReturnFixtureContext,
    *,
    case: str,
    spec: PinConnectivityAnalysis,
    source_case: str,
    relationship: str,
    check_results: tuple[ElectricalCheck, ...],
) -> None:
    checks = {item.id: item.status for item in check_results}
    details = {item.id: item.detail for item in check_results}
    spec_digest = hashlib.sha256(
        json.dumps(
            spec.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    ctx.log.event(
        f"connector-return-fixture/pin-connectivity-contract-{case}",
        "PASS",
        project=ctx.project,
        kicad_version=ctx.config.kicad_version,
        image=ctx.pinned,
        source_sha256=ctx.source_hashes[source_case],
        netlist_sha256=ctx.netlist_hashes[source_case, "first"],
        repeat_netlist_sha256=ctx.netlist_hashes[source_case, "repeat"],
        normalized_netlist_sha256=ctx.normalized_netlist_hashes[source_case, "first"],
        repeat_normalized_netlist_sha256=ctx.normalized_netlist_hashes[source_case, "repeat"],
        pin_connectivity_contract_sha256=spec_digest,
        relationship=relationship,
        check_details=json.dumps(
            details, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ),
        contract_status="FAIL" if "FAIL" in checks.values() else "PASS",
        checks=";".join(f"{key}={value}" for key, value in sorted(checks.items())),
        repeatable="true"
        if ctx.normalized_netlist_hashes[source_case, "first"]
        == ctx.normalized_netlist_hashes[source_case, "repeat"]
        else "false",
        command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
    )


def verify_db9_return_contracts(
    ctx: ConnectorReturnFixtureContext, db9_control_nets: Mapping[str, tuple[str, ...]]
) -> None:
    """Check common and isolated DB9 requirements against only DB9 native fixtures."""
    expected_pins = tuple(f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9))
    if db9_control_nets.get("COMMON_RETURN") != expected_pins:
        raise ValueError("Common four-port DB9 control lost its eight native pin assignments")

    common_grounding = GroundingAnalysis(
        basis="Synthetic approved DB9 pinout requires all return contacts on one domain",
        domains=(GroundDomain(net="COMMON_RETURN", pins=expected_pins),),
    )
    isolated_grounding = GroundingAnalysis(
        basis="Synthetic approved DB9 pinout requires one isolated return domain per connector",
        domains=tuple(
            GroundDomain(
                net=f"RETURN_PORT_{reference}", pins=(f"J{reference}.7", f"J{reference}.9")
            )
            for reference in range(1, 5)
        ),
    )
    grounding_cases = (
        (
            "common-fault",
            common_grounding,
            "four-db9-fault",
            "common-net",
            {
                "grounding/COMMON_RETURN": "FAIL",
                "grounding/component-coverage": "PASS",
                "grounding/return-net-review": "FAIL",
            },
        ),
        (
            "common-control",
            common_grounding,
            "four-db9-control",
            "common-net",
            {
                "grounding/COMMON_RETURN": "PASS",
                "grounding/component-coverage": "PASS",
            },
        ),
        (
            "isolated-fault",
            isolated_grounding,
            "four-db9-fault",
            "separate-per-port",
            {
                **{f"grounding/RETURN_PORT_{reference}": "PASS" for reference in range(1, 5)},
                "grounding/component-coverage": "PASS",
                "grounding/return-net-review": "PASS",
            },
        ),
        (
            "isolated-control",
            isolated_grounding,
            "four-db9-control",
            "separate-per-port",
            {
                **{f"grounding/RETURN_PORT_{reference}": "FAIL" for reference in range(1, 5)},
                "grounding/component-coverage": "PASS",
            },
        ),
    )
    for case, spec, source_case, relationship, expected in grounding_cases:
        checks = {
            item.id: item.status
            for item in grounding_checks(spec, ctx.observed_contracts[source_case, "first"])
        }
        if checks != expected:
            raise ValueError(f"Four-port DB9 {case} grounding requirement changed: {checks}")
        _record_grounding_contract(
            ctx,
            case=case,
            spec=spec,
            source_case=source_case,
            relationship=relationship,
            checks=checks,
        )

    common_connectivity = PinConnectivityAnalysis(
        basis="Synthetic approved DB9 pinout requires all return contacts on one net",
        rules=(
            PinRelationshipRule(
                id="db9-common-return",
                basis="All DB9 return contacts share the approved return net",
                topology="common_net",
                pins=expected_pins,
                net="COMMON_RETURN",
            ),
        ),
    )
    isolated_connectivity = PinConnectivityAnalysis(
        basis="Synthetic approved DB9 pinout requires isolated per-connector return nets",
        rules=tuple(
            PinRelationshipRule(
                id=f"db9-{reference}-isolated-return",
                basis=f"Connector J{reference} return contacts share its isolated return net",
                topology="common_net",
                pins=(f"J{reference}.7", f"J{reference}.9"),
                net=f"RETURN_PORT_{reference}",
            )
            for reference in range(1, 5)
        ),
    )
    assigned_connectivity = PinConnectivityAnalysis(
        basis="Synthetic approved DB9 pinout requires every return contact to be wired",
        rules=(
            PinRelationshipRule(
                id="db9-returns-assigned",
                basis="Each reviewed DB9 return contact has one schematic net assignment",
                topology="assigned",
                pins=expected_pins,
            ),
        ),
    )
    pin_cases = (
        (
            "common-fault",
            common_connectivity,
            "four-db9-fault",
            "common-net",
            {
                "pin-connectivity/db9-common-return": "FAIL",
            },
        ),
        (
            "common-control",
            common_connectivity,
            "four-db9-control",
            "common-net",
            {
                "pin-connectivity/db9-common-return": "PASS",
            },
        ),
        (
            "isolated-fault",
            isolated_connectivity,
            "four-db9-fault",
            "separate-per-port",
            {
                **{
                    f"pin-connectivity/db9-{reference}-isolated-return": "PASS"
                    for reference in range(1, 5)
                },
            },
        ),
        (
            "isolated-control",
            isolated_connectivity,
            "four-db9-control",
            "separate-per-port",
            {
                **{
                    f"pin-connectivity/db9-{reference}-isolated-return": "FAIL"
                    for reference in range(1, 5)
                },
            },
        ),
        (
            "assignment-only-split-control",
            assigned_connectivity,
            "four-db9-fault",
            "assignment-only",
            {"pin-connectivity/db9-returns-assigned": "PASS"},
        ),
        (
            "assignment-only-common-control",
            assigned_connectivity,
            "four-db9-control",
            "assignment-only",
            {"pin-connectivity/db9-returns-assigned": "PASS"},
        ),
    )
    for case, spec, source_case, relationship, expected in pin_cases:
        results = pin_relationship_checks(spec, ctx.observed_contracts[source_case, "first"])
        checks = {item.id: item.status for item in results}
        if checks != expected:
            raise ValueError(f"DB9 pin-connectivity requirement {case} changed: {checks}")
        _record_pin_connectivity_contract(
            ctx,
            case=case,
            spec=spec,
            source_case=source_case,
            relationship=relationship,
            check_results=results,
        )


def verify_peer_power_pin_contracts(ctx: ConnectorReturnFixtureContext) -> None:
    """Check generic peer-power and stale-pin contract controls."""
    peer_common_power = PinConnectivityAnalysis(
        basis="Synthetic approved three-port pinout requires one shared +5V contact net",
        rules=(
            PinRelationshipRule(
                id="peer-common-power",
                basis="All three reviewed connector power contacts share +5V",
                topology="common_net",
                pins=("J1.1", "J2.1", "J3.1"),
                net="+5V",
            ),
            PinRelationshipRule(
                id="peer-power-contacts-assigned",
                basis="Each reviewed connector power contact must be wired",
                topology="assigned",
                pins=("J1.1", "J2.1", "J3.1"),
            ),
        ),
    )
    peer_independent_power = PinConnectivityAnalysis(
        basis="Synthetic approved variant has independent J1/J2 power outputs and an unused J3 pin",
        rules=(
            PinRelationshipRule(
                id="peer-independent-power-outputs",
                basis="J1 and J2 power contacts are separate switched outputs",
                topology="separate_nets",
                pins=("J1.1", "J2.1"),
            ),
            PinRelationshipRule(
                id="peer-independent-outputs-assigned",
                basis="Both reviewed switched outputs must have a net assignment",
                topology="assigned",
                pins=("J1.1", "J2.1"),
            ),
            PinRelationshipRule(
                id="peer-j3-power-unused",
                basis="J3.1 is intentionally unconnected on this approved variant",
                topology="unconnected",
                pins=("J3.1",),
            ),
        ),
    )
    stale_pin_reference = PinConnectivityAnalysis(
        basis="Synthetic contract typo must not count an absent symbol pin as unused",
        rules=(
            PinRelationshipRule(
                id="stale-pin-reference",
                basis="J1.99 is intentionally unused",
                topology="unconnected",
                pins=("J1.99",),
            ),
        ),
    )
    cases = (
        (
            "peer-common-open-fault",
            peer_common_power,
            "peer-pin-outlier-fault",
            "common-net",
            {
                "pin-connectivity/peer-common-power": "FAIL",
                "pin-connectivity/peer-power-contacts-assigned": "FAIL",
            },
        ),
        (
            "peer-common-control",
            peer_common_power,
            "peer-pin-outlier-control",
            "common-net",
            {
                "pin-connectivity/peer-common-power": "PASS",
                "pin-connectivity/peer-power-contacts-assigned": "PASS",
            },
        ),
        (
            "peer-independent-control",
            peer_independent_power,
            "peer-power-fault",
            "independent-outputs-plus-unused-contact",
            {
                "pin-connectivity/peer-independent-power-outputs": "PASS",
                "pin-connectivity/peer-independent-outputs-assigned": "PASS",
                "pin-connectivity/peer-j3-power-unused": "PASS",
            },
        ),
        (
            "peer-independent-common-net-mismatch",
            peer_independent_power,
            "peer-power-control",
            "independent-outputs-plus-unused-contact",
            {
                "pin-connectivity/peer-independent-power-outputs": "FAIL",
                "pin-connectivity/peer-independent-outputs-assigned": "PASS",
                "pin-connectivity/peer-j3-power-unused": "FAIL",
            },
        ),
        (
            "stale-pin-reference",
            stale_pin_reference,
            "four-db9-control",
            "stale-symbol-pin",
            {
                "pin-connectivity/stale-pin-reference": "FAIL",
            },
        ),
    )
    for case, spec, source_case, relationship, expected in cases:
        results = pin_relationship_checks(spec, ctx.observed_contracts[source_case, "first"])
        checks = {item.id: item.status for item in results}
        if checks != expected:
            raise ValueError(f"Pin-connectivity requirement {case} changed: {checks}")
        _record_pin_connectivity_contract(
            ctx,
            case=case,
            spec=spec,
            source_case=source_case,
            relationship=relationship,
            check_results=results,
        )


def verify_connector_grounding_contracts(
    ctx: ConnectorReturnFixtureContext, db9_control_nets: Mapping[str, tuple[str, ...]]
) -> None:
    """Verify all return-domain and peer-power pin-connectivity contracts."""
    verify_db9_return_contracts(ctx, db9_control_nets)
    verify_peer_power_pin_contracts(ctx)

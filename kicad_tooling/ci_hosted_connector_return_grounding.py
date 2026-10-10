"""Verify authored return-domain and pin-connectivity contracts."""

from __future__ import annotations

import json
from collections.abc import Mapping

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def verify_connector_grounding_contracts(
    ctx: ConnectorReturnFixtureContext, db9_control_nets: Mapping[str, tuple[str, ...]]
):
    """Verify authored return-domain and pin-connectivity contracts."""
    import hashlib

    from .hwrepo.electrical import grounding_checks, pin_relationship_checks
    from .hwrepo.models import (
        GroundDomain,
        GroundingAnalysis,
        PinConnectivityAnalysis,
        PinRelationshipRule,
    )

    if db9_control_nets.get("COMMON_RETURN") != tuple(
        f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9)
    ):
        raise ValueError("Common four-port DB9 control lost its eight native pin assignments")
    db9_return_pins = tuple(f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9))
    common_grounding = GroundingAnalysis(
        basis="Synthetic approved DB9 pinout requires all return contacts on one domain",
        domains=(GroundDomain(net="COMMON_RETURN", pins=db9_return_pins),),
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
    expected_grounding_results = {
        "common-fault": {
            "grounding/COMMON_RETURN": "FAIL",
            "grounding/component-coverage": "PASS",
            "grounding/return-net-review": "FAIL",
        },
        "common-control": {
            "grounding/COMMON_RETURN": "PASS",
            "grounding/component-coverage": "PASS",
        },
        "isolated-fault": {
            **{f"grounding/RETURN_PORT_{reference}": "PASS" for reference in range(1, 5)},
            "grounding/component-coverage": "PASS",
            "grounding/return-net-review": "PASS",
        },
        "isolated-control": {
            **{f"grounding/RETURN_PORT_{reference}": "FAIL" for reference in range(1, 5)},
            "grounding/component-coverage": "PASS",
        },
    }
    grounding_cases = {
        "common-fault": (common_grounding, "four-db9-fault", "common-net"),
        "common-control": (common_grounding, "four-db9-control", "common-net"),
        "isolated-fault": (isolated_grounding, "four-db9-fault", "separate-per-port"),
        "isolated-control": (isolated_grounding, "four-db9-control", "separate-per-port"),
    }
    for case, (spec, source_case, relationship) in grounding_cases.items():
        checks = {
            item.id: item.status
            for item in grounding_checks(spec, ctx.observed_contracts[source_case, "first"])
        }
        if checks != expected_grounding_results[case]:
            raise ValueError(f"Four-port DB9 {case} grounding requirement changed: {checks}")
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
            contract_status="FAIL"
            if any(status == "FAIL" for status in checks.values())
            else "PASS",
            checks=";".join(
                f"{check_id}={status}" for (check_id, status) in sorted(checks.items())
            ),
            repeatable="true"
            if ctx.normalized_netlist_hashes[source_case, "first"]
            == ctx.normalized_netlist_hashes[source_case, "repeat"]
            else "false",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )
    common_pin_connectivity = PinConnectivityAnalysis(
        basis="Synthetic approved DB9 pinout requires all return contacts on one net",
        rules=(
            PinRelationshipRule(
                id="db9-common-return",
                basis="All DB9 return contacts share the approved return net",
                topology="common_net",
                pins=db9_return_pins,
                net="COMMON_RETURN",
            ),
        ),
    )
    isolated_pin_connectivity = PinConnectivityAnalysis(
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
    expected_pin_connectivity_results = {
        "common-fault": {"pin-connectivity/db9-common-return": "FAIL"},
        "common-control": {"pin-connectivity/db9-common-return": "PASS"},
        "isolated-fault": {
            **{
                f"pin-connectivity/db9-{reference}-isolated-return": "PASS"
                for reference in range(1, 5)
            }
        },
        "isolated-control": {
            **{
                f"pin-connectivity/db9-{reference}-isolated-return": "FAIL"
                for reference in range(1, 5)
            }
        },
        "peer-common-open-fault": {"pin-connectivity/peer-common-power": "FAIL"},
        "peer-common-control": {"pin-connectivity/peer-common-power": "PASS"},
        "peer-independent-control": {
            "pin-connectivity/peer-independent-power-outputs": "PASS",
            "pin-connectivity/peer-j3-power-unused": "PASS",
        },
        "peer-independent-common-net-mismatch": {
            "pin-connectivity/peer-independent-power-outputs": "FAIL",
            "pin-connectivity/peer-j3-power-unused": "FAIL",
        },
        "stale-pin-reference": {"pin-connectivity/stale-pin-reference": "FAIL"},
    }
    pin_connectivity_cases = {
        "common-fault": (common_pin_connectivity, "four-db9-fault", "common-net"),
        "common-control": (common_pin_connectivity, "four-db9-control", "common-net"),
        "isolated-fault": (isolated_pin_connectivity, "four-db9-fault", "separate-per-port"),
        "isolated-control": (isolated_pin_connectivity, "four-db9-control", "separate-per-port"),
        "peer-common-open-fault": (peer_common_power, "peer-pin-outlier-fault", "common-net"),
        "peer-common-control": (peer_common_power, "peer-pin-outlier-control", "common-net"),
        "peer-independent-control": (
            peer_independent_power,
            "peer-power-fault",
            "independent-outputs-plus-unused-contact",
        ),
        "peer-independent-common-net-mismatch": (
            peer_independent_power,
            "peer-power-control",
            "independent-outputs-plus-unused-contact",
        ),
        "stale-pin-reference": (stale_pin_reference, "four-db9-control", "stale-symbol-pin"),
    }
    for case, (spec, source_case, relationship) in pin_connectivity_cases.items():
        check_results = pin_relationship_checks(spec, ctx.observed_contracts[source_case, "first"])
        checks = {item.id: item.status for item in check_results}
        check_details = {item.id: item.detail for item in check_results}
        if checks != expected_pin_connectivity_results[case]:
            raise ValueError(f"Pin-connectivity requirement {case} changed: {checks}")
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
                check_details, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ),
            contract_status="FAIL"
            if any(status == "FAIL" for status in checks.values())
            else "PASS",
            checks=";".join(
                f"{check_id}={status}" for (check_id, status) in sorted(checks.items())
            ),
            repeatable="true"
            if ctx.normalized_netlist_hashes[source_case, "first"]
            == ctx.normalized_netlist_hashes[source_case, "repeat"]
            else "false",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )

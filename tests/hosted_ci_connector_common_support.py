"""Shared result checks for native connector fixture reports."""

from __future__ import annotations


def assert_connector_result_sources(testcase, results, version, cases):
    for case in cases:
        result = results[f"connector-return-fixture/{case}"]
        testcase.assertEqual(result["kicad_version"], version)
        testcase.assertEqual(result["repeatable"], "true")


def normalized_connector_return_patterns(results):
    cases = (
        "four-db9-fault",
        "four-db9-control",
        "four-db9-neutral-fault",
        "four-db9-neutral-control",
        "peer-power-fault",
        "peer-power-control",
        "peer-pin-outlier-fault",
        "peer-pin-outlier-control",
        "peer-pin-part-id-open-fault",
        "peer-pin-part-id-common-control",
        "peer-pin-part-id-split-fault",
        "two-peer-open-fault",
        "two-peer-no-connect-fault",
        "two-peer-common-control",
        "single-offboard-port-control",
        "peer-pin-minority-fault",
        "peer-pin-divergence-fault",
        "generic-placeholder-divergence-fault",
        "generic-placeholder-control",
        "peer-scope-split-return-fault",
        "reviewed-role-fault",
        "reviewed-role-control",
        "reviewed-supply-fault",
        "reviewed-supply-control",
        "reviewed-supply-domain-control",
        "unconnected-generic-power-input-fault",
        "unconnected-generic-power-input-control",
    )
    return {
        case: results[f"connector-return-fixture/{case}"]["normalized_netlist_sha256"]
        for case in cases
    }

"""Theme-owned assertions for synthetic connector native fixtures."""

from __future__ import annotations

import json

from tests.hosted_ci_connector_common_support import assert_connector_result_sources


def assert_base_connector_return_cases(testcase, results, version):
    fault = results["connector-return-fixture/fault"]
    control = results["connector-return-fixture/control"]
    testcase.assertEqual(fault["status"], "PASS")
    testcase.assertEqual(fault["lint_status"], "REVIEW")
    testcase.assertEqual(
        set(fault["findings"].split(",")),
        {"connector.repeated_pin_function", "net.numbered_returns"},
    )
    testcase.assertEqual(control["status"], "PASS")
    testcase.assertEqual(control["lint_status"], "PASS")
    testcase.assertEqual(control["findings"], "none")

    cross_fault = results["connector-return-fixture/cross-symbol-fault"]
    testcase.assertEqual(cross_fault["lint_status"], "REVIEW")
    testcase.assertEqual(
        set(cross_fault["subjects"].split(";")),
        {
            "multiple connector symbols: ground/return",
            "multiple connector symbols: PWR",
        },
    )
    testcase.assertIn("J3.1=SHIELD", cross_fault["pin_functions"])
    cross_control = results["connector-return-fixture/cross-symbol-control"]
    testcase.assertEqual(cross_control["lint_status"], "PASS")
    testcase.assertEqual(cross_control["findings"], "none")
    cross_open = results["connector-return-fixture/cross-symbol-open"]
    testcase.assertEqual(cross_open["lint_status"], "REVIEW")
    testcase.assertEqual(cross_open["subjects"], "multiple connector symbols: ground/return")
    assert_connector_result_sources(
        testcase,
        results,
        version,
        ("fault", "control", "cross-symbol-fault", "cross-symbol-control", "cross-symbol-open"),
    )


def assert_grounding_contract_cases(testcase, results, version):
    db9_fault = results["connector-return-fixture/four-db9-fault"]
    db9_control = results["connector-return-fixture/four-db9-control"]
    testcase.assertEqual(db9_fault["status"], "PASS")
    testcase.assertEqual(db9_fault["lint_status"], "REVIEW")
    testcase.assertEqual(
        set(db9_fault["findings"].split(",")),
        {"connector.repeated_pin_function", "net.numbered_returns"},
    )
    testcase.assertIn("J4.7=GND", db9_fault["pin_functions"])
    testcase.assertIn("J4.9=GND", db9_fault["pin_functions"])
    testcase.assertEqual(db9_control["status"], "PASS")
    testcase.assertEqual(db9_control["lint_status"], "PASS")
    testcase.assertEqual(db9_control["findings"], "none")
    assert_connector_result_sources(
        testcase,
        results,
        version,
        (
            "four-db9-fault",
            "four-db9-control",
            "four-db9-neutral-fault",
            "four-db9-neutral-control",
        ),
    )
    grounding_expectations = {
        "ground-contract-common-fault": "FAIL",
        "ground-contract-common-control": "PASS",
        "ground-contract-isolated-fault": "PASS",
        "ground-contract-isolated-control": "FAIL",
    }
    for case, expected_contract_status in grounding_expectations.items():
        result = results[f"connector-return-fixture/{case}"]
        testcase.assertEqual(result["status"], "PASS")
        testcase.assertEqual(result["contract_status"], expected_contract_status)
        testcase.assertEqual(result["kicad_version"], version)
        testcase.assertEqual(result["repeatable"], "true")
        testcase.assertRegex(result["grounding_contract_sha256"], r"^[0-9a-f]{64}$")
    testcase.assertEqual(
        results["connector-return-fixture/ground-contract-common-fault"]["checks"],
        "grounding/COMMON_RETURN=FAIL;grounding/component-coverage=PASS;"
        "grounding/return-net-review=FAIL",
    )
    testcase.assertEqual(
        results["connector-return-fixture/ground-contract-common-control"]["checks"],
        "grounding/COMMON_RETURN=PASS;grounding/component-coverage=PASS",
    )
    pin_connectivity_expectations = {
        "common-fault": "FAIL",
        "common-control": "PASS",
        "isolated-fault": "PASS",
        "isolated-control": "FAIL",
        "peer-common-open-fault": "FAIL",
        "peer-common-control": "PASS",
        "peer-independent-control": "PASS",
        "peer-independent-common-net-mismatch": "FAIL",
        "stale-pin-reference": "FAIL",
    }
    for case, expected_contract_status in pin_connectivity_expectations.items():
        result = results[f"connector-return-fixture/pin-connectivity-contract-{case}"]
        testcase.assertEqual(result["status"], "PASS")
        testcase.assertEqual(result["contract_status"], expected_contract_status)
        testcase.assertEqual(result["kicad_version"], version)
        testcase.assertEqual(result["repeatable"], "true")
        testcase.assertRegex(result["pin_connectivity_contract_sha256"], r"^[0-9a-f]{64}$")
    testcase.assertEqual(
        results["connector-return-fixture/pin-connectivity-contract-common-fault"]["checks"],
        "pin-connectivity/db9-common-return=FAIL",
    )
    testcase.assertEqual(
        results["connector-return-fixture/pin-connectivity-contract-common-control"]["checks"],
        "pin-connectivity/db9-common-return=PASS",
    )
    testcase.assertEqual(
        results["connector-return-fixture/pin-connectivity-contract-isolated-fault"]["checks"],
        ";".join(
            f"pin-connectivity/db9-{reference}-isolated-return=PASS" for reference in range(1, 5)
        ),
    )
    testcase.assertEqual(
        results["connector-return-fixture/pin-connectivity-contract-isolated-control"]["checks"],
        ";".join(
            f"pin-connectivity/db9-{reference}-isolated-return=FAIL" for reference in range(1, 5)
        ),
    )
    testcase.assertEqual(
        results["connector-return-fixture/pin-connectivity-contract-peer-common-open-fault"][
            "checks"
        ],
        "pin-connectivity/peer-common-power=FAIL",
    )
    testcase.assertEqual(
        results["connector-return-fixture/pin-connectivity-contract-peer-common-control"]["checks"],
        "pin-connectivity/peer-common-power=PASS",
    )
    testcase.assertEqual(
        results["connector-return-fixture/pin-connectivity-contract-peer-independent-control"][
            "checks"
        ],
        "pin-connectivity/peer-independent-power-outputs=PASS;"
        "pin-connectivity/peer-j3-power-unused=PASS",
    )
    testcase.assertEqual(
        results[
            "connector-return-fixture/"
            "pin-connectivity-contract-peer-independent-common-net-mismatch"
        ]["checks"],
        "pin-connectivity/peer-independent-power-outputs=FAIL;"
        "pin-connectivity/peer-j3-power-unused=FAIL",
    )
    stale_pin = results["connector-return-fixture/pin-connectivity-contract-stale-pin-reference"]
    testcase.assertEqual(stale_pin["relationship"], "stale-symbol-pin")
    testcase.assertIn(
        "unknown symbol pins=['J1.99']",
        json.loads(stale_pin["check_details"])["pin-connectivity/stale-pin-reference"],
    )
    neutral_fault = results["connector-return-fixture/four-db9-neutral-fault"]
    neutral_control = results["connector-return-fixture/four-db9-neutral-control"]
    testcase.assertEqual(neutral_fault["status"], "PASS")
    testcase.assertEqual(neutral_fault["lint_status"], "REVIEW")
    testcase.assertEqual(
        set(neutral_fault["findings"].split(",")),
        {"connector.repeated_pin_function", "connector.no_connected_return"},
    )
    testcase.assertEqual(
        set(neutral_fault["subjects"].split(";")),
        {
            "Lint:DB9: 7",
            "Lint:DB9: 9",
            *(f"J{reference}: no connected return" for reference in range(1, 5)),
        },
    )
    testcase.assertIn("J1.7=7", neutral_fault["pin_functions"])
    testcase.assertIn("J1.9=9", neutral_fault["pin_functions"])
    testcase.assertEqual(neutral_control["status"], "PASS")
    testcase.assertEqual(neutral_control["lint_status"], "REVIEW")
    testcase.assertEqual(
        set(neutral_control["findings"].split(",")),
        {"connector.no_connected_return"},
    )
    testcase.assertEqual(
        set(neutral_control["subjects"].split(";")),
        {f"J{reference}: no connected return" for reference in range(1, 5)},
    )

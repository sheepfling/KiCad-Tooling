"""Theme-owned assertions for synthetic connector native fixtures."""

from __future__ import annotations

import json
import re

from tests.hosted_ci_connector_common_support import assert_connector_result_sources


def assert_base_connector_return_cases(results, version):
    fault = results["connector-return-fixture/fault"]
    control = results["connector-return-fixture/control"]
    assert fault["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert set(fault["findings"].split(",")) == {
        "connector.repeated_pin_function",
        "net.numbered_returns",
    }
    assert control["status"] == "PASS"
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"

    cross_fault = results["connector-return-fixture/cross-symbol-fault"]
    assert cross_fault["lint_status"] == "REVIEW"
    assert set(cross_fault["subjects"].split(";")) == {
        "multiple connector symbols: ground/return",
        "multiple connector symbols: PWR",
    }
    assert "J3.1=SHIELD" in cross_fault["pin_functions"]
    cross_control = results["connector-return-fixture/cross-symbol-control"]
    assert cross_control["lint_status"] == "PASS"
    assert cross_control["findings"] == "none"
    cross_open = results["connector-return-fixture/cross-symbol-open"]
    assert cross_open["lint_status"] == "REVIEW"
    assert cross_open["subjects"] == "multiple connector symbols: ground/return"
    assert_connector_result_sources(
        results,
        version,
        ("fault", "control", "cross-symbol-fault", "cross-symbol-control", "cross-symbol-open"),
    )


def assert_positive_rail_return_cases(results, version):
    fault = results["connector-return-fixture/return-positive-rail-fault"]
    control = results["connector-return-fixture/return-positive-rail-control"]
    assert fault["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert "connector.return_pin_on_positive_rail" in fault["findings"].split(",")
    assert "J1.1=GND" in fault["pin_functions"]
    assert "J1.2=GND" in fault["pin_functions"]
    finding_subject_pairs = tuple(
        zip(fault["findings"].split(","), fault["subjects"].split(";"), strict=True)
    )
    assert {
        subject
        for rule_id, subject in finding_subject_pairs
        if rule_id == "connector.return_pin_on_positive_rail"
    } == {"J1.1: return assigned to +5V", "J1.2: return assigned to +5V"}
    assert control["status"] == "PASS"
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"
    assert_connector_result_sources(
        results, version, ("return-positive-rail-fault", "return-positive-rail-control")
    )


def assert_grounding_contract_cases(results, version):
    db9_fault = results["connector-return-fixture/four-db9-fault"]
    db9_control = results["connector-return-fixture/four-db9-control"]
    assert db9_fault["status"] == "PASS"
    assert db9_fault["lint_status"] == "REVIEW"
    assert set(db9_fault["findings"].split(",")) == {
        "connector.repeated_pin_function",
        "net.numbered_returns",
    }
    assert "J4.7=GND" in db9_fault["pin_functions"]
    assert "J4.9=GND" in db9_fault["pin_functions"]
    assert db9_control["status"] == "PASS"
    assert db9_control["lint_status"] == "PASS"
    assert db9_control["findings"] == "none"
    assert_connector_result_sources(
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
        assert result["status"] == "PASS"
        assert result["contract_status"] == expected_contract_status
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert re.search("^[0-9a-f]{64}$", result["grounding_contract_sha256"])
    assert (
        results["connector-return-fixture/ground-contract-common-fault"]["checks"]
        == "grounding/COMMON_RETURN=FAIL;grounding/component-coverage=PASS;grounding/return-net-review=FAIL"
    )
    assert (
        results["connector-return-fixture/ground-contract-common-control"]["checks"]
        == "grounding/COMMON_RETURN=PASS;grounding/component-coverage=PASS"
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
        assert result["status"] == "PASS"
        assert result["contract_status"] == expected_contract_status
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert re.search("^[0-9a-f]{64}$", result["pin_connectivity_contract_sha256"])
    assert (
        results["connector-return-fixture/pin-connectivity-contract-common-fault"]["checks"]
        == "pin-connectivity/db9-common-return=FAIL"
    )
    assert (
        results["connector-return-fixture/pin-connectivity-contract-common-control"]["checks"]
        == "pin-connectivity/db9-common-return=PASS"
    )
    assert results["connector-return-fixture/pin-connectivity-contract-isolated-fault"][
        "checks"
    ] == ";".join(
        f"pin-connectivity/db9-{reference}-isolated-return=PASS" for reference in range(1, 5)
    )
    assert results["connector-return-fixture/pin-connectivity-contract-isolated-control"][
        "checks"
    ] == ";".join(
        f"pin-connectivity/db9-{reference}-isolated-return=FAIL" for reference in range(1, 5)
    )
    assert (
        results["connector-return-fixture/pin-connectivity-contract-peer-common-open-fault"][
            "checks"
        ]
        == "pin-connectivity/peer-common-power=FAIL;"
        "pin-connectivity/peer-power-contacts-assigned=FAIL"
    )
    assert (
        results["connector-return-fixture/pin-connectivity-contract-peer-common-control"]["checks"]
        == "pin-connectivity/peer-common-power=PASS;"
        "pin-connectivity/peer-power-contacts-assigned=PASS"
    )
    assert (
        results["connector-return-fixture/pin-connectivity-contract-peer-independent-control"][
            "checks"
        ]
        == "pin-connectivity/peer-independent-outputs-assigned=PASS;"
        "pin-connectivity/peer-independent-power-outputs=PASS;"
        "pin-connectivity/peer-j3-power-unused=PASS"
    )
    assert (
        results[
            "connector-return-fixture/pin-connectivity-contract-peer-independent-common-net-mismatch"
        ]["checks"]
        == "pin-connectivity/peer-independent-outputs-assigned=PASS;"
        "pin-connectivity/peer-independent-power-outputs=FAIL;"
        "pin-connectivity/peer-j3-power-unused=FAIL"
    )
    stale_pin = results["connector-return-fixture/pin-connectivity-contract-stale-pin-reference"]
    assert stale_pin["relationship"] == "stale-symbol-pin"
    assert (
        "unknown symbol pins=['J1.99']"
        in json.loads(stale_pin["check_details"])["pin-connectivity/stale-pin-reference"]
    )
    neutral_fault = results["connector-return-fixture/four-db9-neutral-fault"]
    neutral_control = results["connector-return-fixture/four-db9-neutral-control"]
    assert neutral_fault["status"] == "PASS"
    assert neutral_fault["lint_status"] == "REVIEW"
    assert set(neutral_fault["findings"].split(",")) == {
        "connector.repeated_pin_function",
        "connector.no_connected_return",
    }
    assert set(neutral_fault["subjects"].split(";")) == {
        "Lint:DB9: 7",
        "Lint:DB9: 9",
        *(f"J{reference}: no connected return" for reference in range(1, 5)),
    }
    assert "J1.7=7" in neutral_fault["pin_functions"]
    assert "J1.9=9" in neutral_fault["pin_functions"]
    assert neutral_control["status"] == "PASS"
    assert neutral_control["lint_status"] == "REVIEW"
    assert set(neutral_control["findings"].split(",")) == {"connector.no_connected_return"}
    assert set(neutral_control["subjects"].split(";")) == {
        f"J{reference}: no connected return" for reference in range(1, 5)
    }

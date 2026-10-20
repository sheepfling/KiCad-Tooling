"""Check source hashes, replay stability, and native export receipts."""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint]


def test_connector_fixture_results_are_source_bound_and_repeatable(
    connector_return_fixture_results: SimpleNamespace,
) -> None:
    lane = connector_return_fixture_results
    results = lane.results
    fixture_results = {
        stage.removeprefix("connector-return-fixture/"): result
        for stage, result in results.items()
        if stage != "connector-return-fixture/native-export"
    }

    assert set(lane.cases) <= set(fixture_results)
    for case in lane.cases:
        result = fixture_results[case]
        assert result["status"] == "PASS"
        assert result["netlist_sha256"] != result["repeat_netlist_sha256"]
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])

    fault = results["connector-return-fixture/fault"]
    control = results["connector-return-fixture/control"]
    assert (lane.root / fault["command_receipt"]).is_file()
    assert fault["source_sha256"] != control["source_sha256"]
    native_export = results["connector-return-fixture/native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == lane.version == "10.0.0"

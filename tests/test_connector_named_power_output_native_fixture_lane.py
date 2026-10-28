"""Exact-version native fixtures for named connector power-output aliases."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted_connector_named_power_output import (
    ALL_OPEN_RULE_ID,
    CASES,
    DIVERGENCE_RULE_ID,
    RULE_ID,
    verify_connector_named_power_output_cases,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]


def test_named_connector_power_output_fixture_sources_match_reviewed_digests() -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures/design_lint/connector-named-power-output-peer-native"
    )
    expected = {
        "fault.kicad_sch": "ef721f666d540f3ce99598fcf9e52a494729e6cdbd56b57798fd260c10bc40be",
        "control.kicad_sch": "e5621a2b8f8660db341ffe5a4088c1b802c28d1b624e522434516f0235de7d71",
        "all-open-fault.kicad_sch": "e16ae20d4f198fdf648049f7571bdf4db0842518bd54f8c7536d89655e93b12b",
        "divergent-fault.kicad_sch": "915340d72ad323d01266b90948d8a42fb55bd0879ceb74cea9b71a667f5a649a",
    }

    assert {
        name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest() for name in expected
    } == expected


def test_named_connector_power_output_hosted_case_validator_accepts_all_four_cases() -> None:
    fault_case, control_case, all_open_case, divergent_case = CASES
    symbols = {
        "J1": "Lint:NamedPeerPowerOutputA",
        "J2": "Lint:NamedPeerPowerOutputB",
    }
    components = {
        reference: SimpleNamespace(part_id="SYNTHETIC-CONNECTOR-NAMED-OUTPUT-001")
        for reference in symbols
    }
    reports = {
        (fault_case, "first"): SimpleNamespace(
            findings=(
                SimpleNamespace(
                    rule_id=RULE_ID,
                    evidence={"J1.1": ("+3V3",), "J2.1": ()},
                ),
            )
        ),
        (control_case, "first"): SimpleNamespace(findings=()),
        (all_open_case, "first"): SimpleNamespace(
            findings=(
                SimpleNamespace(
                    rule_id=ALL_OPEN_RULE_ID,
                    evidence={"J1.1": (), "J2.1": ()},
                ),
            )
        ),
        (divergent_case, "first"): SimpleNamespace(
            findings=(
                SimpleNamespace(
                    rule_id=DIVERGENCE_RULE_ID,
                    evidence={"J1.1": ("+3V3",), "J2.1": ("+5V",)},
                ),
            )
        ),
    }
    observed_contracts = {
        (fault_case, "first"): SimpleNamespace(
            component_symbols=symbols,
            components=components,
            component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
            pin_functions={"J1.1": "BIAS_OUT", "J2.1": "BIAS_OUT"},
            pin_electrical_types={"J1.1": "power_out", "J2.1": "power_out"},
        ),
        (control_case, "first"): SimpleNamespace(nets={"+3V3": ("J1.1", "J2.1")}),
        (all_open_case, "first"): SimpleNamespace(
            component_symbols=symbols,
            components=components,
            component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
            pin_functions={"J1.1": "BIAS_OUT", "J2.1": "BIAS_OUT"},
            pin_electrical_types={"J1.1": "power_out", "J2.1": "power_out"},
            nets={"SIGNAL": ("J1.2", "J2.2")},
        ),
        (divergent_case, "first"): SimpleNamespace(
            component_symbols=symbols,
            components=components,
            component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
            pin_functions={"J1.1": "BIAS_OUT", "J2.1": "BIAS_OUT"},
            pin_electrical_types={"J1.1": "power_out", "J2.1": "power_out"},
            nets={"+3V3": ("J1.1",), "+5V": ("J2.1",), "SIGNAL": ("J1.2", "J2.2")},
        ),
    }

    verify_connector_named_power_output_cases(
        SimpleNamespace(cases=CASES, reports=reports, observed_contracts=observed_contracts)
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="pinned native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_connector_named_power_output_alias_fault_and_control_are_repeatable(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted_connector_named_power_output_lane import (
        connector_named_power_output_fixture_lane,
    )

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == image

    log = HostedLog(root, f"native-connector-named-power-output-{project}")
    connector_named_power_output_fixture_lane(root, project=project, image=config.image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    prefix = "connector-named-power-output-peer-fixture/"
    results = {
        item["stage"].removeprefix(prefix): item
        for item in events
        if item.get("stage", "").startswith(prefix)
    }
    assert set(results) == {"native-export", *CASES}
    native_export = results["native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    fault = results[CASES[0]]
    control = results[CASES[1]]
    all_open = results[CASES[2]]
    divergent = results[CASES[3]]
    assert fault["status"] == control["status"] == all_open["status"] == "PASS"
    assert divergent["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert RULE_ID in fault["findings"].split(",")
    assert control["lint_status"] in {"PASS", "REVIEW"}
    assert not {RULE_ID, ALL_OPEN_RULE_ID, DIVERGENCE_RULE_ID}.intersection(
        control["findings"].split(",")
    )
    assert all_open["lint_status"] == "REVIEW"
    assert ALL_OPEN_RULE_ID in all_open["findings"].split(",")
    assert RULE_ID not in all_open["findings"].split(",")
    assert divergent["lint_status"] == "REVIEW"
    assert DIVERGENCE_RULE_ID in divergent["findings"].split(",")
    assert not {RULE_ID, ALL_OPEN_RULE_ID}.intersection(divergent["findings"].split(","))
    for result in (fault, control, all_open, divergent):
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]

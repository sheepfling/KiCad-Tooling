"""Shared source-hashed native runner for two-pin component fault/control cases."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from kicad_tooling.ci_hosted import HostedLog, two_pin_component_fixture_lane
from kicad_tooling.ci_hosted_two_pin_component_cases import (
    two_pin_component_fixture_cases_for_rules,
)
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures.two_pin_component_sources import TWO_PIN_COMPONENT_SOURCE_HASHES
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)


def run_native_two_pin_rule_fixture(
    tmp_path: Path,
    *,
    kicad_version: str,
    rule_id: str,
) -> dict[str, dict[str, str]]:
    """Run one selected rule against its pinned native fault/control fixtures."""
    selected_cases = two_pin_component_fixture_cases_for_rules((rule_id,))
    fixture_root = Path(__file__).resolve().parents[2] / "tests/fixtures/design_lint"
    for filename, _, _ in selected_cases.values():
        source = fixture_root / filename
        assert (
            hashlib.sha256(source.read_bytes()).hexdigest()
            == TWO_PIN_COMPONENT_SOURCE_HASHES[filename]
        )

    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        kicad_version=kicad_version,
        image=PINNED_NATIVE_KICAD_IMAGES[kicad_version],
    )
    config = selected_config(root, "controller")
    assert config.kicad_version == kicad_version
    assert config.image == PINNED_NATIVE_KICAD_IMAGES[kicad_version]

    log = HostedLog(root, f"native-two-pin-component-{kicad_version}")
    two_pin_component_fixture_lane(
        root,
        project="controller",
        image=config.image,
        log=log,
        rule_ids=(rule_id,),
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("two-pin-component-fixture/")
    }
    expected_cases = {
        f"two-pin-component-fixture/{name}" for name in ("native-export", *selected_cases)
    }
    assert set(results) == expected_cases
    native_export = results["two-pin-component-fixture/native-export"]
    assert native_export["status"] == "PASS"
    receipt = root / native_export["command_receipt"]
    assert receipt.is_file()
    argv = json.loads(receipt.read_text(encoding="utf-8"))["argv"]
    assert config.image in argv
    assert argv[argv.index("--network") + 1] == "none"
    assert "--read-only" in argv
    mounts = tuple(argv[index + 1] for index, argument in enumerate(argv[:-1]) if argument == "-v")
    assert len(mounts) == 2
    assert sum(mount.endswith(":/fixtures:ro") for mount in mounts) == 1
    assert sum(mount.endswith(":/output:rw") for mount in mounts) == 1

    for case, (filename, case_rule_id, expected_subjects) in selected_cases.items():
        result = results[f"two-pin-component-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["component_rule"] == case_rule_id == rule_id
        assert result["source_sha256"] == TWO_PIN_COMPONENT_SOURCE_HASHES[filename]
        expected_findings = ";".join(sorted(expected_subjects)) or "none"
        assert result["component_findings"] == expected_findings
        assert result["lint_status"] == ("REVIEW" if expected_subjects else "PASS")
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]

    return results

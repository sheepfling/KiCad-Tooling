"""Exact-version native export evidence for scoped unanchored all-open aliases."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.connector_coverage import source_matched_connector_peer_assignment_groups
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.design_lint_connector_footprint_candidates import (
    connector_footprint_peer_pin_candidates,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.validate import read_netlist
from tests.design_lint_fixtures.connector_peer_pin_all_open import (
    generic_open_peer_coverage,
)
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

_RULE_ID = "connector.footprint_peer_pin_all_open"
_FIXTURE = (
    Path(__file__).parent
    / "fixtures/design_lint/connector-footprint-alias-native/unanchored-all-open-fault.kicad_sch"
)
_SOURCE_SHA256 = "6fef8dab77b5ebab8459a8bf4456152a87c29fd60cd02b229e92b35119c5363f"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
        reason="native connector fixtures run in the digest-pinned acceptance lane",
    ),
]


@pytest.mark.design_lint_rule(rule_id=_RULE_ID)
@pytest.mark.parametrize("kicad_version", tuple(PINNED_NATIVE_KICAD_IMAGES))
def test_native_export_reviews_unanchored_aliases_only_in_current_shared_scope(
    tmp_path: Path,
    kicad_version: str,
) -> None:
    assert hashlib.sha256(_FIXTURE.read_bytes()).hexdigest() == _SOURCE_SHA256
    work = tmp_path / "native-work"
    fixture_dir = work / "fixtures"
    output_dir = work / "outputs"
    receipt_dir = tmp_path / "receipts"
    for directory in (fixture_dir, output_dir, receipt_dir):
        directory.mkdir(parents=True, exist_ok=True)
    source = fixture_dir / _FIXTURE.name
    shutil.copyfile(_FIXTURE, source)
    image = PINNED_NATIVE_KICAD_IMAGES[kicad_version]

    version = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        work,
        home_directory=f"footprint-peer-open-{kicad_version}",
        fixture_directory=fixture_dir,
        output_directory=output_dir,
    )
    assert version.returncode == 0
    assert version.stdout.strip() == kicad_version

    exports = []
    for run in ("first", "repeat"):
        output = output_dir / f"{run}.netlist.xml"
        command = execute_kicad_cli(
            image,
            (
                "kicad-cli",
                "sch",
                "export",
                "netlist",
                "--format",
                "kicadxml",
                "--output",
                str(output),
                str(source),
            ),
            work,
            home_directory=f"footprint-peer-open-{kicad_version}-{run}",
            fixture_directory=fixture_dir,
            output_directory=output_dir,
        )
        assert command.returncode == 0, command.model_dump_json(indent=2)
        exports.append((read_netlist(output), digest(output)))
        write_model(receipt_dir / f"{run}.command.json", command)

    observed, _ = exports[0]
    assert exports[0][0] == exports[1][0]
    assert observed.nets == {}
    assert set(observed.component_symbols) == {"J1", "J2"}
    assert observed.component_pin_numbers == {"J1": ("1", "2"), "J2": ("1", "2")}
    assert observed.component_symbols["J1"] != observed.component_symbols["J2"]
    assert all(component.part_id is None for component in observed.components.values())

    shared = generic_open_peer_coverage(observed, groups=("serial-peers", "serial-peers"))
    groups = source_matched_connector_peer_assignment_groups(observed, shared)
    findings = tuple(
        item
        for item in connector_footprint_peer_pin_candidates(
            observed,
            peer_assignment_groups=groups,
            connector_coverage=shared,
        )
        if item.rule_id == _RULE_ID
    )
    assert len(findings) == 2
    assert {item.evidence["pin_number"] for item in findings} == {("1",), ("2",)}
    assert all(item.evidence["common_anchor_pin_numbers"] == () for item in findings)
    assert all(item.evidence["peer_assignment_group"] == ("serial-peers",) for item in findings)

    separate = generic_open_peer_coverage(observed, groups=("serial-a", "serial-b"))
    assert not tuple(
        item
        for item in connector_footprint_peer_pin_candidates(
            observed,
            peer_assignment_groups=source_matched_connector_peer_assignment_groups(
                observed,
                separate,
            ),
            connector_coverage=separate,
        )
        if item.rule_id == _RULE_ID
    )
    assert_native_fixture_mounts(tmp_path, "receipts/repeat.command.json")

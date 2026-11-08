"""Exact-version native evidence for scoped all-open connector contacts."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.connector_comparison_scope_types import ConnectorComparisonScope
from kicad_tooling.hwrepo.connector_peer_pin_all_open import (
    all_open_generic_connector_peer_pin_candidates,
)
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.validate import read_netlist
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.native_kicad_support import execute_kicad_cli
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

RULE_ID = "connector.generic_peer_pin_all_open"
FIXTURE = (
    Path(__file__).parent
    / "fixtures/design_lint/generic-peer-reviewed-scope-all-open-native/fault.kicad_sch"
)
SOURCE_SHA256 = "37fdbd5d0691e3bb44e6f8ef2b7cc4ee26e484f85a0c5160199f9b2f17e23cf3"

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


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("kicad_version", tuple(PINNED_NATIVE_KICAD_IMAGES))
def test_native_peer_group_scope_reviews_all_open_generic_contact(
    tmp_path: Path,
    kicad_version: str,
) -> None:
    source_bytes = FIXTURE.read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest() == SOURCE_SHA256

    image = PINNED_NATIVE_KICAD_IMAGES[kicad_version]
    work = tmp_path / "native-work"
    fixture_dir = work / "fixtures"
    output_dir = work / "outputs"
    receipt_dir = tmp_path / "receipts"
    for directory in (fixture_dir, output_dir, receipt_dir):
        directory.mkdir(parents=True, exist_ok=True)
    source = fixture_dir / FIXTURE.name
    shutil.copyfile(FIXTURE, source)

    version = execute_kicad_cli(
        image,
        ("kicad-cli", "version"),
        work,
        home_directory=f"connector-reviewed-open-version-{kicad_version}",
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
            home_directory=f"connector-reviewed-open-{kicad_version}-{run}",
            fixture_directory=fixture_dir,
            output_directory=output_dir,
        )
        assert command.returncode == 0, command.model_dump_json(indent=2)
        assert output.is_file()
        write_model(receipt_dir / f"{run}.command.json", command)
        exports.append((read_netlist(output), digest(output)))

    assert exports[0][0] == exports[1][0]
    observed, netlist_sha256 = exports[0]
    assert len(netlist_sha256) == 64
    assert all(len(export_sha256) == 64 for _, export_sha256 in exports)
    assert observed.component_pin_numbers == {"J1": ("1", "2"), "J2": ("1", "2")}
    assert observed.pin_functions["J1.1"] == "GND"
    assert observed.pin_functions["J1.2"] == "Pin_2"
    assert observed.nets == {}

    shared_scope = {
        reference: ConnectorComparisonScope(
            "reviewed-serial-peers",
            f"Reviewed {reference} in one synthetic serial peer group",
        )
        for reference in ("J1", "J2")
    }
    (candidate,) = all_open_generic_connector_peer_pin_candidates(
        observed,
        peer_assignment_groups=shared_scope,
    )
    assert candidate.rule_id == RULE_ID
    assert candidate.evidence["J1.2"] == ()
    assert candidate.evidence["J2.2"] == ()
    assert candidate.evidence["shared_anchor_contacts"] == ()
    assert candidate.evidence["peer_assignment_group"] == ("reviewed-serial-peers",)

    separate_scopes = {
        "J1": ConnectorComparisonScope("serial-1", "Reviewed J1 as a separate port"),
        "J2": ConnectorComparisonScope("serial-2", "Reviewed J2 as a separate port"),
    }
    assert all_open_generic_connector_peer_pin_candidates(
        observed,
        peer_assignment_groups=separate_scopes,
    ) == ()
    assert all_open_generic_connector_peer_pin_candidates(observed) == ()
    assert_native_fixture_mounts(tmp_path, "receipts/repeat.command.json")

"""Source-bound inspection and reporting behavior for contract coaching."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from kicad_tooling.hwrepo.contract_coach import inspect_summary, text_report
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    ProjectKind,
)
from kicad_tooling.hwrepo.scaffold import new_project
from kicad_tooling.validate import read_netlist
from tests.contract_coach_support import NETLIST

pytestmark = pytest.mark.slow


def test_netlist_retains_dnp_status_for_population_heuristics(
    coach_workspace,
) -> None:
    path = coach_workspace.root / "build" / "dnp-netlist.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        NETLIST.replace('<comp ref="R1">', '<comp ref="R1"><property name="dnp"/>'),
        encoding="utf-8",
    )
    observed = read_netlist(path)
    assert observed.dnp_components == ("R1",)

    ambiguous = coach_workspace.root / "build" / "ambiguous-dnp-netlist.xml"
    ambiguous.write_text(
        NETLIST.replace('<comp ref="R1">', '<comp ref="R1"><property name="dnp" value="no"/>'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Ambiguous native dnp property"):
        read_netlist(ambiguous)


def test_failed_contract_check_still_yields_bound_unreviewed_inventory(
    coach_workspace,
) -> None:
    contract = coach_workspace.root / "examples/projects/controller/tests/contract.json"
    before = contract.read_bytes()
    report = inspect_summary(
        coach_workspace.root,
        coach_workspace.project_id,
        coach_workspace.native / "summary.json",
    )
    assert report.status == "READY_FOR_REVIEW", report.issues
    assert report.review_state == "UNREVIEWED"
    assert not report.electrical_coverage
    assert report.native_summary == str(coach_workspace.native / "summary.json")
    assert report.native_status == "FAIL"
    assert (
        "The validation summary is FAIL; inspect individual check states to distinguish "
        "native export failures from contract or design-lint review findings."
        in report.next_actions
    )
    assert {
        component.identifier for component in report.differences if component.kind == "component"
    } == {"R2", "R3"}
    assert "UNREVIEWED component R3" in text_report(report, "full")
    assert contract.read_bytes() == before


def test_successful_empty_netlist_export_is_blocked_as_lint_evidence(
    coach_workspace,
) -> None:
    netlist = coach_workspace.native / "netlist.xml"
    netlist.write_text("<export><components/><nets/></export>", encoding="utf-8")
    write_model(
        coach_workspace.native / "summary.json",
        coach_workspace.summary.model_copy(
            update={
                "artifacts_sha256": {
                    **coach_workspace.summary.artifacts_sha256,
                    "netlist.xml": digest(netlist),
                }
            }
        ),
    )

    report = inspect_summary(
        coach_workspace.root,
        coach_workspace.project_id,
        coach_workspace.native / "summary.json",
    )

    assert report.status == "BLOCKED"
    assert "contains no component records" in report.issues[0]
    assert report.observed is None


def test_tampered_netlist_artifact_is_blocked(coach_workspace) -> None:
    netlist = coach_workspace.native / "netlist.xml"
    netlist.write_text(NETLIST + "\n", encoding="utf-8")
    report = inspect_summary(
        coach_workspace.root, coach_workspace.project_id, coach_workspace.native
    )
    assert report.status == "BLOCKED"
    assert "artifact hash" in report.issues[0]
    assert report.observed is None


def test_summary_for_another_project_is_blocked(coach_workspace) -> None:
    write_model(
        coach_workspace.native / "summary.json",
        coach_workspace.summary.model_copy(update={"project_id": "passive-signal-reference"}),
    )
    report = inspect_summary(
        coach_workspace.root, coach_workspace.project_id, coach_workspace.native
    )
    assert "another project" in report.issues[0]


def test_stale_source_is_blocked(coach_workspace) -> None:
    source = coach_workspace.root / "examples/projects/controller/kicad/controller.kicad_sch"
    source.write_bytes(source.read_bytes() + b"\n")
    report = inspect_summary(
        coach_workspace.root, coach_workspace.project_id, coach_workspace.native
    )
    assert report.status == "BLOCKED"
    assert "source" in report.issues[0]


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("kicad_version", "10.0.1"),
        ("image", "ghcr.io/kicad/kicad@sha256:" + "a" * 64),
    ),
    ids=("version-changed", "image-changed"),
)
def test_native_summary_is_blocked_after_catalogued_toolchain_changes(
    coach_workspace, field: str, replacement: str
) -> None:
    catalog = coach_workspace.root / "catalog/toolchains.json"
    original = json.loads(catalog.read_text(encoding="utf-8"))
    altered = json.loads(json.dumps(original))
    for record in altered["toolchains"]:
        if record["id"] == coach_workspace.config.toolchain_id:
            record[field] = replacement
    catalog.write_text(json.dumps(altered), encoding="utf-8")
    report = inspect_summary(
        coach_workspace.root, coach_workspace.project_id, coach_workspace.native
    )
    assert report.status == "BLOCKED"
    assert "toolchain version or image" in report.issues[0]
    assert report.observed is None


@pytest.mark.parametrize("toolchain", ("missing", "failed"), ids=("missing", "not-passing"))
def test_native_summary_requires_a_passing_toolchain_record(
    coach_workspace, toolchain: str
) -> None:
    checks = dict(coach_workspace.summary.checks)
    if toolchain == "missing":
        del checks["toolchain"]
    else:
        checks["toolchain"] = CheckEvidence(
            status="FAIL",
            observed_version=coach_workspace.config.kicad_version,
            image=coach_workspace.config.image,
        )
    write_model(
        coach_workspace.native / "summary.json",
        coach_workspace.summary.model_copy(update={"checks": checks}),
    )
    report = inspect_summary(
        coach_workspace.root, coach_workspace.project_id, coach_workspace.native
    )
    assert report.status == "BLOCKED"
    assert "toolchain version or image" in report.issues[0]


def test_command_evidence_must_be_hashed_and_successful(coach_workspace) -> None:
    (coach_workspace.native / "netlist.command.json").write_text("{}", encoding="utf-8")
    report = inspect_summary(
        coach_workspace.root, coach_workspace.project_id, coach_workspace.native
    )
    assert report.status == "BLOCKED"
    assert "command evidence" in report.issues[0]


def test_pcb_only_is_never_presented_as_electrical_coverage(coach_workspace) -> None:
    created = new_project(
        coach_workspace.root,
        "layout-only",
        ProjectKind.PCB_ONLY,
        "kicad-10.0.5",
    )
    assert created.status == "PASS"
    report = inspect_summary(coach_workspace.root, "layout-only", coach_workspace.native)
    assert report.status == "BLOCKED"
    assert "PCB-only" in report.issues[0]
    assert not report.electrical_coverage


def test_cli_json_and_short_text_keep_observations_explicit(coach_workspace) -> None:
    base = (
        sys.executable,
        "-I",
        "-B",
        "-m",
        "kicad_tooling.contract_coach",
        "--root",
        str(coach_workspace.root),
        "--project-id",
        coach_workspace.project_id,
        "--native-summary",
        str(coach_workspace.native),
    )
    machine = subprocess.run(
        (*base, "--format", "json"),
        cwd=coach_workspace.root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert machine.returncode == 0, machine.stderr
    structured = json.loads(machine.stdout)
    assert structured["review_state"] == "UNREVIEWED"
    assert structured["observed"]["components"]["R3"]["value"] == "3k"
    human = subprocess.run(
        (*base, "--format", "text"),
        cwd=coach_workspace.root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert human.returncode == 0, human.stderr
    assert "Observed: 2 components, 2 nets" in human.stdout
    assert "UNREVIEWED" in human.stdout

    receipt = coach_workspace.root / "build/contract-coach/inspect-001"
    retained = subprocess.run(
        (*base, "--output", str(receipt), "--format", "json"),
        cwd=coach_workspace.root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert retained.returncode == 0, retained.stderr
    assert (receipt / "report.json").is_file()
    assert json.loads(retained.stdout)["receipt_dir"] == str(receipt)

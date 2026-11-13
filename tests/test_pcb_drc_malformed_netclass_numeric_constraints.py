"""Source-bound review of malformed numeric PCB netclass constraints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_malformed_netclass_numeric_constraints import (
    PCB_NUMERIC_NETCLASS_CONSTRAINTS,
    configured_pcb_malformed_netclass_numeric_constraints,
)
from kicad_tooling.hwrepo.pcb_drc_malformed_netclass_numeric_constraints_review import (
    PcbMalformedNetClassNumericConstraintCandidate,
    source_bound_pcb_malformed_netclass_numeric_constraint_candidates,
)

RULE_ID = "pcb.drc_malformed_netclass_numeric_constraints"
PROJECT_RELATIVE = "projects/board.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-duplicate-net-settings"
FAULT_FIXTURES = {
    "fault-netclass-clearance-type-array.kicad_pro": (
        "3b4868d576f5741659e42a23c10c787626d07ef5e182b08a50d25eb335f5516d",
        "array",
    ),
    "fault-netclass-clearance-type-boolean.kicad_pro": (
        "12e4e4050cea56f38ac3adf44990361400d0ef86f83a07e46ba4cd4596a3fb22",
        "boolean",
    ),
    "fault-netclass-clearance-type-null.kicad_pro": (
        "09bfc7424fab3826f6893b506f08128e1b588db78430618294349a5ea8912bf5",
        "null",
    ),
    "fault-netclass-clearance-type-object.kicad_pro": (
        "2760e7b5025070b06796c7957c0cf3bd7386d17f5b3712c84f530d1e0cdeb996",
        "object",
    ),
    "fault-netclass-clearance-type-string.kicad_pro": (
        "a5ae5596c3254a6e54ecb1b8641b45fd5612e52f77cc6884f720104dced93269",
        "string",
    ),
}
CONTROL_FIXTURES = (
    "control-netclass-clearance-narrower-default.kicad_pro",
    "control-netclass-clearance-default-assignment.kicad_pro",
    "control-netclass-clearance-property-omitted.kicad_pro",
)
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _document_with_class_constraints(constraints: dict[str, object]) -> str:
    return json.dumps(
        {
            "net_settings": {
                "classes": [
                    {"name": "Default", "clearance": 0.05},
                    {"name": "Narrow", **constraints},
                ]
            }
        }
    )


def _project(
    tmp_path: Path,
    fixture: str,
    *,
    kicad_version: str = "10.0.8",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    project = root / PROJECT_RELATIVE
    project.parent.mkdir(parents=True, exist_ok=True)
    project.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=kind, project=PROJECT_RELATIVE, kicad_version=kicad_version),
    )
    return root, project, config, {PROJECT_RELATIVE: digest(project)}


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return source_bound_pcb_malformed_netclass_numeric_constraint_candidates(
        root,
        config,
        source_hashes,
    )


@pytest.mark.parametrize(
    ("fixture", "expected_hash", "observed_type"),
    tuple((fixture, *metadata) for fixture, metadata in FAULT_FIXTURES.items()),
)
def test_nonnumeric_constraint_fixtures_are_source_hashed_and_reviewed(
    tmp_path: Path,
    fixture: str,
    expected_hash: str,
    observed_type: str,
) -> None:
    source = FIXTURES / fixture
    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_hash

    root, project, config, hashes = _project(tmp_path, fixture)
    (candidate,) = _scan(root, config, hashes)

    assert isinstance(candidate, PcbMalformedNetClassNumericConstraintCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == (f"{PROJECT_RELATIVE}#net_settings.classes[1].clearance[1]")
    assert candidate.source_evidence.source_sha256 == digest(project)
    assert candidate.source_evidence.constraint.observed_json_type == observed_type
    assert "as JSON" in candidate.message
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": ("10.0.8",),
        "project_kind": ("pcb",),
        "class_index": ("1",),
        "class_name": ("Narrow",),
        "property": ("clearance",),
        "observed_json_type": (observed_type,),
        "member_occurrence": ("1",),
    }


@pytest.mark.parametrize("observed", (None, False, "0.2", [], {}))
def test_all_recognized_constraint_names_retain_nonnumeric_types(observed: object) -> None:
    findings = configured_pcb_malformed_netclass_numeric_constraints(
        _document_with_class_constraints(
            {property_name: observed for property_name in PCB_NUMERIC_NETCLASS_CONSTRAINTS}
        )
    )

    assert {item.property_name for item in findings} == PCB_NUMERIC_NETCLASS_CONSTRAINTS
    assert len(findings) == len(PCB_NUMERIC_NETCLASS_CONSTRAINTS)
    assert {item.observed_json_type for item in findings} == {
        "null"
        if observed is None
        else "boolean"
        if observed is False
        else "string"
        if isinstance(observed, str)
        else "array"
        if isinstance(observed, list)
        else "object"
    }


def test_numeric_values_and_omitted_constraint_properties_are_controls() -> None:
    constraints: dict[str, object] = {
        property_name: 0.2 if index % 2 else index
        for index, property_name in enumerate(sorted(PCB_NUMERIC_NETCLASS_CONSTRAINTS))
    }
    assert (
        configured_pcb_malformed_netclass_numeric_constraints(
            _document_with_class_constraints(constraints)
        )
        == ()
    )
    assert (
        configured_pcb_malformed_netclass_numeric_constraints(_document_with_class_constraints({}))
        == ()
    )


@pytest.mark.parametrize("fixture", CONTROL_FIXTURES)
def test_valid_clearance_configuration_controls_stay_quiet(
    tmp_path: Path,
    fixture: str,
) -> None:
    root, _, config, hashes = _project(tmp_path, fixture)
    assert _scan(root, config, hashes) == ()


def test_unmeasured_versions_and_non_pcb_projects_are_out_of_scope(tmp_path: Path) -> None:
    root, _, config, hashes = _project(tmp_path, CONTROL_FIXTURES[0])
    assert (
        _scan(
            root,
            cast(ProjectConfig, SimpleNamespace(**{**config.__dict__, "kicad_version": "9.0.0"})),
            hashes,
        )
        == ()
    )
    assert (
        _scan(
            root,
            cast(
                ProjectConfig, SimpleNamespace(**{**config.__dict__, "kind": ProjectKind.SCHEMATIC})
            ),
            hashes,
        )
        == ()
    )


def test_pcb_only_projects_are_supported(tmp_path: Path) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        next(iter(FAULT_FIXTURES)),
        kind=ProjectKind.PCB_ONLY,
    )
    (candidate,) = _scan(root, config, hashes)
    assert candidate.source_evidence.project_kind is ProjectKind.PCB_ONLY


def test_stale_source_hash_does_not_produce_candidate(tmp_path: Path) -> None:
    root, _, config, _hashes = _project(tmp_path, next(iter(FAULT_FIXTURES)))
    with pytest.raises(ValueError, match="differ from source-bound project inputs"):
        _scan(root, config, {PROJECT_RELATIVE: "0" * 64})

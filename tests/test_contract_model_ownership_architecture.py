"""Guard domain ownership and compatibility imports for shared contracts."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport, ContractDifference
from kicad_tooling.hwrepo.models import (
    CheckEvidence as RegistryCheckEvidence,
)
from kicad_tooling.hwrepo.models import (
    ComponentContract as RegistryComponentContract,
)
from kicad_tooling.hwrepo.models import ContractCoachReport as RegistryContractCoachReport
from kicad_tooling.hwrepo.models import ContractDifference as RegistryContractDifference
from kicad_tooling.hwrepo.models import (
    NetlistContract as RegistryNetlistContract,
)
from kicad_tooling.hwrepo.models import (
    ValidationSummary as RegistryValidationSummary,
)
from kicad_tooling.hwrepo.native_project_validation_models import CheckEvidence, ValidationSummary
from kicad_tooling.hwrepo.netlist_contract_models import (
    ComponentContract,
    NetlistContract,
)
from kicad_tooling.hwrepo.project_models import ComponentContract as ProjectComponentContract
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.evidence_lint,
    pytest.mark.rule_gate_integrity,
]

_CONTRACT_OWNERS = {
    "ComponentContract": "netlist_contract_models",
    "NetlistContract": "netlist_contract_models",
    "CheckEvidence": "native_project_validation_models",
    "ValidationSummary": "native_project_validation_models",
    "ContractCoachReport": "contract_coach_models",
    "ContractDifference": "contract_coach_models",
}
_REGISTRY_MODULES = {
    "models",
    "project_models",
    "hwrepo.models",
    "hwrepo.project_models",
    "kicad_tooling.hwrepo.models",
    "kicad_tooling.hwrepo.project_models",
}
_CENTRAL_REGISTRIES = {"models", "hwrepo.models", "kicad_tooling.hwrepo.models"}


def test_contract_owners_are_small_and_keep_domain_dependencies() -> None:
    expected = {
        "netlist_contract_models.py": {
            "collections.abc",
            "pydantic",
            "model_primitives",
            "netlist_contract_inputs",
        },
        "native_project_validation_models.py": {
            "collections.abc",
            "pathlib",
            "typing",
            "pydantic",
            "model_primitives",
            "project_models",
            "source_state_models",
        },
        "contract_coach_models.py": {
            "collections.abc",
            "typing",
            "pydantic",
            "command_evidence_models",
            "connector_peer_pin_models",
            "model_primitives",
            "netlist_contract_models",
            "project_models",
            "return_net_models",
        },
    }
    expected_classes = {
        "netlist_contract_models.py": {"ComponentContract", "NetlistContract"},
        "native_project_validation_models.py": {
            "NativeProjectValidationRequest",
            "CheckEvidence",
            "ValidationSummary",
        },
        "contract_coach_models.py": {"ContractDifference", "ContractCoachReport"},
    }
    for filename, modules in expected.items():
        path = REPO_ROOT / "kicad_tooling/hwrepo" / filename
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module != "__future__"
        }
        classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}

        assert line_count(path) < IMPLEMENTATION_MAX_LINES
        assert imports == modules
        assert classes == expected_classes[filename]
        assert not imports.intersection(_CENTRAL_REGISTRIES)


def test_legacy_registry_and_project_exports_preserve_contract_identity() -> None:
    assert RegistryComponentContract is ComponentContract
    assert ProjectComponentContract is ComponentContract
    assert RegistryNetlistContract is NetlistContract
    assert RegistryCheckEvidence is CheckEvidence
    assert RegistryValidationSummary is ValidationSummary
    assert RegistryContractCoachReport is ContractCoachReport
    assert RegistryContractDifference is ContractDifference

    assert set(ComponentContract.model_fields) == {"value", "footprint", "part_id"}
    assert set(NetlistContract.model_fields) == {
        "components",
        "nets",
        "unconnected_nets",
        "dnp_components",
        "component_symbols",
        "pin_functions",
        "pin_electrical_types",
        "component_pin_numbers",
    }
    assert set(CheckEvidence.model_fields) == {
        "status",
        "returncode",
        "error",
        "findings",
        "expected_ignored_checks",
        "files",
        "source_hashes",
        "identity_status",
        "observed_version",
        "image",
    }
    assert set(ValidationSummary.model_fields) == {
        "schema_version",
        "lane",
        "timestamp_utc",
        "checked_commit",
        "source",
        "project_id",
        "pr_head_commit",
        "assurance_profile",
        "not_for_manufacture",
        "project_kind",
        "checks",
        "status",
        "artifacts_sha256",
    }
    assert set(ContractDifference.model_fields) == {"kind", "identifier", "difference"}

    summary = ValidationSummary(
        timestamp_utc="2026-11-04T00:00:00Z",
        checked_commit="a" * 40,
        checks={"erc": CheckEvidence(status="PASS")},
        status="PASS",
        artifacts_sha256={},
    )
    assert RegistryValidationSummary.model_validate_json(summary.model_dump_json()) == summary

    report = ContractCoachReport(
        status="BLOCKED",
        project_id="board-1",
        differences=(
            ContractDifference(
                kind="net",
                identifier="GND",
                difference="observed_only",
            ),
        ),
    )
    assert report.electrical_coverage is False
    assert report.build_authorized is False
    assert RegistryContractCoachReport.model_validate_json(report.model_dump_json()) == report


def test_production_contract_consumers_import_from_their_domain_owner() -> None:
    roots = (REPO_ROOT / "kicad_tooling", REPO_ROOT / "scripts")
    excluded = {
        "models.py",
        "netlist_contract_models.py",
        "native_project_validation_models.py",
        "contract_coach_models.py",
    }
    legacy_imports: list[str] = []
    missing_owner_imports: list[str] = []

    for root in roots:
        for path in sorted(root.rglob("*.py")):
            if path.name in excluded and path.parent.name == "hwrepo":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            loaded_names = {
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id in _CONTRACT_OWNERS
            }
            owner_names: set[str] = set()
            location = str(path.relative_to(REPO_ROOT))

            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                selected = {alias.name for alias in node.names}.intersection(_CONTRACT_OWNERS)
                if not selected:
                    continue
                if node.module in _REGISTRY_MODULES:
                    legacy_imports.append(f"{location}:{node.lineno}")
                if node.module and node.module.endswith("netlist_contract_models"):
                    owner_names.update(
                        selected.intersection({"ComponentContract", "NetlistContract"})
                    )
                if node.module and node.module.endswith("native_project_validation_models"):
                    owner_names.update(
                        selected.intersection({"CheckEvidence", "ValidationSummary"})
                    )
                if node.module and node.module.endswith("contract_coach_models"):
                    owner_names.update(
                        selected.intersection({"ContractCoachReport", "ContractDifference"})
                    )

            missing = loaded_names - owner_names
            if missing:
                missing_owner_imports.append(f"{location}: {', '.join(sorted(missing))}")

    assert not legacy_imports
    assert not missing_owner_imports

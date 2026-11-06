"""Guard purchasing contract ownership and compatibility routes."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.digikey_handoff_models import (
    DigiKeyHandoffPart,
    DigiKeyHandoffPayload,
    DigiKeyHandoffQuantity,
    DigiKeyHandoffReply,
    DigiKeyHandoffResult,
    DigiKeyHandoffUrl,
)
from kicad_tooling.hwrepo.models import (
    DigiKeyHandoffPart as RegistryDigiKeyHandoffPart,
)
from kicad_tooling.hwrepo.models import (
    DigiKeyHandoffPayload as RegistryDigiKeyHandoffPayload,
)
from kicad_tooling.hwrepo.models import (
    DigiKeyHandoffQuantity as RegistryDigiKeyHandoffQuantity,
)
from kicad_tooling.hwrepo.models import (
    DigiKeyHandoffReply as RegistryDigiKeyHandoffReply,
)
from kicad_tooling.hwrepo.models import (
    DigiKeyHandoffResult as RegistryDigiKeyHandoffResult,
)
from kicad_tooling.hwrepo.models import (
    DigiKeyHandoffUrl as RegistryDigiKeyHandoffUrl,
)
from kicad_tooling.hwrepo.models import (
    PurchasingComponent as RegistryPurchasingComponent,
)
from kicad_tooling.hwrepo.models import (
    PurchasingFinding as RegistryPurchasingFinding,
)
from kicad_tooling.hwrepo.models import (
    PurchasingLine as RegistryPurchasingLine,
)
from kicad_tooling.hwrepo.models import (
    PurchasingPlan as RegistryPurchasingPlan,
)
from kicad_tooling.hwrepo.models import (
    PurchasingReport as RegistryPurchasingReport,
)
from kicad_tooling.hwrepo.models import (
    SupplierHandoffPlan as RegistrySupplierHandoffPlan,
)
from kicad_tooling.hwrepo.models import (
    SupplierHandoffReport as RegistrySupplierHandoffReport,
)
from kicad_tooling.hwrepo.purchasing_models import (
    PurchasingComponent,
    PurchasingFinding,
    PurchasingLine,
    PurchasingPlan,
    PurchasingReport,
)
from kicad_tooling.hwrepo.purchasing_preference_models import PurchasingPreferences
from kicad_tooling.hwrepo.supplier_handoff_models import (
    SupplierHandoffPlan,
    SupplierHandoffReport,
)
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = pytest.mark.architecture

_OWNER_BY_NAME = {
    "PurchasingComponent": "purchasing_models",
    "PurchasingLine": "purchasing_models",
    "PurchasingFinding": "purchasing_models",
    "PurchasingPlan": "purchasing_models",
    "PurchasingReport": "purchasing_models",
    "DigiKeyHandoffQuantity": "digikey_handoff_models",
    "DigiKeyHandoffPart": "digikey_handoff_models",
    "DigiKeyHandoffPayload": "digikey_handoff_models",
    "DigiKeyHandoffUrl": "digikey_handoff_models",
    "DigiKeyHandoffReply": "digikey_handoff_models",
    "DigiKeyHandoffResult": "digikey_handoff_models",
    "SupplierHandoffPlan": "supplier_handoff_models",
    "SupplierHandoffReport": "supplier_handoff_models",
}
_LEGACY_REGISTRIES = {
    "models",
    "hwrepo.models",
    "kicad_tooling.hwrepo.models",
}
_OWNER_FILES = {
    "models.py",
    "purchasing_models.py",
    "digikey_handoff_models.py",
    "supplier_handoff_models.py",
}


def test_purchasing_model_owners_have_bounded_dependencies() -> None:
    expected_imports = {
        "purchasing_models.py": {
            "typing",
            "pydantic",
            "contract_coach_models",
            "model_primitives",
            "purchasing_preference_models",
            "source_state_models",
        },
        "digikey_handoff_models.py": {
            "typing",
            "pydantic",
            "model_primitives",
        },
        "supplier_handoff_models.py": {
            "collections.abc",
            "typing",
            "pydantic",
            "model_primitives",
            "digikey_handoff_models",
        },
    }
    expected_classes = {
        "purchasing_models.py": {
            "PurchasingComponent",
            "PurchasingLine",
            "PurchasingFinding",
            "PurchasingPlan",
            "PurchasingReport",
        },
        "digikey_handoff_models.py": {
            "DigiKeyHandoffQuantity",
            "DigiKeyHandoffPart",
            "DigiKeyHandoffPayload",
            "DigiKeyHandoffUrl",
            "DigiKeyHandoffReply",
            "DigiKeyHandoffResult",
        },
        "supplier_handoff_models.py": {"SupplierHandoffPlan", "SupplierHandoffReport"},
    }
    for filename, expected in expected_imports.items():
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
        assert imports == expected
        assert classes == expected_classes[filename]


def test_registry_exports_keep_identity_and_typed_serialization() -> None:
    assert RegistryPurchasingComponent is PurchasingComponent
    assert RegistryPurchasingLine is PurchasingLine
    assert RegistryPurchasingFinding is PurchasingFinding
    assert RegistryPurchasingPlan is PurchasingPlan
    assert RegistryPurchasingReport is PurchasingReport
    assert RegistryDigiKeyHandoffQuantity is DigiKeyHandoffQuantity
    assert RegistryDigiKeyHandoffPart is DigiKeyHandoffPart
    assert RegistryDigiKeyHandoffPayload is DigiKeyHandoffPayload
    assert RegistryDigiKeyHandoffUrl is DigiKeyHandoffUrl
    assert RegistryDigiKeyHandoffReply is DigiKeyHandoffReply
    assert RegistryDigiKeyHandoffResult is DigiKeyHandoffResult
    assert RegistrySupplierHandoffPlan is SupplierHandoffPlan
    assert RegistrySupplierHandoffReport is SupplierHandoffReport

    plan = PurchasingPlan(
        status="NEEDS_PARTS",
        preferences=PurchasingPreferences(),
        components=(),
        lines=(),
        findings=(),
    )
    parts_report = PurchasingReport(
        project_id="board-1",
        status="BLOCKED",
        receipt_dir="build/parts/run-1",
    )
    payload = DigiKeyHandoffPayload(
        root=(
            DigiKeyHandoffPart(
                requestedPartNumber="RC0603FR-0710KL",
                quantities=(DigiKeyHandoffQuantity(quantity=2),),
                customerReference="board-1",
                notes="",
            ),
        )
    )
    handoff_plan = SupplierHandoffPlan(
        project_id="board-1",
        parts_report="build/parts/run-1/report.json",
        report_sha256="a" * 64,
        payload=payload,
        payload_sha256="b" * 64,
        source_hashes={},
        preconditions={},
    )
    handoff_report = SupplierHandoffReport(
        status="PREPARED",
        project_id="board-1",
        handoff="build/handoff/plan.json",
        handoff_sha256="c" * 64,
        payload_sha256="b" * 64,
    )

    assert plan.purchase_authorized is False and plan.build_authorized is False
    assert parts_report.purchase_authorized is False and parts_report.build_authorized is False
    assert handoff_plan.purchase_authorized is False and handoff_plan.build_authorized is False
    assert handoff_report.purchase_authorized is False and handoff_report.build_authorized is False
    assert RegistryPurchasingPlan.model_validate_json(plan.model_dump_json()) == plan
    assert (
        RegistryPurchasingReport.model_validate_json(parts_report.model_dump_json()) == parts_report
    )
    assert (
        RegistryDigiKeyHandoffPayload.model_validate_json(payload.model_dump_json(by_alias=True))
        == payload
    )
    assert (
        RegistrySupplierHandoffPlan.model_validate_json(handoff_plan.model_dump_json(by_alias=True))
        == handoff_plan
    )
    assert (
        RegistrySupplierHandoffReport.model_validate_json(handoff_report.model_dump_json())
        == handoff_report
    )


def test_production_purchasing_consumers_import_from_domain_owners() -> None:
    legacy: list[str] = []
    missing_owner: list[str] = []
    roots = (REPO_ROOT / "kicad_tooling", REPO_ROOT / "scripts")

    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if path.parent.name == "hwrepo" and path.name in _OWNER_FILES:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            loaded = {
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id in _OWNER_BY_NAME
            }
            imported_from_owner: set[str] = set()
            location = str(path.relative_to(REPO_ROOT))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                selected = {alias.name for alias in node.names}.intersection(_OWNER_BY_NAME)
                if not selected:
                    continue
                if node.module in _LEGACY_REGISTRIES:
                    legacy.append(f"{location}:{node.lineno}")
                for owner in {_OWNER_BY_NAME[name] for name in selected}:
                    if node.module and node.module.endswith(owner):
                        imported_from_owner.update(
                            name for name in selected if _OWNER_BY_NAME[name] == owner
                        )
            missing = loaded - imported_from_owner
            if missing:
                missing_owner.append(f"{location}: {', '.join(sorted(missing))}")

    assert not legacy
    assert not missing_owner

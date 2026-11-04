"""Guard the typed scripting boundary used by policy and CI kicad_tooling."""

from __future__ import annotations

import ast
import unittest

import pytest

from tests.support import SOURCE_ROOT

pytestmark = pytest.mark.architecture

ROOT = SOURCE_ROOT
JSON_ADAPTERS = frozenset(
    {
        "kicad_tooling/hwrepo/contracts.py",
        # GitHub API JSON is validated into narrow Pydantic response models at this boundary.
        "kicad_tooling/hwrepo/hosted_governance.py",
        # Native ERC/DRC JSON is checked against project toolchain identity before use.
        "kicad_tooling/hwrepo/native_report_parsing.py",
        # Native PCB probe output is validated as a strict snapshot before models are built.
        "kicad_tooling/hwrepo/pcb_return_path_capture.py",
        # Native variant-probe JSON is bound to board and project digests before use.
        "kicad_tooling/hwrepo/pcb_variant_population_capture.py",
        # Native DRC JSON is decoded into typed report and source-bound evidence models.
        "kicad_tooling/hwrepo/pcb_drc_rule_parser.py",
        "kicad_tooling/hwrepo/pcb_drc_source_evidence.py",
        # Native custom-rule probe JSON has a focused identity and sentinel adapter.
        "kicad_tooling/hwrepo/pcb_dru_compilation_native_report.py",
        # Retained glTF JSON chunks are parsed under binary envelope and size limits.
        "kicad_tooling/hwrepo/three_d_glb.py",
    }
)
# Discover services automatically so a new module cannot evade architecture checks.
CORE_MODULES = tuple(
    sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "kicad_tooling").rglob("*.py")
        if path.name not in {"__init__.py", "models.py"}
        and path.relative_to(ROOT).as_posix() not in JSON_ADAPTERS | {"kicad_tooling/hardware.py"}
    )
)


def _uses_raw_json_decoder(source: str) -> bool:
    tree = ast.parse(source)
    json_modules: set[str] = set()
    decoder_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            json_modules.update(
                alias.asname or alias.name.split(".")[0]
                for alias in node.names
                if alias.name == "json" or alias.name.startswith("json.")
            )
        elif isinstance(node, ast.ImportFrom) and node.module == "json":
            decoder_names.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name in {"load", "loads"}
            )

    return any(
        isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id in decoder_names
            or isinstance(node.func, ast.Attribute)
            and node.func.attr in {"load", "loads"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in json_modules
        )
        for node in ast.walk(tree)
    )


class ScriptArchitectureTests(unittest.TestCase):
    def source(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_core_services_do_not_reintroduce_any_or_opaque_object_maps(self) -> None:
        for relative in CORE_MODULES:
            with self.subTest(module=relative):
                source = self.source(relative)
                tree = ast.parse(source, filename=relative)
                forbidden_names = {
                    node.id
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Name) and node.id == "Any"
                }
                self.assertEqual(forbidden_names, set())
                self.assertNotIn("dict[str, object]", source)
                self.assertNotIn("Mapping[str, object]", source)

    def test_raw_json_deserialization_is_limited_to_declared_adapters(self) -> None:
        all_modules = (*CORE_MODULES, *JSON_ADAPTERS)
        for relative in all_modules:
            with self.subTest(module=relative):
                decodes_json = _uses_raw_json_decoder(self.source(relative))
                self.assertEqual(decodes_json, relative in JSON_ADAPTERS)

    def test_json_decoder_gate_detects_import_aliases(self) -> None:
        self.assertTrue(_uses_raw_json_decoder("import json as decoder\ndecoder.loads('{}')"))
        self.assertTrue(_uses_raw_json_decoder("from json import loads as decode\ndecode('{}')"))
        self.assertFalse(_uses_raw_json_decoder("json_text = '{}'; print(json_text)"))

    def test_model_primitives_define_closed_inputs_and_ci_outputs_remain_typed(self) -> None:
        primitive_source = self.source("kicad_tooling/hwrepo/model_primitives.py")
        source = self.source("kicad_tooling/hwrepo/models.py")
        self.assertIn('extra="forbid"', primitive_source)
        self.assertIn("frozen=True", primitive_source)
        validation_models = self.source("kicad_tooling/hwrepo/native_project_validation_models.py")
        self.assertIn("class ValidationSummary", validation_models)
        self.assertIn("ValidationSummary", source)
        self.assertIn("from .native_project_validation_models import", source)
        self.assertIn("class ToolchainAssessment", source)
        self.assertIn("from .doctor_models import", source)
        self.assertIn("from .native_project_check_models import", source)
        documentation_models = self.source("kicad_tooling/hwrepo/documentation_models.py")
        self.assertIn("class DocumentationPolicyReport", documentation_models)
        self.assertIn("from .documentation_models import", source)
        release_contract_models = self.source("kicad_tooling/hwrepo/release_contract_models.py")
        self.assertIn("class ReleaseManifest", release_contract_models)
        self.assertIn("from .release_contract_models import", source)
        self.assertIn("class TemplateContract", source)
        sourcing_models = self.source("kicad_tooling/hwrepo/sourcing_models.py")
        self.assertIn("class SourcingSnapshot", sourcing_models)
        self.assertIn("class TemplateMetricsReport", source)


if __name__ == "__main__":
    unittest.main()

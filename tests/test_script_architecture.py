"""Guard the typed scripting boundary used by policy and CI kicad_tooling."""

from __future__ import annotations

import ast
import unittest

from tests.support import SOURCE_ROOT

ROOT = SOURCE_ROOT
JSON_ADAPTERS = {
    "kicad_tooling/hwrepo/contracts.py",
    # GitHub API JSON is validated into narrow Pydantic response models at this boundary.
    "kicad_tooling/hwrepo/hosted_governance.py",
    "kicad_tooling/validate.py",
    "kicad_tooling/fault_probe.py",
}
# Discover services automatically so a new module cannot evade architecture checks.
CORE_MODULES = tuple(
    sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "kicad_tooling").rglob("*.py")
        if path.name not in {"__init__.py", "models.py"}
        and path.relative_to(ROOT).as_posix() not in JSON_ADAPTERS | {"kicad_tooling/hardware.py"}
    )
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
                calls_json_loads = "json.loads(" in self.source(relative)
                self.assertEqual(calls_json_loads, relative in JSON_ADAPTERS)

    def test_models_define_closed_inputs_and_typed_ci_outputs(self) -> None:
        source = self.source("kicad_tooling/hwrepo/models.py")
        self.assertIn('extra="forbid"', source)
        self.assertIn("frozen=True", source)
        self.assertIn("class ValidationSummary", source)
        self.assertIn("class CheckAllSummary", source)
        self.assertIn("class ToolchainAssessment", source)
        self.assertIn("class DocumentationPolicyReport", source)
        self.assertIn("class ReleaseManifest", source)
        self.assertIn("class TemplateContract", source)
        self.assertIn("class SourcingSnapshot", source)
        self.assertIn("class TemplateMetricsReport", source)


if __name__ == "__main__":
    unittest.main()

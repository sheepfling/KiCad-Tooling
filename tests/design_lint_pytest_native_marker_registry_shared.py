"""Expected markers for focused shared lint suites."""

from types import MappingProxyType

PYTEST_NATIVE_LINT_SUITES = MappingProxyType(
    {
        "test_electrical_pcb_return_evidence.py": frozenset({"evidence_lint", "return_path_lint"}),
        "test_design_lint_schematic_connectivity.py": frozenset({"schematic_lint"}),
        "test_design_lint_schematic_text.py": frozenset({"schematic_lint"}),
        "test_schematic_geometry_symbol_arc_body.py": frozenset({"schematic_lint"}),
    }
)

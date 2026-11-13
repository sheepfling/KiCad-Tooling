"""Expected markers for focused shared lint suites."""

from types import MappingProxyType

PYTEST_NATIVE_LINT_SUITES = MappingProxyType(
    {
        "test_electrical_pcb_return_evidence.py": frozenset({"evidence_lint", "return_path_lint"}),
        "test_design_lint_schematic_connectivity.py": frozenset({"schematic_lint"}),
        "test_design_lint_schematic_text.py": frozenset({"schematic_lint"}),
        "test_schematic_missing_embedded_symbol_definition_native.py": frozenset(
            {"schematic_lint", "evidence_lint"}
        ),
        "test_schematic_duplicate_embedded_symbol_definition_native.py": frozenset(
            {"schematic_lint", "evidence_lint"}
        ),
        "test_schematic_embedded_symbol_pin_number_mismatch_native.py": frozenset(
            {"schematic_lint", "evidence_lint"}
        ),
        "test_schematic_duplicate_object_uuid_native.py": frozenset(
            {"schematic_lint", "evidence_lint"}
        ),
        "test_schematic_geometry_symbol_arc_body.py": frozenset({"schematic_lint"}),
        "test_schematic_erc_global_severity_native_fixture_lane.py": frozenset(
            {"schematic_lint", "evidence_lint"}
        ),
        "test_schematic_erc_nonstring_severity_value_native.py": frozenset(
            {"schematic_lint", "evidence_lint"}
        ),
        "test_schematic_erc_duplicate_severity_key_native.py": frozenset(
            {"schematic_lint", "evidence_lint"}
        ),
        "test_schematic_erc_duplicate_section_native.py": frozenset(
            {"schematic_lint", "evidence_lint"}
        ),
        "test_pcb_drc_duplicate_severity_key_native.py": frozenset({"pcb_lint", "evidence_lint"}),
        "test_pcb_drc_duplicate_board_section_native.py": frozenset({"pcb_lint", "evidence_lint"}),
        "test_pcb_drc_duplicate_net_settings_section_native.py": frozenset(
            {"pcb_lint", "evidence_lint"}
        ),
        "test_pcb_drc_conflicting_netclass_definitions_native.py": frozenset(
            {"pcb_lint", "evidence_lint"}
        ),
        "test_pcb_drc_unresolved_netclass_assignment_native.py": frozenset(
            {"pcb_lint", "evidence_lint"}
        ),
        "test_pcb_drc_malformed_netclass_assignment_native.py": frozenset(
            {"pcb_lint", "evidence_lint"}
        ),
        "test_pcb_drc_malformed_netclass_inventory_native.py": frozenset(
            {"pcb_lint", "evidence_lint"}
        ),
        "test_pcb_drc_malformed_netclass_numeric_constraints_native.py": frozenset(
            {"pcb_lint", "evidence_lint"}
        ),
    }
)

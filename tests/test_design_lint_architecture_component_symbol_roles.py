"""Guard ownership of named native BJT and MOSFET role-number records."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
]

_ROLE_OWNERS = {
    "component_bjt_symbols.py": ("basic_bjt_role_numbers", "BjtPinRoleNumbers"),
    "component_mosfet_symbols.py": ("mosfet_terminal_role_numbers", "MosfetPinRoleNumbers"),
}
_ROLE_CONSUMERS = {
    "component_bjt_base_bias.py": ("basic_bjt_role_numbers",),
    "component_bjt_base_drive.py": ("basic_bjt_role_numbers",),
    "component_bjt_terminal_order.py": ("basic_bjt_role_numbers",),
    "design_lint_bjt_base_candidate_evidence.py": ("basic_bjt_role_numbers",),
    "design_lint_component_bjt_terminals.py": ("basic_bjt_role_numbers",),
    "component_mosfet_terminal_order.py": ("mosfet_terminal_role_numbers",),
    "design_lint_component_mosfet_terminals.py": ("mosfet_terminal_role_numbers",),
    "design_lint_mosfet_gate_candidate_evidence.py": ("mosfet_terminal_role_numbers",),
    "design_lint_component_terminal_order_candidate_evidence.py": (
        "basic_bjt_role_numbers",
        "mosfet_terminal_role_numbers",
    ),
}


def test_symbol_role_owners_return_frozen_named_records() -> None:
    for filename, (function_name, record_name) in _ROLE_OWNERS.items():
        source = HWREPO / filename
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=filename)
        assert line_count(source) < IMPLEMENTATION_MAX_LINES

        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        assert function.returns is not None
        assert ast.unparse(function.returns) == f"{record_name} | None"

        record = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == record_name
        )
        dataclass = next(
            decorator
            for decorator in record.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Name)
            and decorator.func.id == "dataclass"
        )
        options = {keyword.arg: keyword.value for keyword in dataclass.keywords}
        assert isinstance(options.get("frozen"), ast.Constant)
        assert options["frozen"].value is True
        assert isinstance(options.get("slots"), ast.Constant)
        assert options["slots"].value is True


def test_role_consumers_import_their_symbol_service_owner() -> None:
    for filename, function_names in _ROLE_CONSUMERS.items():
        source = HWREPO / filename
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=filename)
        imports = {
            (node.module, alias.name)
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        assert line_count(source) < IMPLEMENTATION_MAX_LINES
        assert all(
            ("component_bjt_symbols", name) in imports
            or ("component_mosfet_symbols", name) in imports
            for name in function_names
        ), filename

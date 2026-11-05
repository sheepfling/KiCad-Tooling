"""Guard typed ownership for protocol pin/net role mismatch candidates."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
    pytest.mark.evidence_lint,
]


def test_signal_label_role_rules_share_a_typed_source_owner() -> None:
    owner = "kicad_tooling/hwrepo/design_lint_signal_label_role_candidate_evidence.py"
    owner_path = HWREPO / "design_lint_signal_label_role_candidate_evidence.py"
    owner_reference = f"{owner}#SignalLabelRoleMismatchCandidate"
    evidence_owner = f"{owner}#project_signal_label_role_mismatch_evidence"
    routes = (
        (
            "i2c_signal_label.py",
            "i2c_signal_label_role_candidates",
            "bus.i2c_signal_label_role_mismatch",
            "I2cSignalLabelRoleMismatchEvidence",
            (),
        ),
        (
            "can_line_polarity.py",
            "can_line_polarity_label_candidates",
            "bus.can_line_polarity_label_mismatch",
            "CanLinePolarityLabelMismatchEvidence",
            (),
        ),
        (
            "spi_data_label.py",
            "spi_data_polarity_label_candidates",
            "bus.spi_data_polarity_label_mismatch",
            "SpiDataLabelRoleMismatchEvidence",
            (),
        ),
        (
            "rs485_data_label_mismatch.py",
            "rs485_data_direction_label_candidates",
            "bus.rs485_data_direction_label_mismatch",
            "Rs485DataLabelRoleMismatchEvidence",
            (),
        ),
        (
            "rs485_line_label_mismatch.py",
            "rs485_line_label_mismatch_candidates",
            "bus.rs485_line_label_mismatch",
            "Rs485LineLabelRoleMismatchEvidence",
            ("kicad_tooling/hwrepo/rs485_line_functions.py#rs485_bus_line_label_role",),
        ),
        (
            "serial_tx_rx_label_mismatch.py",
            "serial_tx_rx_label_mismatch_candidates",
            "bus.serial_tx_rx_label_mismatch",
            "SerialTxRxLabelRoleMismatchEvidence",
            (),
        ),
    )
    catalog = {item.rule_id: item for item in rule_catalog().rules}

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    for filename, function_name, rule_id, evidence_type, extra_refs in routes:
        route_path = HWREPO / filename
        route_tree = ast.parse(route_path.read_text(encoding="utf-8"), filename=filename)
        route_function = next(
            node
            for node in route_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        source_builders = tuple(
            node
            for node in ast.walk(route_function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_source_evidence"
        )
        direct_candidates = tuple(
            node
            for node in ast.walk(route_function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Candidate"
        )
        rule = catalog[rule_id]

        assert line_count(route_path) < IMPLEMENTATION_MAX_LINES
        assert source_builders
        assert not direct_candidates
        assert owner_reference in rule.implementation_refs
        assert f"{owner}#{evidence_type}" in rule.implementation_refs
        assert evidence_owner in rule.implementation_refs
        assert all(reference in rule.implementation_refs for reference in extra_refs)
        assert rule.implementation_owner == f"kicad_tooling/hwrepo/{filename}#{function_name}"

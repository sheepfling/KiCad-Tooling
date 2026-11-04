"""Guard precise input types at retained-report and serialized JSON boundaries."""

from __future__ import annotations

import ast
from typing import get_type_hints

import pytest
from pydantic import JsonValue

from kicad_tooling.hwrepo.connectivity_view import _authored  # pyright: ignore[reportPrivateUsage]
from kicad_tooling.hwrepo.electrical_analysis_contract_models import ElectricalAnalysisContract
from kicad_tooling.hwrepo.hosted_governance import (  # pyright: ignore[reportPrivateUsage]
    _gh,
    _model,
)
from kicad_tooling.hwrepo.netlist_contract_inputs import (
    NetlistRawValue,
    normalize_native_unconnected_nets,
)
from kicad_tooling.playtest_mcp import PlaytestHost
from tests.support import SOURCE_ROOT

pytestmark = pytest.mark.architecture


def _return_annotation(relative: str, name: str) -> str:
    source = (SOURCE_ROOT / relative).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source, filename=relative)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            assert node.returns is not None
            return ast.unparse(node.returns)
    raise AssertionError(f"Function {name} is missing from {relative}")


def test_connectivity_view_uses_the_authored_contract_owner() -> None:
    assert get_type_hints(_authored, include_extras=True)["contract"] is (
        ElectricalAnalysisContract
    )


def test_external_json_adapters_keep_the_closed_json_value_type() -> None:
    assert get_type_hints(_gh, include_extras=True)["return"] == JsonValue
    assert get_type_hints(_model, include_extras=True)["value"] == JsonValue
    assert get_type_hints(PlaytestHost.save, include_extras=True)["document"] == JsonValue
    assert (
        get_type_hints(normalize_native_unconnected_nets, include_extras=True)["return"]
        == NetlistRawValue
    )


def test_fixture_repeatability_keys_use_their_finding_record_types() -> None:
    for module, function in (
        ("kicad_tooling/ci_hosted_open_drain_bias.py", "finding_key"),
        ("kicad_tooling/ci_hosted_serial_peer_net_labels.py", "report_signature"),
    ):
        assert "object" not in _return_annotation(module, function)

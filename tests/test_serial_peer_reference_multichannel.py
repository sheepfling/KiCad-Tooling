"""Three-header UART split-reference regression coverage."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.serial_peer_reference_review import (
    unmapped_serial_peer_reference_reviews,
)
from tests.serial_peer_reference_multichannel_support import (
    three_uart_connector_reference_netlist,
)
from tests.serial_peer_reference_support import RULE_ID, report

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_three_uart_headers_localize_one_split_return_among_common_peers() -> None:
    source = three_uart_connector_reference_netlist()
    candidates = unmapped_serial_peer_reference_reviews(source)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert {candidate.first_reference, candidate.second_reference} == {"U1", "J1"}
    assert {link.net for link in candidate.links} == {"UART_RX", "UART_TX"}
    assert "J3.4" in source.nets["GND_A"]

    lint = report(source)
    findings = tuple(item for item in lint.findings if item.rule_id == RULE_ID)
    assert len(findings) == 1
    assert "J1" in findings[0].subject
    assert "U1" in findings[0].subject
    coverage = lint.serial_peer_reference_coverage
    assert coverage is not None
    assert (
        coverage.native_peer_link_count,
        coverage.supported_reference_link_count,
        coverage.separate_reference_link_count,
        coverage.common_reference_link_count,
        coverage.candidate_group_count,
    ) == (6, 6, 2, 4, 1)

    common = report(three_uart_connector_reference_netlist(common_references=True))
    assert RULE_ID not in {item.rule_id for item in common.findings}
    common_coverage = common.serial_peer_reference_coverage
    assert common_coverage is not None
    assert (
        common_coverage.native_peer_link_count,
        common_coverage.common_reference_link_count,
        common_coverage.candidate_group_count,
    ) == (6, 6, 0)

    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    assert report(source) == report(reordered)

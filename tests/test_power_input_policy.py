"""Power-input source-path policy, stable finding, and valid-control cases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates
from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.design_lint_fixtures.power_input_paths import (
    RULE_ID,
    lint_report,
    series_diode_netlist,
    source_path_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]


@pytest.mark.parametrize(
    ("mode", "expected_status", "disposition"),
    (
        pytest.param("block", "FAIL", "OPEN", id="block"),
        pytest.param("off", "PASS", "RULE_OFF", id="off"),
    ),
)
def test_review_block_off_and_exact_ignore_lifecycle(mode, expected_status, disposition) -> None:
    source = source_path_netlist(wrong_rail=True)
    initial = lint_report(source)
    finding = next(item for item in initial.findings if item.rule_id == RULE_ID)
    report = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode=mode,
                    reason="Synthetic policy exercises the power-path review mode",
                ),
            )
        ),
    )
    assert report.status == expected_status
    assert (
        next(item for item in report.findings if item.rule_id == RULE_ID).disposition == disposition
    )
    ignored = lint_report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic reviewer accepts this exact isolated supply domain",
                ),
            )
        ),
    )
    assert ignored.status == "PASS"
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


def test_finding_is_order_stable_and_valid_path_clears_it() -> None:
    source = source_path_netlist(wrong_rail=True)
    original = lint_report(source)
    original_candidate = next(item for item in candidates(source) if item.rule_id == RULE_ID)
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
    reordered_candidate = next(item for item in candidates(reordered) if item.rule_id == RULE_ID)
    assert original_candidate == reordered_candidate
    assert original.netlist_sha256 != lint_report(reordered).netlist_sha256
    assert RULE_ID not in {item.rule_id for item in candidates(source_path_netlist())}
    reverse_diode = series_diode_netlist(reverse=True)
    reverse_finding = next(item for item in candidates(reverse_diode) if item.rule_id == RULE_ID)
    reordered_reverse_diode = reverse_diode.model_copy(
        update={
            "components": dict(reversed(tuple(reverse_diode.components.items()))),
            "nets": dict(reversed(tuple(reverse_diode.nets.items()))),
            "component_symbols": dict(reversed(tuple(reverse_diode.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(reverse_diode.pin_functions.items()))),
            "pin_electrical_types": dict(
                reversed(tuple(reverse_diode.pin_electrical_types.items()))
            ),
            "component_pin_numbers": dict(
                reversed(tuple(reverse_diode.component_pin_numbers.items()))
            ),
        }
    )
    reordered_reverse_finding = next(
        item for item in candidates(reordered_reverse_diode) if item.rule_id == RULE_ID
    )
    forward_diode = series_diode_netlist()
    assert RULE_ID not in {item.rule_id for item in candidates(forward_diode)}
    assert reverse_finding == reordered_reverse_finding

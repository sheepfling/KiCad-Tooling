"""Review regressions for I2S serial-data outputs sharing one schematic net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate, rule_catalog
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.i2s_data_output_sharing import (
    i2s_data_output_sharing_candidates,
)
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i2s_data_output_sharing import i2s_data_output_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.i2s_data_outputs_share_net"


def _report(
    netlist: NetlistContract,
    mode: str | None = None,
    *,
    ignore: DesignLintIgnore | None = None,
):
    rules = (
        ()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review synthetic I2S data-output sharing",
            ),
        )
    )
    policy = DesignLintPolicy(rules=rules, ignores=() if ignore is None else (ignore,))
    return evaluate("synthetic-i2s-data-output-sharing", coach(netlist), policy)


def _findings(report) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.architecture
def test_catalog_owns_the_i2s_output_sharing_rule_in_its_theme_module() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.default_mode == "off"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/i2s_data_output_sharing.py#i2s_data_output_sharing_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_fitted_i2s_data_outputs_form_a_configurable_review_candidate() -> None:
    source = i2s_data_output_netlist()
    candidates = i2s_data_output_sharing_candidates(source)
    default = _findings(_report(source))[0]
    reviewed = _findings(_report(source, "review"))[0]

    assert len(candidates) == 1
    assert default.disposition == "RULE_OFF"
    assert reviewed.subject == "U1, U2: I2S data-output pins share I2S_DATA_SHARED"
    assert reviewed.evidence == {
        "components": ("U1", "U2"),
        "functions": ("SDOUT", "SDOUT"),
        "pins": ("U1.3", "U2.3"),
        "pin_types": ("passive", "passive"),
        "net": ("I2S_DATA_SHARED",),
    }
    assert "Tri-state audio buses" in reviewed.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_bounded_aliases_and_output_to_input_are_controls() -> None:
    aliases = i2s_data_output_netlist(output_functions=("I2S_SDO", "SERIAL_DATA_OUT"))
    output_to_input = i2s_data_output_netlist(output_functions=("SDOUT", "SDIN"))
    unrelated_sdo = i2s_data_output_netlist().model_copy(
        update={
            "pin_functions": {
                "U1.1": "SCK",
                "U1.2": "LRCLK",
                "U1.3": "SDOUT",
                "U1.4": "MCLK",
                "U2.1": "SCK",
                "U2.2": "LRCLK",
                "U2.3": "SDO",
                "U2.4": "MCLK",
            }
        }
    )

    assert len(i2s_data_output_sharing_candidates(aliases)) == 1
    assert not i2s_data_output_sharing_candidates(output_to_input)
    assert not i2s_data_output_sharing_candidates(unrelated_sdo)
    assert not _findings(_report(i2s_data_output_netlist(shared=False), "review"))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_incomplete_and_unsupported_groups_are_skipped() -> None:
    source = i2s_data_output_netlist()
    open_peer = source.model_copy(
        update={"nets": {key: pins for key, pins in source.nets.items() if "U2.3" not in pins}}
    )
    ambiguous_peer = source.model_copy(update={"nets": {**source.nets, "OTHER": ("U2.3",)}})
    incomplete = source.model_copy(
        update={
            "pin_electrical_types": {
                pin: kind for pin, kind in source.pin_electrical_types.items() if pin != "U2.3"
            }
        }
    )
    wrong_i2s_context = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U2.1": "SCK"}}
    )
    duplicate_output = source.model_copy(
        update={
            "component_pin_numbers": {
                **source.component_pin_numbers,
                "U1": ("1", "2", "3", "4", "5"),
            },
            "pin_functions": {**source.pin_functions, "U1.5": "I2S_DOUT"},
            "pin_electrical_types": {**source.pin_electrical_types, "U1.5": "passive"},
            "nets": {**source.nets, "I2S_DATA_SHARED": ("U1.3", "U1.5", "U2.3")},
        }
    )

    for case in (
        i2s_data_output_netlist(dnp_references=("U2",)),
        open_peer,
        ambiguous_peer,
        incomplete,
        wrong_i2s_context,
        duplicate_output,
    ):
        assert not i2s_data_output_sharing_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_net_and_two_native_outputs_are_left_out() -> None:
    source = i2s_data_output_netlist()
    return_net = source.model_copy(
        update={
            "nets": {
                "GND": ("U1.3", "U2.3"),
                **{key: pins for key, pins in source.nets.items() if key != "I2S_DATA_SHARED"},
            }
        }
    )
    output_conflict = source.model_copy(
        update={
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U1.3": "output",
                "U2.3": "output",
            }
        }
    )

    assert not i2s_data_output_sharing_candidates(return_net)
    assert not i2s_data_output_sharing_candidates(output_conflict)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_review_block_or_ignore_exact_finding() -> None:
    source = i2s_data_output_netlist()
    finding = _findings(_report(source, "review"))[0]
    blocked = _findings(_report(source, "block"))[0]
    ignored = _findings(
        _report(
            source,
            "review",
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic I2S multi-device bus is intentionally shared",
            ),
        )
    )[0]

    assert _report(source, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprint_is_order_stable_and_separating_outputs_clears_finding() -> None:
    source = i2s_data_output_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    separate = _findings(_report(i2s_data_output_netlist(shared=False), "review"))
    first = _findings(_report(source, "review"))[0]
    second = _findings(_report(reordered, "review"))[0]

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert not separate

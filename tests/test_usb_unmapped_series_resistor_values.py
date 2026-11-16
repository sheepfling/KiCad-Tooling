"""Review differing series-resistor values on unmapped USB 2.0 data pairs."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintRuleOverride
from tests.usb_peer_reference_support import (
    lint_report,
    usb_peer_netlist,
    usb_peer_series_netlist,
    usb_series_data_map,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.usb_unmapped_series_resistor_value_mismatch"


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_different_fitted_series_values_request_review() -> None:
    report = lint_report(
        usb_peer_series_netlist(
            positive_resistor_value="22R",
            negative_resistor_value="33R",
        ),
        path_map=None,
    )
    (finding,) = _findings(report)

    assert finding.mode == "review"
    assert finding.evidence["USB_D+_nominal_resistance_ohms"] == ("22",)
    assert finding.evidence["USB_D-_nominal_resistance_ohms"] == ("33",)
    assert finding.evidence["USB_D+_series_resistor"][0].startswith("R1 22R Device:R")
    assert finding.evidence["USB_D-_series_resistor"][0].startswith("R2 33R Device:R")
    assert "does not say either value is wrong" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("positive_value", "negative_value"),
    (("27R", "0.027k"), ("2k2", "2.2 kΩ"), ("0R", "0Ω")),
)
def test_equal_parsed_values_are_quiet_across_value_spellings(
    positive_value: str,
    negative_value: str,
) -> None:
    report = lint_report(
        usb_peer_series_netlist(
            positive_resistor_value=positive_value,
            negative_resistor_value=negative_value,
        ),
        path_map=None,
    )

    assert not _findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_current_exact_map_owns_distinct_approved_resistance_ranges() -> None:
    report = lint_report(
        usb_peer_series_netlist(
            positive_resistor_value="22R",
            negative_resistor_value="33R",
        ),
        path_map=usb_series_data_map(
            positive_resistance_ohms=22,
            negative_resistance_ohms=33,
        ),
    )

    assert not _findings(report)
    assert not any(item.rule_id == "bus.usb_data_path_mismatch" for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unmapped_direct_single_resistor_and_unparseable_paths_are_outside_scope() -> None:
    one_resistor = usb_peer_series_netlist().model_copy(update={"dnp_components": ("R2",)})
    unreadable = usb_peer_series_netlist(
        positive_resistor_value="part-specific",
        negative_resistor_value="33R",
    )

    assert not _findings(lint_report(usb_peer_netlist(), path_map=None))
    assert not _findings(lint_report(one_resistor, path_map=None))
    assert not _findings(lint_report(unreadable, path_map=None))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_policy_override_and_exact_ignore_are_supported() -> None:
    source = usb_peer_series_netlist(
        positive_resistor_value="22R",
        negative_resistor_value="33R",
    )
    default = _findings(lint_report(source, path_map=None))[0]
    blocked = _findings(
        lint_report(
            source,
            path_map=None,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="The reviewed USB contract requires matched values",
            ),
        )
    )[0]
    disabled = _findings(
        lint_report(
            source,
            path_map=None,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="off",
                reason="The project reviewed and accepted these values",
            ),
        )
    )[0]
    ignored = _findings(
        lint_report(
            source,
            path_map=None,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=default.fingerprint,
                reason="The PHY reference approves this value pair",
            ),
        )
    )[0]

    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_is_stable_under_native_netlist_mapping_order() -> None:
    source = usb_peer_series_netlist(
        positive_resistor_value="22R",
        negative_resistor_value="33R",
    )
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
        }
    )

    first = _findings(lint_report(source, path_map=None))[0]
    second = _findings(lint_report(reordered, path_map=None))[0]

    assert (second.fingerprint, second.evidence) == (first.fingerprint, first.evidence)

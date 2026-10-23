"""Review SPI clock and chip-select pins against explicit net labels."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.spi_clock_select_label_mismatch import (
    spi_clock_select_label_mismatch_candidates,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.spi_clock_select_label_mismatch import (
    spi_clock_select_label_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.spi_clock_select_label_mismatch"


def _report(
    netlist: NetlistContract,
    mode: str | None = None,
    *,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    rules = (
        ()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review synthetic SPI clock/select labels",
            ),
        )
    )
    policy = DesignLintPolicy(rules=rules, ignores=() if ignore is None else (ignore,))
    return evaluate("synthetic-spi-clock-select-labels", coach(netlist), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_crossed_spi_clock_select_labels_are_reviewed() -> None:
    source = spi_clock_select_label_netlist()

    findings = spi_clock_select_label_mismatch_candidates(source)

    assert tuple(item.subject for item in findings) == (
        "U1.1: SPI1_SCK on SPI1_CS",
        "U1.2: SPI1_NSS on SPI1_SCK",
    )
    assert findings[0].evidence["pin_role"] == ("clock",)
    assert findings[0].evidence["net_role"] == ("chip_select",)
    assert findings[1].evidence["pin_role"] == ("chip_select",)
    assert findings[1].evidence["net_role"] == ("clock",)
    assert _report(source).status == "REVIEW"
    assert tuple(item.subject for item in _findings(_report(source))) == tuple(
        item.subject for item in candidates(source) if item.rule_id == RULE_ID
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_matching_aliases_and_unrelated_net_names_remain_quiet() -> None:
    source = spi_clock_select_label_netlist(crossed=False)
    generic_functions = source.model_copy(update={"pin_functions": {"U1.1": "SCK", "U1.2": "NSS"}})
    neutral_labels = source.model_copy(
        update={"nets": {"CLOCK_A": ("U1.1",), "CONTROL_B": ("U1.2",)}}
    )
    uart_labels = source.model_copy(update={"nets": {"UART_SCK": ("U1.1",), "UART_CS": ("U1.2",)}})
    different_spi_channel = source.model_copy(
        update={"nets": {"SPI2_SCK": ("U1.1",), "SPI2_CS": ("U1.2",)}}
    )

    for control in (source, generic_functions, neutral_labels, uart_labels, different_spi_channel):
        assert not spi_clock_select_label_mismatch_candidates(control)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_multiple_assignments_and_incomplete_inventory_are_skipped() -> None:
    source = spi_clock_select_label_netlist()
    dnp = spi_clock_select_label_netlist(dnp=True)
    open_pins = source.model_copy(update={"nets": {}})
    multiply_assigned = source.model_copy(
        update={"nets": {"SPI1_CS": ("U1.1", "U1.2"), "SPI1_SCK_AUX": ("U1.1",)}}
    )
    missing_inventory = source.model_copy(update={"component_pin_numbers": {}})
    inconsistent_inventory = source.model_copy(update={"component_pin_numbers": {"U1": ("1",)}})
    connector = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "nets": {"SPI1_CS": ("J1.1",), "SPI1_SCK": ("J1.2",)},
            "component_symbols": {"J1": "Connector:Conn_01x02"},
            "pin_functions": {"J1.1": "SPI1_SCK", "J1.2": "SPI1_NSS"},
            "component_pin_numbers": {"J1": ("1", "2")},
        }
    )

    for unsupported in (
        dnp,
        open_pins,
        multiply_assigned,
        missing_inventory,
        inconsistent_inventory,
        connector,
    ):
        assert not spi_clock_select_label_mismatch_candidates(unsupported)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_ignore_exact_assignments() -> None:
    source = spi_clock_select_label_netlist()
    review = _findings(_report(source))
    blocked = _findings(_report(source, "block"))
    disabled = _findings(_report(source, "off"))
    ignored = _findings(
        _report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=review[0].fingerprint,
                reason="The board intentionally uses this part-specific label mapping",
            ),
        )
    )

    assert _report(source, "block").status == "FAIL"
    assert all(item.mode == "block" for item in blocked)
    assert all(item.disposition == "RULE_OFF" for item in disabled)
    assert ignored[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_findings_are_order_stable_and_correction_clears_them() -> None:
    source = spi_clock_select_label_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )

    assert _findings(_report(reordered)) == _findings(_report(source))
    assert not spi_clock_select_label_mismatch_candidates(
        spi_clock_select_label_netlist(crossed=False)
    )

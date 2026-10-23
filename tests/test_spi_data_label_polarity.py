"""Focused SPI MOSI/MISO pin-function and net-label regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.spi_data_label import spi_data_polarity_label_candidates
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.spi_data_label import spi_data_label_netlist

RULE_ID = "bus.spi_data_polarity_label_mismatch"

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _findings(netlist: NetlistContract):
    return tuple(item for item in candidates(netlist) if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reversed_spi_data_labels_are_reviewed_while_the_data_pins_remain_assigned() -> None:
    source = spi_data_label_netlist(reversed_labels=True)

    findings = _findings(source)

    assert tuple(item.subject for item in findings) == (
        "U1.1: MOSI on SPI_MISO",
        "U1.2: MISO on SPI_MOSI",
    )
    assert findings[0].evidence["pin_role"] == ("MOSI",)
    assert findings[0].evidence["net_role"] == ("MISO",)
    assert (
        evaluate("synthetic-spi-data-label", coach(source), DesignLintPolicy()).status == "REVIEW"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_miso_pin_on_the_named_mosi_net_emits_one_review_candidate() -> None:
    source = spi_data_label_netlist().model_copy(update={"nets": {"SPI_MOSI": ("U1.1", "U1.2")}})

    assert tuple(item.subject for item in _findings(source)) == ("U1.2: MISO on SPI_MOSI",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_matching_aliases_and_neutral_or_indexed_labels_remain_unclassified() -> None:
    source = spi_data_label_netlist()
    prefixed = source.model_copy(update={"nets": {"SPI_MOSI": ("U1.1",), "SPI_MISO": ("U1.2",)}})
    neutral = source.model_copy(update={"nets": {"DATA_A": ("U1.1",), "DATA_B": ("U1.2",)}})
    indexed = source.model_copy(update={"nets": {"SPI1_MISO": ("U1.1",), "SPI1_MOSI": ("U1.2",)}})
    vendor_aliases = source.model_copy(update={"pin_functions": {"U1.1": "COPI", "U1.2": "CIPO"}})

    assert not _findings(prefixed)
    assert not _findings(neutral)
    assert not _findings(indexed)
    assert not _findings(vendor_aliases)
    assert not spi_data_polarity_label_candidates(source)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_and_multiply_assigned_pins_are_not_classified() -> None:
    source = spi_data_label_netlist(reversed_labels=True)
    dnp = source.model_copy(update={"dnp_components": ("U1",)})
    open_pin = source.model_copy(update={"nets": {"SPI_MISO": ("U1.2",)}})
    multiply_assigned = source.model_copy(
        update={
            "nets": {
                "SPI_MISO": ("U1.1", "U1.2"),
                "SPI_MOSI": ("U1.1", "U1.2"),
            }
        }
    )

    assert not _findings(dnp)
    assert not _findings(open_pin)
    assert not _findings(multiply_assigned)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_modes_and_exact_fingerprint_ignore_are_supported() -> None:
    source = spi_data_label_netlist(reversed_labels=True)
    reviewed = evaluate("synthetic-spi-data-label", coach(source), DesignLintPolicy())
    finding = next(item for item in reviewed.findings if item.rule_id == RULE_ID)
    blocked = evaluate(
        "synthetic-spi-data-label",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Reviewed map"),)
        ),
    )
    disabled = evaluate(
        "synthetic-spi-data-label",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Intentional labels"),
            )
        ),
    )
    ignored = evaluate(
        "synthetic-spi-data-label",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID, fingerprint=finding.fingerprint, reason="Reviewed"
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert all(item.mode == "block" for item in blocked.findings if item.rule_id == RULE_ID)
    assert all(
        item.disposition == "RULE_OFF" for item in disabled.findings if item.rule_id == RULE_ID
    )
    assert (
        next(
            item for item in ignored.findings if item.fingerprint == finding.fingerprint
        ).disposition
        == "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reordering_is_stable_and_correcting_labels_clears_the_candidate() -> None:
    fault = spi_data_label_netlist(reversed_labels=True)
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )

    assert _findings(reordered) == _findings(fault)
    assert not _findings(spi_data_label_netlist())

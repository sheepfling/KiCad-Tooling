"""Review generic connector pins assigned to a recognized I2C bus pair."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.design_lint_fixtures.i2c_generic_connector_pair import (
    generic_i2c_connector_pair_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.i2c_generic_connector_pair_review"


def _report(
    observed=None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
):
    netlist = observed or generic_i2c_connector_pair_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-i2c-generic-connector",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    policy = DesignLintPolicy(
        rules=() if override is None else (override,),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate(coach.project_id, coach, policy, connector_coverage)


def _finding(report):
    return next(item for item in report.findings if item.rule_id == RULE_ID)


def _source_matched_i2c_pin_map() -> ConnectorCoverageReport:
    signals = (
        ("1", "SDA", "I2C_SDA"),
        ("2", "SCL", "I2C_SCL"),
        ("3", "3V3", "+3V3"),
        ("4", "GND", "BOARD_GND"),
    )
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic I2C connector inventory",
        project_interfaces=("synthetic-i2c",),
        inventory_review_basis="Synthetic complete connector inventory",
        interface_catalog_sha256="b" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-i2c",
                basis="Synthetic approved I2C pin map",
                interface_pin_map={signal: number for number, signal, _ in signals},
                mapped_pins=tuple(
                    ConnectorMappedPinEvidence(
                        interface_pin_number=signal,
                        interface_signal=signal,
                        component_pin=f"J1.{number}",
                        symbol_function=f"Pin_{number}",
                        nets=(net,),
                    )
                    for number, signal, net in signals
                ),
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_contacts_on_exact_i2c_pair_emit_review() -> None:
    finding = _finding(_report())

    assert finding.mode == "review"
    assert finding.subject == "J1: generic pins match SDA/SCL bus nets"
    assert finding.evidence["SDA_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["SCL_generic_connector_pins"] == ("J1.2",)
    assert finding.evidence["SDA_net"] == ("I2C_SDA",)
    assert finding.evidence["SCL_net"] == ("I2C_SCL",)
    assert finding.evidence["I2C_endpoint_pairs"] == ("U1:U1.1=SDA/I2C_SDA;U1.2=SCL/I2C_SCL",)
    assert "does not infer connector identity" in finding.message
    assert "require common grounds or power" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_roles_and_source_matched_pin_map_suppress_review() -> None:
    named = generic_i2c_connector_pair_netlist(connector_functions=("SDA", "SCL", "3V3", "GND"))
    stale_map = ConnectorCoverageReport(
        status="INCOMPLETE",
        scope="Synthetic stale connector review",
        entries=(ConnectorCoverageEntry(reference="J1", status="STALE"),),
    )

    assert not any(item.rule_id == RULE_ID for item in _report(named).findings)
    assert not any(
        item.rule_id == RULE_ID
        for item in _report(connector_coverage=_source_matched_i2c_pin_map()).findings
    )
    assert any(item.rule_id == RULE_ID for item in _report(connector_coverage=stale_map).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_one_sided_pair_dnp_and_incomplete_inventories_are_quiet() -> None:
    incomplete_pair = generic_i2c_connector_pair_netlist(include_scl_contact=False)
    dnp_connector = generic_i2c_connector_pair_netlist().model_copy(
        update={"dnp_components": ("J1",)}
    )
    dnp_endpoint = generic_i2c_connector_pair_netlist().model_copy(
        update={"dnp_components": ("U1",)}
    )
    incomplete_connector = generic_i2c_connector_pair_netlist().model_copy(
        update={"component_pin_numbers": {"J1": ("1", "2", "3"), "U1": ("1", "2", "3", "4")}}
    )
    missing_endpoint_metadata = generic_i2c_connector_pair_netlist().model_copy(
        update={
            "pin_functions": {"J1.1": "Pin_1", "J1.2": "Pin_2", "J1.3": "Pin_3", "J1.4": "Pin_4"}
        }
    )

    for observed in (
        incomplete_pair,
        dnp_connector,
        dnp_endpoint,
        incomplete_connector,
        missing_endpoint_metadata,
    ):
        assert not any(item.rule_id == RULE_ID for item in _report(observed).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ambiguous_assignments_and_not_applicable_disposition_are_quiet() -> None:
    observed = generic_i2c_connector_pair_netlist()
    ambiguous_connector = observed.model_copy(
        update={"nets": {**observed.nets, "OTHER": ("J1.1",)}}
    )
    same_net_endpoint = observed.model_copy(
        update={
            "nets": {
                **observed.nets,
                "I2C_SDA": ("J1.1", "J1.2", "U1.1", "U1.2"),
                "I2C_SCL": (),
            }
        }
    )
    multiple_sda_functions = observed.model_copy(
        update={"pin_functions": {**observed.pin_functions, "U1.4": "SDA"}}
    )
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed connector inventory",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )

    assert not any(item.rule_id == RULE_ID for item in _report(ambiguous_connector).findings)
    assert not any(item.rule_id == RULE_ID for item in _report(same_net_endpoint).findings)
    assert not any(item.rule_id == RULE_ID for item in _report(multiple_sda_functions).findings)
    assert not any(
        item.rule_id == RULE_ID for item in _report(connector_coverage=not_applicable).findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_override_and_exact_ignore_remain_available() -> None:
    base = _finding(_report())
    blocked = _finding(
        _report(
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="This project requires reviewed I2C connector pinouts",
            )
        )
    )
    off_report = _report(
        override=DesignLintRuleOverride(
            rule_id=RULE_ID, mode="off", reason="This project has no I2C connectors"
        )
    )
    ignored = _finding(
        _report(
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=base.fingerprint,
                reason="Reviewed as a non-I2C accessory connector",
            )
        )
    )

    assert blocked.mode == "block"
    assert _finding(off_report).disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_report_is_stable_when_netlist_mappings_are_reordered() -> None:
    observed = generic_i2c_connector_pair_netlist()
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )

    baseline = _finding(_report(observed))
    reordered_finding = _finding(_report(reordered))
    assert baseline.evidence == reordered_finding.evidence
    assert baseline.fingerprint == reordered_finding.fingerprint

"""Review cues for generic connector contacts on an IC TCK/TMS pair."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.bus_jtag_generic_connector import jtag_function_role
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
from tests.design_lint_fixtures.jtag_generic_connector_pair import generic_jtag_connector_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.jtag_generic_connector_pair_review"


def _report(
    observed=None,
    *,
    connector_coverage: ConnectorCoverageReport | None = None,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
):
    netlist = observed or generic_jtag_connector_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-jtag-generic-connector",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    policy = DesignLintPolicy(
        rules=() if override is None else (override,),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate(coach.project_id, coach, policy, connector_coverage)


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _source_matched_jtag_pin_map() -> ConnectorCoverageReport:
    pins = (
        ("1", "JTAG_TCK", "JTAG_CLOCK"),
        ("2", "JTAG_TMS", "JTAG_MODE"),
        ("3", "AUX_3", "PORT_AUX_3"),
        ("4", "AUX_4", "PORT_AUX_4"),
        ("5", "GND", "BOARD_GND"),
    )
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic JTAG connector inventory",
        project_interfaces=("synthetic-jtag",),
        inventory_review_basis="Synthetic complete connector inventory",
        interface_catalog_sha256="b" * 64,
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="synthetic-jtag",
                basis="Synthetic approved JTAG connector pinout",
                interface_pin_map={signal: number for number, signal, _net in pins},
                mapped_pins=tuple(
                    ConnectorMappedPinEvidence(
                        interface_pin_number=signal,
                        interface_signal=signal,
                        component_pin=f"J1.{number}",
                        symbol_function="GND" if signal == "GND" else f"Pin_{number}",
                        nets=(net,),
                    )
                    for number, signal, net in pins
                ),
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_contacts_on_exact_native_jtag_pair_emit_review() -> None:
    findings = _findings(_report())

    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == "J1: generic pins match native JTAG TCK/TMS nets"
    assert finding.evidence["TCK_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["TMS_generic_connector_pins"] == ("J1.2",)
    assert finding.evidence["jtag_endpoint_pairs"] == ("U1:U1.5=TCK/JTAG_CLOCK;U1.6=TMS/JTAG_MODE",)
    assert finding.mode == "review"
    assert "does not establish connector purpose" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_jtag_role_tokens_do_not_reinterpret_swd_aliases() -> None:
    assert jtag_function_role("JTAG_TCK") == "tck"
    assert jtag_function_role("TMS/JTAG") == "tms"
    assert jtag_function_role("TCK") == "tck"
    assert jtag_function_role("SYS_JTMS-SWDIO") is None
    assert jtag_function_role("SYS_JTCK-SWCLK") is None
    assert jtag_function_role("JTMS") is None
    assert jtag_function_role("JTCK") is None
    assert jtag_function_role("GPIO") is None


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_contacts_and_current_reviewed_pinout_are_quiet() -> None:
    named = generic_jtag_connector_netlist(
        connector_functions=("JTAG_TCK", "JTAG_TMS", "Pin_3", "Pin_4", "GND")
    )

    assert not _findings(_report(named))
    assert not _findings(_report(connector_coverage=_source_matched_jtag_pin_map()))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_one_sided_dnp_ambiguous_and_endpoint_controls_are_quiet() -> None:
    base = generic_jtag_connector_netlist()
    one_sided = generic_jtag_connector_netlist(
        connector_assignments={
            "1": "JTAG_CLOCK",
            "2": "PORT_AUX_2",
            "3": "PORT_AUX_3",
            "4": "PORT_AUX_4",
            "5": "BOARD_GND",
        }
    )
    dnp_connector = base.model_copy(update={"dnp_components": ("J1",)})
    dnp_endpoint = base.model_copy(update={"dnp_components": ("U1",)})
    incomplete_connector = base.model_copy(
        update={
            "component_pin_numbers": {
                "J1": ("1", "2", "3", "4"),
                "U1": ("1", "2", "3", "4", "5", "6"),
            }
        }
    )
    missing_endpoint_metadata = base.model_copy(
        update={
            "pin_electrical_types": {
                pin: kind for pin, kind in base.pin_electrical_types.items() if pin != "U1.6"
            }
        }
    )
    missing_connector_metadata = base.model_copy(
        update={
            "pin_functions": {
                pin: function for pin, function in base.pin_functions.items() if pin != "J1.5"
            }
        }
    )
    ambiguous_connector = base.model_copy(update={"nets": {**base.nets, "OTHER": ("J1.1",)}})
    same_net_endpoint = generic_jtag_connector_netlist(
        endpoint_assignments={
            "1": "GPIO_1",
            "2": "GPIO_2",
            "3": "GPIO_3",
            "4": "GPIO_4",
            "5": "JTAG_CLOCK",
            "6": "JTAG_CLOCK",
        }
    )
    duplicate_endpoint_role = base.model_copy(
        update={"pin_functions": {**base.pin_functions, "U1.3": "TCK"}}
    )
    swd_aliases = generic_jtag_connector_netlist(
        endpoint_functions=(
            "GPIO_1",
            "GPIO_2",
            "GPIO_3",
            "GPIO_4",
            "SYS_JTCK-SWCLK",
            "SYS_JTMS-SWDIO",
        )
    )

    for observed in (
        one_sided,
        dnp_connector,
        dnp_endpoint,
        incomplete_connector,
        missing_endpoint_metadata,
        missing_connector_metadata,
        ambiguous_connector,
        same_net_endpoint,
        duplicate_endpoint_role,
        swd_aliases,
    ):
        assert not _findings(_report(observed))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_not_applicable_and_only_current_source_matched_maps_suppress() -> None:
    correct = _source_matched_jtag_pin_map()
    entry = correct.entries[0]
    stale_pin = entry.mapped_pins[0].model_copy(update={"nets": ("OLD_JTAG_CLOCK",)})
    stale = correct.model_copy(
        update={
            "entries": (
                entry.model_copy(update={"mapped_pins": (stale_pin, *entry.mapped_pins[1:])}),
            )
        }
    )
    wrong_role_pin = entry.mapped_pins[0].model_copy(update={"interface_signal": "JTAG_TMS"})
    wrong_role = correct.model_copy(
        update={
            "entries": (
                entry.model_copy(update={"mapped_pins": (wrong_role_pin, *entry.mapped_pins[1:])}),
            )
        }
    )
    partial = correct.model_copy(
        update={"entries": (entry.model_copy(update={"mapped_pins": entry.mapped_pins[:1]}),)}
    )
    not_applicable = ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed connector inventory",
        inventory_review_basis="Reviewed connector inventory",
        entries=(ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE"),),
    )

    assert not _findings(_report(connector_coverage=correct))
    assert _findings(_report(connector_coverage=stale))
    assert _findings(_report(connector_coverage=wrong_role))
    assert _findings(_report(connector_coverage=partial))
    assert not _findings(_report(connector_coverage=not_applicable))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_override_and_exact_ignore_remain_available() -> None:
    base = _findings(_report())[0]
    blocked = _findings(
        _report(
            override=DesignLintRuleOverride(
                rule_id=RULE_ID, mode="block", reason="Require reviewed JTAG pinouts"
            )
        )
    )[0]
    off = _findings(
        _report(
            override=DesignLintRuleOverride(
                rule_id=RULE_ID, mode="off", reason="No external JTAG connector"
            )
        )
    )
    ignored = _findings(
        _report(
            ignore=DesignLintIgnore(
                rule_id=RULE_ID, fingerprint=base.fingerprint, reason="Reviewed local fixture"
            )
        )
    )

    assert blocked.mode == "block"
    assert len(off) == 1 and off[0].disposition == "RULE_OFF"
    assert len(ignored) == 1 and ignored[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_report_is_stable_when_native_mappings_are_reordered() -> None:
    baseline = _findings(_report())
    original = generic_jtag_connector_netlist()
    reversed_netlist = original.model_copy(
        update={
            "nets": dict(reversed(tuple(original.nets.items()))),
            "pin_functions": dict(reversed(tuple(original.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(original.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(original.component_pin_numbers.items()))),
        }
    )

    assert _findings(_report(reversed_netlist)) == baseline

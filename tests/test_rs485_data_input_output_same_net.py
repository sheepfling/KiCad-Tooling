"""Review regressions for RS-485 transceiver D/DI and R/RO pins on one net."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_rs485_data_same_net import rs485_data_same_net_fixture_lane
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.rs485_same_net import rs485_data_input_output_same_net_candidates
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.rs485_data_same_net import rs485_data_same_net_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.rs485_data_input_output_same_net"


def _report(
    netlist: NetlistContract,
    mode: str = "review",
    *,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review synthetic RS-485 transceiver data paths",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-rs485-data-same-net", coach(netlist), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_explicit_rs485_driver_input_and_receiver_output_on_one_net_are_reviewed() -> None:
    source = rs485_data_same_net_netlist()
    candidates = rs485_data_input_output_same_net_candidates(source)
    findings = _findings(_report(source))

    assert tuple(item.subject for item in candidates) == (
        "U1: RS-485 driver input and receiver output share DATA_SHARED",
    )
    assert candidates[0].evidence["driver_input_pin"] == ("U1.1",)
    assert candidates[0].evidence["receiver_output_pin"] == ("U1.2",)
    assert findings[0].evidence["identity_basis"] == (
        "Synthetic:Rs485Transceiver RS-485 transceiver",
    )
    assert findings[0].mode == "review"
    assert _report(source).status == "REVIEW"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("functions", "identity", "symbol"),
    (
        (("DI", "RO"), "MAX487", "Vendor:Transceiver"),
        (("D", "RO"), "ADM488", "Vendor:Transceiver"),
        (("DI", "R"), "MAX3485", "Vendor:Transceiver"),
        (("DI", "RO"), "SP3485", "Vendor:Transceiver"),
        (("driver input", "receiver output"), "Synthetic IC", "Vendor:RS_485_Interface"),
        (("DRIVERDATAIN", "RECEIVERDATAOUT"), "SN65HVD485E", "Vendor:Transceiver"),
    ),
)
def test_documented_aliases_and_explicit_device_identity_are_supported(
    functions: tuple[str, str], identity: str, symbol: str
) -> None:
    source = rs485_data_same_net_netlist(functions=functions, identity=identity, symbol=symbol)

    assert len(rs485_data_input_output_same_net_candidates(source)) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_data_nets_and_generic_d_r_functions_are_valid_controls() -> None:
    separated = rs485_data_same_net_netlist(shared=False)
    generic = rs485_data_same_net_netlist(identity="Generic logic IC", symbol="Logic:Device")
    can_transceiver = rs485_data_same_net_netlist(
        identity="SN65HVD230", symbol="Vendor:Transceiver"
    )

    assert not rs485_data_input_output_same_net_candidates(separated)
    assert not rs485_data_input_output_same_net_candidates(generic)
    assert not rs485_data_input_output_same_net_candidates(can_transceiver)
    assert not _findings(_report(separated))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_and_incomplete_pin_evidence_is_skipped() -> None:
    source = rs485_data_same_net_netlist()
    unsupported = (
        rs485_data_same_net_netlist(dnp=True),
        source.model_copy(update={"nets": {"DATA_SHARED": ("U1.1",)}}),
        source.model_copy(update={"nets": {**source.nets, "DATA_AUX": ("U1.1",)}}),
        source.model_copy(update={"component_pin_numbers": {}}),
        source.model_copy(update={"component_pin_numbers": {"U1": ("2",)}}),
        source.model_copy(update={"pin_functions": {"U1.1": "D", "U1.2": "R", "U1.3": "DI"}}),
        source.model_copy(update={"pin_electrical_types": {"U1.1": "output", "U1.2": "output"}}),
    )

    for case in unsupported:
        assert not rs485_data_input_output_same_net_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_duplicate_role_pins_connectors_and_non_ic_references_are_skipped() -> None:
    source = rs485_data_same_net_netlist()
    duplicate_role = source.model_copy(
        update={
            "nets": {"DATA_SHARED": ("U1.1", "U1.2", "U1.3")},
            "pin_functions": {**source.pin_functions, "U1.3": "DI"},
            "component_pin_numbers": {"U1": ("1", "2", "3")},
        }
    )
    connector = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "nets": {"DATA_SHARED": ("J1.1", "J1.2")},
            "component_symbols": {"J1": source.component_symbols["U1"]},
            "pin_functions": {"J1.1": "D", "J1.2": "R"},
            "component_pin_numbers": {"J1": ("1", "2")},
        }
    )
    non_ic = source.model_copy(
        update={
            "components": {"Q1": source.components["U1"]},
            "nets": {"DATA_SHARED": ("Q1.1", "Q1.2")},
            "component_symbols": {"Q1": source.component_symbols["U1"]},
            "pin_functions": {"Q1.1": "D", "Q1.2": "R"},
            "component_pin_numbers": {"Q1": ("1", "2")},
        }
    )

    assert not rs485_data_input_output_same_net_candidates(duplicate_role)
    assert not rs485_data_input_output_same_net_candidates(connector)
    assert not rs485_data_input_output_same_net_candidates(non_ic)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_review_block_disable_or_ignore_the_exact_assignment() -> None:
    source = rs485_data_same_net_netlist()
    initial = _findings(_report(source))[0]
    blocked = _findings(_report(source, "block"))[0]
    disabled = _findings(_report(source, "off"))[0]
    ignored = _findings(
        _report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=initial.fingerprint,
                reason="The transceiver uses an intentional echo path",
            ),
        )
    )[0]

    assert _report(source, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reordering_preserves_findings_and_splitting_the_net_clears_them() -> None:
    source = rs485_data_same_net_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )

    assert _findings(_report(reordered)) == _findings(_report(source))
    assert not rs485_data_input_output_same_net_candidates(
        rs485_data_same_net_netlist(shared=False)
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_fixture_runner_rejects_an_unreviewed_kicad_version(tmp_path: Path) -> None:
    log = HostedLog(tmp_path, "unsupported-rs485-same-net")

    with pytest.raises(ValueError, match="do not cover KiCad 10.0.6"):
        rs485_data_same_net_fixture_lane(
            tmp_path,
            version="10.0.6",
            image="local/unpinned",
            log=log,
        )

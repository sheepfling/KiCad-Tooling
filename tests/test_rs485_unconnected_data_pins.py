"""Focused regressions for partially assigned RS-485 D/DI and R/RO pairs."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Literal

import pytest

from kicad_tooling.ci_hosted_rs485_unconnected_data import (
    rs485_unconnected_data_pin_fixture_lane,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.rs485_unconnected_data_pins import (
    rs485_unconnected_data_netlist,
)

RULE_ID = "bus.rs485_unconnected_data_pin"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    source: NetlistContract | None = None,
    mode: Literal["review", "block", "off"] | None = None,
    ignores: tuple[DesignLintIgnore, ...] = (),
) -> DesignLintReport:
    selected = rs485_unconnected_data_netlist() if source is None else source
    overrides = (
        ()
        if mode is None
        else (DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="test policy"),)
    )
    return evaluate(
        "synthetic-rs485-unconnected-data-pin",
        coach(selected),
        DesignLintPolicy(rules=overrides, ignores=ignores),
    )


def _non_ic_reference_netlist() -> NetlistContract:
    source = rs485_unconnected_data_netlist()
    return source.model_copy(
        update={
            "components": {"Q1": source.components["U1"]},
            "nets": {"HOST_TX": ("Q1.1",)},
            "component_symbols": {"Q1": source.component_symbols["U1"]},
            "pin_functions": {"Q1.1": "D", "Q1.2": "R"},
            "component_pin_numbers": {"Q1": ("1", "2")},
        }
    )


def test_open_rs485_data_pin_emits_pair_identity_and_net_evidence() -> None:
    finding = next(item for item in _report(mode="review").findings if item.rule_id == RULE_ID)

    assert finding.subject == "U1.2: R"
    assert finding.evidence == {
        "U1.2": (),
        "function": ("R",),
        "rs485_data_role": ("receiver-output",),
        "paired_pin": ("U1.1",),
        "paired_function": ("D",),
        "paired_role": ("driver-input",),
        "paired_net": ("HOST_TX",),
        "identity_basis": ("Synthetic:Rs485Transceiver RS-485 transceiver",),
    }
    assert "one-way operation is intentional" in finding.message
    assert "do not establish interface use or PCB routing" in finding.message


@pytest.mark.parametrize(
    ("functions", "open_pin", "role"),
    (
        pytest.param(("DI", "RO"), "U1.2", "receiver-output", id="di-ro"),
        pytest.param(
            ("driver data in", "receiver data out"), "U1.2", "receiver-output", id="long-aliases"
        ),
        pytest.param(
            ("driver input", "receiver output"), "U1.1", "driver-input", id="reverse-open"
        ),
    ),
)
def test_bounded_data_function_aliases_include_the_open_role(
    functions: tuple[str, str], open_pin: str, role: str
) -> None:
    source = rs485_unconnected_data_netlist(functions=functions, open_pin=open_pin)
    finding = next(
        item for item in _report(source, mode="review").findings if item.rule_id == RULE_ID
    )

    assert finding.evidence["rs485_data_role"] == (role,)
    assert finding.evidence["paired_pin"] == ("U1.1" if open_pin == "U1.2" else "U1.2",)


def test_rule_defaults_off_and_supports_review_block_off_and_exact_ignore() -> None:
    default = next(item for item in _report().findings if item.rule_id == RULE_ID)
    assert (default.mode, default.disposition) == ("off", "RULE_OFF")
    assert _report(mode="review").status == "REVIEW"
    assert _report(mode="block").status == "FAIL"
    assert _report(mode="off").status == _report().status
    ignored = _report(
        mode="review",
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=default.fingerprint,
                reason="Reviewed as intentional one-way operation",
            ),
        ),
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(rs485_unconnected_data_netlist(open_pin=None), id="connected-control"),
        pytest.param(
            rs485_unconnected_data_netlist(open_pin="U1.1", functions=("D", "R"), dnp=True),
            id="dnp-transceiver",
        ),
        pytest.param(
            rs485_unconnected_data_netlist(identity="generic interface", symbol="Logic:Device"),
            id="generic-identity",
        ),
        pytest.param(
            rs485_unconnected_data_netlist(identity="SN65HVD230", symbol="Vendor:Transceiver"),
            id="can-transceiver-identity",
        ),
        pytest.param(
            rs485_unconnected_data_netlist(open_pin="U1.1", functions=("TX", "RX")),
            id="generic-serial-functions",
        ),
        pytest.param(
            _non_ic_reference_netlist(),
            id="non-ic-reference",
        ),
    ),
)
def test_valid_or_unsupported_shapes_are_quiet(source: NetlistContract) -> None:
    assert not any(item.rule_id == RULE_ID for item in _report(source, mode="review").findings)


def test_both_open_duplicate_role_and_incomplete_inventory_are_quiet() -> None:
    source = rs485_unconnected_data_netlist()
    cases = (
        source.model_copy(
            update={"nets": {}, "unconnected_nets": {"unconnected": ("U1.1", "U1.2")}}
        ),
        source.model_copy(update={"component_pin_numbers": {}}),
        source.model_copy(update={"component_pin_numbers": {"U1": ("1",)}}),
        source.model_copy(
            update={
                "pin_functions": {"U1.1": "D", "U1.2": "R", "U1.3": "DI"},
                "component_pin_numbers": {"U1": ("1", "2", "3")},
            }
        ),
        source.model_copy(update={"pin_functions": {"U1.1": "D", "U1.2": "R", "U1.3": "POWER"}}),
    )

    for case in cases:
        assert not any(item.rule_id == RULE_ID for item in _report(case, mode="review").findings)


def test_multi_net_assignment_is_ambiguous_and_quiet() -> None:
    source = rs485_unconnected_data_netlist().model_copy(
        update={"nets": {"HOST_TX": ("U1.1",), "OTHER": ("U1.1",)}}
    )

    assert not any(item.rule_id == RULE_ID for item in _report(source, mode="review").findings)


def test_reordering_is_stable_and_connecting_open_pin_clears_candidate() -> None:
    source = rs485_unconnected_data_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    original = next(
        item for item in _report(source, mode="review").findings if item.rule_id == RULE_ID
    )
    repeated = next(
        item for item in _report(reordered, mode="review").findings if item.rule_id == RULE_ID
    )
    repaired = rs485_unconnected_data_netlist(open_pin=None)

    assert (repeated.fingerprint, repeated.evidence) == (original.fingerprint, original.evidence)
    assert not any(item.rule_id == RULE_ID for item in _report(repaired, mode="review").findings)


def test_native_fixture_source_hashes_are_pinned() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint/rs485-unconnected-data-native"
    expected = {
        "fault.kicad_sch": "39ec0fb43f3175204f550a71506a7b5fd063cf71759f2786ea0bf765f6077c5f",
        "control.kicad_sch": "fa1ee6811e6351691e186c70411c6fbb139acbbebbb99e556136ad36818ea588",
    }

    assert {
        filename: sha256((fixture_root / filename).read_bytes()).hexdigest()
        for filename in expected
    } == expected


def test_native_runner_rejects_an_unapproved_kicad_version(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="do not cover KiCad 10.0.6"):
        rs485_unconnected_data_pin_fixture_lane(
            tmp_path,
            version="10.0.6",
            image="local/unpinned",
            log=HostedLog(tmp_path, "unsupported-rs485-open-data"),
        )

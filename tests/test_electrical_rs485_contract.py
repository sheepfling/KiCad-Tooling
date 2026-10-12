"""RS-485 electrical contract fault, control, and applicability tests."""

from __future__ import annotations

from typing import Literal

import pytest

from kicad_tooling.hwrepo.models import ElectricalCheck, Rs485Analysis, Rs485BusRequirement
from kicad_tooling.hwrepo.rs485_heuristics import rs485_checks
from tests.electrical_rs485_support import rs485_netlist, rs485_requirement

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _checks(
    spec: Rs485Analysis,
    fault: Literal[
        "endpoint-line-wrong-net",
        "endpoint-reference-wrong-net",
        "termination-dnp",
        "termination-wrong-net",
        "bias-dnp",
        "bias-wrong-net",
        "dnp-option-fitted",
        "identity-wrong",
    ]
    | None = None,
) -> dict[str, ElectricalCheck]:
    return {item.id: item for item in rs485_checks(spec, rs485_netlist(spec, fault=fault))}


def test_rs485_authored_pair_termination_and_bias_control_passes() -> None:
    checks = _checks(rs485_requirement())

    assert all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values())
    assert checks["rs485/fieldbus/endpoint/controller/identity"].status == "PASS"
    assert checks["rs485/fieldbus/endpoint/bus-connector/pins"].status == "PASS"
    assert checks["rs485/fieldbus/pair/shared/membership"].status == "PASS"
    assert checks["rs485/fieldbus/pair/shared/termination/local-end"].observed == 120
    assert checks["rs485/fieldbus/pair/shared/bias"].status == "PASS"


@pytest.mark.parametrize(
    ("fault", "check_id"),
    (
        ("endpoint-line-wrong-net", "rs485/fieldbus/endpoint/controller/pins"),
        ("endpoint-reference-wrong-net", "rs485/fieldbus/endpoint/bus-connector/pins"),
        ("termination-dnp", "rs485/fieldbus/pair/shared/termination/local-end"),
        ("termination-wrong-net", "rs485/fieldbus/pair/shared/termination/local-end"),
        ("bias-dnp", "rs485/fieldbus/pair/shared/bias"),
        ("bias-wrong-net", "rs485/fieldbus/pair/shared/bias"),
        ("identity-wrong", "rs485/fieldbus/endpoint/controller/identity"),
    ),
)
def test_rs485_faults_fail_the_specific_authored_check(fault: str, check_id: str) -> None:
    checks = _checks(rs485_requirement(), fault)

    assert checks[check_id].status == "FAIL"


def test_rs485_split_termination_and_external_dnp_option_are_explicit() -> None:
    split = _checks(rs485_requirement(termination_mode="split"))
    split_termination = split["rs485/fieldbus/pair/shared/termination/local-end"]
    assert split_termination.status == "PASS"
    assert split_termination.observed == 120

    optional = rs485_requirement(dnp_option=True)
    optional_checks = _checks(optional)
    option_id = "rs485/fieldbus/pair/shared/termination/remote-end/dnp-options"
    assert optional_checks[option_id].status == "PASS"
    fitted_option = _checks(optional, "dnp-option-fitted")
    assert fitted_option[option_id].status == "FAIL"


def test_rs485_full_duplex_records_isolation_and_remote_applicability() -> None:
    requirement = rs485_requirement(
        topology="four_wire_full_duplex",
        termination_mode="split",
        bias_mode="internal_failsafe",
        isolated=True,
        external_peers=("Remote controller pin map not supplied",),
    )
    checks = _checks(requirement)

    assert all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values())
    for pair_id in ("board-to-peer", "peer-to-board"):
        assert checks[f"rs485/fieldbus/pair/{pair_id}/membership"].status == "PASS"
        assert checks[f"rs485/fieldbus/pair/{pair_id}/termination/local-end"].status == "PASS"
        internal_bias = checks[f"rs485/fieldbus/pair/{pair_id}/bias"]
        assert internal_bias.status == "NOT_APPLICABLE"
        assert "not verified from the netlist" in internal_bias.detail
    assert checks["rs485/fieldbus/endpoint/controller/pins"].status == "PASS"
    assert any(
        item.status == "NOT_APPLICABLE"
        and "remote controller pin map not supplied" in item.detail.casefold()
        for item in checks.values()
    )


@pytest.mark.parametrize("bias_mode", ("remote", "not_required"))
def test_rs485_nonlocal_bias_is_reported_not_applicable(bias_mode: str) -> None:
    checks = _checks(rs485_requirement(bias_mode=bias_mode))

    assert checks["rs485/fieldbus/pair/shared/bias"].status == "NOT_APPLICABLE"


def test_rs485_four_wire_topology_requires_four_wire_pairs() -> None:
    bus = rs485_requirement().buses[0]

    with pytest.raises(ValueError, match="Four-wire RS-485 needs"):
        Rs485BusRequirement(
            id=bus.id,
            basis=bus.basis,
            topology="four_wire_full_duplex",
            pairs=bus.pairs,
            endpoints=bus.endpoints,
        )

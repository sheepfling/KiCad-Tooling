"""Focused pytest coverage for authored serial-peer contracts."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import ElectricalCheck, NetlistContract
from kicad_tooling.hwrepo.serial_heuristics import serial_peer_checks
from kicad_tooling.hwrepo.serial_logic_models import (
    SerialLogicInputLimits,
    SerialLogicOutputLimits,
)
from kicad_tooling.hwrepo.serial_peer_models import SerialPeerAnalysis, SerialPeerLinkRequirement
from tests.electrical_serial_support import serial_peer_netlist, serial_peer_requirement

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _checks(
    specification: SerialPeerAnalysis,
    *,
    fault: str | None = None,
) -> dict[str, ElectricalCheck]:
    observed: NetlistContract = serial_peer_netlist(specification, fault=fault)
    return {item.id: item for item in serial_peer_checks(specification, observed)}


def test_serial_peer_map_checks_crossed_lines_reference_policy_and_voltage_limits() -> None:
    direct = serial_peer_requirement()
    checks = _checks(direct)
    assert all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values())
    assert checks["serial/console-link/route/a_tx_to_b_rx"].status == "PASS"
    assert checks["serial/console-link/route/b_tx_to_a_rx"].status == "PASS"
    assert checks["serial/console-link/reference"].status == "PASS"
    assert checks["serial/console-link/logic-voltage/a_tx_to_b_rx"].status == "PASS"
    assert checks["serial/console-link/logic-voltage/b_tx_to_a_rx"].status == "PASS"

    exact_absolute_limit = _checks(serial_peer_requirement(peer_output_high_maximum_v=3.6))
    high_limit = exact_absolute_limit["serial/console-link/logic-voltage/b_tx_to_a_rx"]
    assert high_limit.status == "PASS"
    assert high_limit.observed == pytest.approx(0.0)

    overvoltage = _checks(serial_peer_requirement(peer_output_high_maximum_v=5.0))[
        "serial/console-link/logic-voltage/b_tx_to_a_rx"
    ]
    assert overvoltage.status == "FAIL"
    assert overvoltage.observed == pytest.approx(-1.4)
    assert "Synthetic UART datasheet Rev A" in overvoltage.detail

    weak_low = _checks(serial_peer_requirement(peer_output_low_maximum_v=0.9))
    assert weak_low["serial/console-link/logic-voltage/b_tx_to_a_rx"].status == "FAIL"

    limits_missing = _checks(serial_peer_requirement(include_logic_limits=False))
    assert limits_missing["serial/console-link/logic-voltage/a_tx_to_b_rx"].status == (
        "NOT_CONFIGURED"
    )

    with pytest.raises(ValueError, match="ordered and non-overlapping"):
        SerialLogicOutputLimits(
            low_minimum_v=0.0,
            low_maximum_v=2.1,
            high_minimum_v=2.0,
            high_maximum_v=3.3,
            source="Synthetic invalid datasheet range",
            conditions="Synthetic operating range",
        )
    with pytest.raises(ValueError, match="absolute limits and logic thresholds"):
        SerialLogicInputLimits(
            absolute_minimum_v=-0.3,
            low_maximum_v=2.1,
            high_minimum_v=2.0,
            absolute_maximum_v=3.6,
            source="Synthetic invalid datasheet range",
            conditions="Synthetic operating range",
        )

    crossed = _checks(direct, fault="tx-to-tx")
    assert crossed["serial/console-link/endpoint/device/pins"].status == "FAIL"
    assert crossed["serial/console-link/route/a_tx_to_b_rx"].status == "FAIL"

    separate = _checks(serial_peer_requirement(reference_policy="separate_nets"))
    assert separate["serial/console-link/reference"].status == "PASS"
    no_reference = _checks(serial_peer_requirement(reference_policy="not_applicable"))
    assert no_reference["serial/console-link/reference"].status == "NOT_APPLICABLE"

    missing_return = _checks(direct, fault="remote-reference-unconnected")
    assert missing_return["serial/console-link/reference"].status == "FAIL"
    wrong_local_reference = _checks(direct, fault="local-reference-wrong-net")
    assert wrong_local_reference["serial/console-link/reference"].status == "FAIL"

    with pytest.raises(ValueError, match="same logic voltage domain"):
        serial_peer_requirement(peer_logic_domain="logic-5v")
    with pytest.raises(ValueError, match="different logic voltage domains"):
        serial_peer_requirement(peer_mode="level_shifted")


@pytest.mark.parametrize(
    ("fault", "expected_detail"),
    (
        ("bond-missing", "R3 is absent or ambiguous"),
        ("bond-wrong-value", "R3 value is 1R; expected 0R"),
        ("bond-wrong-footprint", "R3 footprint is Synthetic:0402; expected Synthetic:0603"),
        ("bond-wrong-symbol", "R3 symbol is Device:C; expected Device:R"),
        ("bond-dnp", "R3 is marked DNP"),
        ("bond-active-pin", "R3.2 is not exported as a passive bond pin"),
        ("bond-wrong-net", "R3.2 is on FLOATING_GND; expected GND_B"),
        ("remote-reference-unconnected", "U11.3 is assigned to unconnected; expected GND_B"),
    ),
    ids=(
        "missing-bond",
        "wrong-value",
        "wrong-footprint",
        "wrong-symbol",
        "dnp-bond",
        "active-bond-pin",
        "wrong-bond-net",
        "missing-peer-reference",
    ),
)
def test_bonded_reference_faults_report_the_exact_component_and_pin_evidence(
    fault: str, expected_detail: str
) -> None:
    checks = _checks(serial_peer_requirement(reference_policy="bonded"), fault=fault)
    reference_check = checks["serial/console-link/reference"]
    assert reference_check.status == "FAIL"
    assert expected_detail in reference_check.detail


def test_bonded_reference_result_is_independent_of_netlist_order() -> None:
    specification = serial_peer_requirement(reference_policy="bonded")
    observed = serial_peer_netlist(specification)
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": {
                net: tuple(reversed(pins)) for net, pins in reversed(tuple(observed.nets.items()))
            },
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": {
                reference: tuple(reversed(numbers))
                for reference, numbers in reversed(tuple(observed.component_pin_numbers.items()))
            },
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )

    assert serial_peer_checks(specification, observed) == serial_peer_checks(
        specification, reordered
    )


def test_bond_policy_requires_distinct_mapped_nets_and_one_exact_component() -> None:
    specification = serial_peer_requirement(reference_policy="bonded")
    link = specification.links[0]
    values = link.model_dump(mode="python")
    values["reference_bond"] = None
    with pytest.raises(ValueError, match="needs one exact bond component"):
        SerialPeerLinkRequirement.model_validate(values)

    bond = link.reference_bond
    assert bond is not None
    values = link.model_dump(mode="python")
    values["reference_bond"] = bond.model_copy(update={"side_b_net": "FLOATING_GND"})
    with pytest.raises(ValueError, match="must join the two mapped endpoint nets"):
        SerialPeerLinkRequirement.model_validate(values)

    values = serial_peer_requirement().links[0].model_dump(mode="python")
    values["reference_bond"] = bond
    values["reference_policy"] = "common_net"
    with pytest.raises(ValueError, match="cannot declare a bond"):
        SerialPeerLinkRequirement.model_validate(values)


def test_serial_peer_map_supports_level_shifted_and_external_peers() -> None:
    shifted = serial_peer_requirement(peer_mode="level_shifted", peer_logic_domain="logic-5v")
    shifted_checks = _checks(shifted)
    assert all(item.status in {"PASS", "NOT_APPLICABLE"} for item in shifted_checks.values())
    assert shifted_checks["serial/console-link/bridge/U9/pins"].status == "PASS"
    assert shifted_checks["serial/console-link/voltage-domain"].status == "PASS"
    assert shifted_checks["serial/console-link/logic-voltage"].status == "NOT_APPLICABLE"

    wrong_bridge = _checks(shifted, fault="bridge-output-wrong-net")
    assert wrong_bridge["serial/console-link/bridge/U9/pins"].status == "FAIL"
    assert wrong_bridge["serial/console-link/route/a_tx_to_b_rx"].status == "FAIL"
    assert wrong_bridge["serial/console-link/voltage-domain"].status == "FAIL"

    external = _checks(serial_peer_requirement(peer_mode="external"))
    assert external["serial/console-link/endpoint/console/pins"].status == "PASS"
    assert external["serial/console-link/peer-map"].status == "NOT_APPLICABLE"
    assert external["serial/console-link/voltage-domain"].status == "NOT_APPLICABLE"
    assert external["serial/console-link/logic-voltage"].status == "NOT_APPLICABLE"
    assert external["serial/console-link/reference"].status == "NOT_APPLICABLE"

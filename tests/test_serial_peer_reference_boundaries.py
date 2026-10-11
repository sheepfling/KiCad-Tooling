"""Serial peer-reference ambiguity, ordering, and policy boundaries."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.serial_peer_reference_review import (
    unmapped_serial_peer_reference_reviews,
)
from tests.serial_peer_reference_support import (
    RULE_ID,
    labelled_serial_reference_netlist,
    report,
    serial_reference_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def optically_isolated_uart_netlist() -> NetlistContract:
    """Model two UART directions crossing optocouplers between local grounds."""
    source = serial_reference_netlist()
    direct_nets = {"UART_A", "UART_B", "+3V3", "GND_A", "GND_B"}
    nets = {name: pins for name, pins in source.nets.items() if name not in direct_nets}
    nets.update(
        {
            "VDD_A": ("U1.8",),
            "VDD_B": ("U2.8",),
            "GND_A": ("U1.9", "U3.2", "U4.4"),
            "GND_B": ("U2.9", "U3.4", "U4.2"),
            "UART_A_TO_B_LED": ("U1.1", "U3.1"),
            "UART_A_TO_B_OUTPUT": ("U3.3", "U2.1"),
            "UART_B_TO_A_LED": ("U2.2", "U4.1"),
            "UART_B_TO_A_OUTPUT": ("U4.3", "U1.2"),
        }
    )
    optocoupler_functions = {
        f"{reference}.{pin}": function
        for reference in ("U3", "U4")
        for pin, function in (
            ("1", "LED_A"),
            ("2", "LED_K"),
            ("3", "COLLECTOR"),
            ("4", "EMITTER"),
        )
    }
    optocoupler_components = {
        reference: ComponentContract(
            value="Synthetic optical isolator", footprint="Package:Optocoupler"
        )
        for reference in ("U3", "U4")
    }
    optocoupler_types = {pin: "passive" for pin in optocoupler_functions}
    return source.model_copy(
        update={
            "components": {**source.components, **optocoupler_components},
            "nets": nets,
            "component_symbols": {
                **source.component_symbols,
                "U3": "Synthetic:Optocoupler",
                "U4": "Synthetic:Optocoupler",
            },
            "component_pin_numbers": {
                **source.component_pin_numbers,
                "U3": ("1", "2", "3", "4"),
                "U4": ("1", "2", "3", "4"),
            },
            "pin_functions": {**source.pin_functions, **optocoupler_functions},
            "pin_electrical_types": {**source.pin_electrical_types, **optocoupler_types},
        }
    )


class SerialPeerReferenceBoundaryTests:
    def test_optically_isolated_uart_pair_is_not_treated_as_direct_peers(self) -> None:
        observed = optically_isolated_uart_netlist()

        assert observed.nets["GND_A"] != observed.nets["GND_B"]
        assert not unmapped_serial_peer_reference_reviews(observed)
        assert RULE_ID not in {finding.rule_id for finding in report(observed).findings}

    def test_channel_label_candidate_skips_ambiguous_or_incomplete_cases(self) -> None:
        source = labelled_serial_reference_netlist()
        tx_net = "Compute module/UART.0.TX"
        rx_net = "Compute module/UART.0.RX"
        cases = {
            "DNP endpoint": source.model_copy(update={"dnp_components": ("U2",)}),
            "mismatched channel": source.model_copy(
                update={
                    "nets": {
                        **{net: pins for net, pins in source.nets.items() if net != rx_net},
                        "Compute module/UART.1.RX": source.nets[rx_net],
                    }
                }
            ),
            "third pin on signal net": source.model_copy(
                update={
                    "components": {
                        **source.components,
                        "U3": ComponentContract(value="Other", footprint="Package:Other"),
                    },
                    "nets": {**source.nets, tx_net: (*source.nets[tx_net], "U3.1")},
                }
            ),
            "missing signal pin function": source.model_copy(
                update={
                    "pin_functions": {
                        pin: function
                        for pin, function in source.pin_functions.items()
                        if pin != "U1.1"
                    }
                }
            ),
            "missing signal electrical type": source.model_copy(
                update={
                    "pin_electrical_types": {
                        pin: kind
                        for pin, kind in source.pin_electrical_types.items()
                        if pin != "U1.1"
                    }
                }
            ),
            "incomplete component pin inventory": source.model_copy(
                update={
                    "component_pin_numbers": {
                        reference: numbers
                        for reference, numbers in source.component_pin_numbers.items()
                        if reference != "U2"
                    }
                }
            ),
            "multiple return domains": source.model_copy(
                update={
                    "component_pin_numbers": {
                        **source.component_pin_numbers,
                        "U1": (*source.component_pin_numbers["U1"], "10"),
                    },
                    "pin_functions": {**source.pin_functions, "U1.10": "AGND"},
                    "pin_electrical_types": {
                        **source.pin_electrical_types,
                        "U1.10": "power_in",
                    },
                    "nets": {**source.nets, "AGND_LOCAL": ("U1.10",)},
                }
            ),
            "unqualified UART labels": source.model_copy(
                update={
                    "nets": {
                        **{
                            net: pins
                            for net, pins in source.nets.items()
                            if net not in {tx_net, rx_net}
                        },
                        "UART_TX": source.nets[tx_net],
                        "UART_RX": source.nets[rx_net],
                    }
                }
            ),
        }
        for name, candidate in cases.items():
            assert not unmapped_serial_peer_reference_reviews(candidate), name

    def test_channel_label_candidate_is_order_stable(self) -> None:
        source = labelled_serial_reference_netlist()
        reordered = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        assert (unmapped_serial_peer_reference_reviews(source)) == (
            unmapped_serial_peer_reference_reviews(reordered)
        )
        assert (report(source).findings) == (report(reordered).findings)

    def test_channel_label_candidate_obeys_rule_override_and_exact_ignore(self) -> None:
        source = labelled_serial_reference_netlist()
        open_finding = next(item for item in report(source).findings if item.rule_id == RULE_ID)
        disabled = report(
            source,
            policy=DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="off",
                        reason="Synthetic isolated UART segment has separate approved references.",
                    ),
                )
            ),
        )
        disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
        assert (disabled_finding.disposition) == ("RULE_OFF")

        ignored = report(
            source,
            policy=DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=open_finding.fingerprint,
                        reason="Synthetic owner recorded the isolated-interface review.",
                    ),
                )
            ),
        )
        ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
        assert (ignored_finding.disposition) == ("IGNORED")

    def test_incomplete_or_ambiguous_native_reference_evidence_is_skipped(self) -> None:
        source = serial_reference_netlist()
        cases = {
            "DNP endpoint": source.model_copy(update={"dnp_components": ("U2",)}),
            "missing return pin type": source.model_copy(
                update={
                    "pin_electrical_types": {
                        key: value
                        for key, value in source.pin_electrical_types.items()
                        if key != "U1.9"
                    }
                }
            ),
            "missing pin function inventory": source.model_copy(
                update={
                    "pin_functions": {
                        key: value for key, value in source.pin_functions.items() if key != "U1.8"
                    }
                }
            ),
            "shield return is not a signal reference": source.model_copy(
                update={
                    "pin_functions": {
                        **source.pin_functions,
                        "U1.9": "SHIELD_GND",
                        "U2.9": "CHASSIS_GND",
                    }
                }
            ),
            "multiple return nets on endpoint": source.model_copy(
                update={
                    "components": {
                        **source.components,
                        "U1": source.components["U1"],
                    },
                    "component_pin_numbers": {
                        **source.component_pin_numbers,
                        "U1": (*source.component_pin_numbers["U1"], "10"),
                    },
                    "pin_functions": {**source.pin_functions, "U1.10": "AGND"},
                    "pin_electrical_types": {
                        **source.pin_electrical_types,
                        "U1.10": "power_in",
                    },
                    "nets": {**source.nets, "AGND_LOCAL": ("U1.10",)},
                }
            ),
        }
        for name, candidate in cases.items():
            assert not unmapped_serial_peer_reference_reviews(candidate), name

    def test_rule_mode_and_exact_ignore_are_project_configurable(self) -> None:
        source = serial_reference_netlist()
        open_finding = next(item for item in report(source).findings if item.rule_id == RULE_ID)
        blocked = report(
            source,
            policy=DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="block",
                        reason="Synthetic project explicitly requires common UART reference.",
                    ),
                )
            ),
        )
        assert (blocked.status) == ("FAIL")
        assert (next(item for item in blocked.findings if item.rule_id == RULE_ID).mode) == (
            "block"
        )

        disabled = report(
            source,
            policy=DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="off",
                        reason="Synthetic isolated interface review is covered elsewhere.",
                    ),
                )
            ),
        )
        disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
        assert (disabled_finding.disposition) == ("RULE_OFF")
        assert (disabled_finding.reason) == (
            "Synthetic isolated interface review is covered elsewhere."
        )

        ignored = report(
            source,
            policy=DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=open_finding.fingerprint,
                        reason="Synthetic project owner reviewed the explicit separate-reference design.",
                    ),
                )
            ),
        )
        ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
        assert (ignored_finding.disposition) == ("IGNORED")
        assert (ignored_finding.reason) == (
            "Synthetic project owner reviewed the explicit separate-reference design."
        )

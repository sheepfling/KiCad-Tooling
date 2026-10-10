"""Format authored electrical-map and heuristic coverage evidence."""

from __future__ import annotations

from .i2c_addressing import format_i2c_address
from .models import DesignLintReport


def contract_coverage_report_lines(report: DesignLintReport) -> list[str]:
    """Render interface, analog, and electrical-contract coverage sections."""
    lines: list[str] = []
    address_coverage = report.i2c_address_coverage

    lines.append(f"I2C address-map coverage: {address_coverage.status}")

    if address_coverage.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {address_coverage.netlist_sha256}")

    lines.append(f"  Scope: {address_coverage.scope}")

    for entry in address_coverage.entries:
        lines.append(
            f"  {entry.status} responder {entry.reference} on {entry.segment_id}: "
            f"expected {format_i2c_address(entry.expected_address)}, "
            f"observed {format_i2c_address(entry.observed_address)}"
        )
        lines.append(
            f"    Symbol: {entry.observed_symbol or 'unknown'} (expected {entry.expected_symbol})"
        )
        lines.append(f"    SDA: {entry.sda_pin} -> {', '.join(entry.sda_nets) or '<unconnected>'}")
        lines.append(f"    SCL: {entry.scl_pin} -> {', '.join(entry.scl_nets) or '<unconnected>'}")
        lines.append(f"    Basis: {entry.basis}")
        for bit in entry.address_bits:
            value = "unknown" if bit.resolved_value is None else str(bit.resolved_value)
            lines.append(
                f"    Address bit {bit.bit}: {bit.pin} ({bit.observed_function or 'unknown'}), "
                f"nets={', '.join(bit.nets) or '<unconnected>'}, value={value}"
            )
        for issue in entry.issues:
            lines.append(f"    Issue: {issue}")

    for issue in address_coverage.issues:
        lines.append(f"  Coverage issue: {issue}")

    if address_coverage.issue is not None:
        lines.append(f"  Coverage issue: {address_coverage.issue}")

    control_bias = report.control_input_bias_coverage

    covered_control_bias = sum(entry.status == "COVERED" for entry in control_bias.entries)

    lines.append(
        "Control-input bias heuristic coverage: "
        f"{control_bias.status} ({covered_control_bias}/"
        f"{len(control_bias.entries)} candidate nets covered)"
    )

    if control_bias.source_path is not None:
        lines.append(
            f"  Electrical contract: {control_bias.source_path} "
            f"(SHA-256 {control_bias.source_sha256})"
        )

    if control_bias.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {control_bias.netlist_sha256}")

    for entry in control_bias.entries:
        pins = ", ".join(entry.control_pins)
        lines.append(f"  {entry.status} {entry.net}: {pins}")
        if entry.signal_id is not None:
            lines.append(
                f"    Requirement: {entry.signal_id}; bias={entry.bias_mode}; "
                f"basis={entry.bias_basis}"
            )
            if entry.bias_reason is not None:
                lines.append(f"    Decision: {entry.bias_reason}")
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")

    if control_bias.issue is not None:
        lines.append(f"  Coverage issue: {control_bias.issue}")

    i2c_pullup_coverage = report.i2c_pullup_heuristic_coverage

    covered_i2c_pullups = sum(entry.status == "COVERED" for entry in i2c_pullup_coverage.entries)

    lines.append(
        "I2C pull-up heuristic coverage: "
        f"{i2c_pullup_coverage.status} ({covered_i2c_pullups}/"
        f"{len(i2c_pullup_coverage.entries)} candidate pairs covered)"
    )

    if i2c_pullup_coverage.source_path is not None:
        lines.append(
            f"  Electrical contract: {i2c_pullup_coverage.source_path} "
            f"(SHA-256 {i2c_pullup_coverage.source_sha256})"
        )

    if i2c_pullup_coverage.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {i2c_pullup_coverage.netlist_sha256}")

    for entry in i2c_pullup_coverage.entries:
        lines.append(
            f"  {entry.status} SDA {entry.sda_net} / SCL {entry.scl_net}; "
            f"missing heuristic paths: {', '.join(entry.missing_lines)}"
        )
        if entry.bus_id is not None:
            lines.append(f"    Requirement: {entry.bus_id}; checks: {', '.join(entry.check_ids)}")
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")

    if i2c_pullup_coverage.issue is not None:
        lines.append(f"  Coverage issue: {i2c_pullup_coverage.issue}")

    protection_coverage = report.external_protection_coverage

    lines.append(f"External-protection coverage: {protection_coverage.status}")

    if protection_coverage.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {protection_coverage.netlist_sha256}")

    if protection_coverage.electrical_contract_path is not None:
        lines.append(
            "  Existing electrical contract: "
            f"{protection_coverage.electrical_contract_path} "
            f"({protection_coverage.electrical_contract_sha256 or 'unavailable'})"
        )

    lines.append(f"  Scope: {protection_coverage.scope}")

    for entry in protection_coverage.entries:
        signal = f" ({entry.interface_signal})" if entry.interface_signal is not None else ""
        net = f" -> {entry.signal_net}" if entry.signal_net is not None else ""
        lines.append(f"  {entry.status} {entry.connector_pin}{signal}{net}")
        if entry.basis is not None:
            lines.append(f"    Basis: {entry.basis}")
        if entry.device_references:
            lines.append(f"    Devices: {', '.join(entry.device_references)}")
        for issue in entry.issues:
            lines.append(f"    Issue: {issue}")

    if protection_coverage.issue is not None:
        lines.append(f"  Coverage issue: {protection_coverage.issue}")

    crystal_coverage = report.crystal_network_coverage

    lines.append(f"Crystal load-network coverage: {crystal_coverage.status}")

    if crystal_coverage.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {crystal_coverage.netlist_sha256}")

    lines.append(f"  Scope: {crystal_coverage.scope}")

    for entry in crystal_coverage.entries:
        lines.append(
            f"  {entry.status} oscillator {entry.oscillator_reference}, "
            f"resonator {entry.resonator_reference}, "
            f"load caps {', '.join(entry.load_capacitor_references)}"
        )
        for pin, nets in sorted(entry.node_nets.items()):
            lines.append(f"    {pin}: {', '.join(nets) or '<unconnected>'}")
        for reference, pin_nets in sorted(entry.extra_capacitor_pin_nets.items()):
            lines.append(f"    Potential extra capacitor {reference}: {', '.join(pin_nets)}")
        for reference, value in sorted(entry.capacitance_pf.items()):
            lines.append(f"    {reference}: {value:g} pF nominal")
        lines.append(f"    Formula: {entry.formula}")
        if (
            entry.calculated_minimum_load_pf is not None
            and entry.calculated_maximum_load_pf is not None
        ):
            lines.append(
                "    Calculated nominal load: "
                f"{entry.calculated_minimum_load_pf:g}–"
                f"{entry.calculated_maximum_load_pf:g} pF; target "
                f"{entry.target_minimum_load_pf:g}–{entry.target_maximum_load_pf:g} pF"
            )
        stray_range = (
            f"{entry.minimum_stray_capacitance_pf:g}–{entry.maximum_stray_capacitance_pf:g} pF"
        )
        lines.append(f"    Stray capacitance assumption: {stray_range}")
        lines.append(f"    Basis: {entry.basis}")
        for issue in entry.issues:
            lines.append(f"    Issue: {issue}")

    if crystal_coverage.issue is not None:
        lines.append(f"  Coverage issue: {crystal_coverage.issue}")

    feedback_coverage = report.regulator_feedback_coverage

    lines.append(f"Regulator feedback coverage: {feedback_coverage.status}")

    if feedback_coverage.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {feedback_coverage.netlist_sha256}")

    lines.append(f"  Scope: {feedback_coverage.scope}")

    for entry in feedback_coverage.entries:
        lines.append(
            f"  {entry.status} regulator {entry.regulator_reference} "
            f"(profile {entry.id}), output {entry.output_net}, reference {entry.reference_net}"
        )
        lines.append(f"    Feedback net: {entry.feedback_net or '<unresolved>'}")
        for pin, nets in sorted(entry.pin_nets.items()):
            lines.append(f"    {pin}: {', '.join(nets) or '<unconnected>'}")
        for reference, value in sorted(entry.nominal_resistance_ohms.items()):
            lines.append(f"    {reference}: {value:g} Ω nominal")
        lines.append(f"    Formula: {entry.formula}")
        if (
            entry.calculated_output_minimum_v is not None
            and entry.calculated_output_maximum_v is not None
        ):
            lines.append(
                "    Calculated nominal output: "
                f"{entry.calculated_output_minimum_v:g}–"
                f"{entry.calculated_output_maximum_v:g} V; target "
                f"{entry.target_output_minimum_v:g}–{entry.target_output_maximum_v:g} V"
            )
        lines.append(
            "    Feedback-reference range: "
            f"{entry.feedback_reference_minimum_v:g}–"
            f"{entry.feedback_reference_maximum_v:g} V"
        )
        lines.append(f"    Basis: {entry.basis}")
        for issue in entry.issues:
            lines.append(f"    Issue: {issue}")

    if feedback_coverage.issue is not None:
        lines.append(f"  Coverage issue: {feedback_coverage.issue}")

    filter_coverage = report.rc_filter_coverage

    lines.append(f"RC filter coverage: {filter_coverage.status}")

    if filter_coverage.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {filter_coverage.netlist_sha256}")

    lines.append(f"  Scope: {filter_coverage.scope}")

    for entry in filter_coverage.entries:
        lines.append(
            f"  {entry.status} filter {entry.id}: {entry.resistor_reference} + "
            f"{entry.capacitor_reference}, {entry.input_net} -> {entry.filtered_net} "
            f"referenced to {entry.reference_net}"
        )
        for pin, nets in sorted(entry.pin_nets.items()):
            lines.append(f"    {pin}: {', '.join(nets) or '<unconnected>'}")
        if entry.resistance_ohms is not None:
            lines.append(f"    {entry.resistor_reference}: {entry.resistance_ohms:g} Ω nominal")
        if entry.capacitance_pf is not None:
            lines.append(f"    {entry.capacitor_reference}: {entry.capacitance_pf:g} pF nominal")
        lines.append(f"    Formula: {entry.formula}")
        if entry.calculated_corner_hz is not None:
            lines.append(
                f"    Calculated nominal corner: {entry.calculated_corner_hz:g} Hz; "
                f"target {entry.target_minimum_corner_hz:g}–"
                f"{entry.target_maximum_corner_hz:g} Hz"
            )
        if entry.unlisted_parallel_components:
            lines.append(
                "    Unlisted parallel components: " + ", ".join(entry.unlisted_parallel_components)
            )
        lines.append(f"    Basis: {entry.basis}")
        for issue in entry.issues:
            lines.append(f"    Issue: {issue}")

    if filter_coverage.issue is not None:
        lines.append(f"  Coverage issue: {filter_coverage.issue}")

    distribution = report.connector_return_distribution

    lines.append(f"Connector return-distribution coverage: {distribution.status}")

    if distribution.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {distribution.netlist_sha256}")

    if distribution.interface_catalog_sha256 is not None:
        lines.append(f"  Interface catalog SHA-256: {distribution.interface_catalog_sha256}")

    lines.append(f"  Scope: {distribution.scope}")

    for entry in distribution.entries:
        lines.append(
            f"  {entry.status} profile {entry.id}: connector "
            f"{entry.connector_reference or '<unbound>'}, interface {entry.interface_id}"
        )
        lines.append(
            f"    Signal contacts: {entry.signal_pin_count}; return contacts: "
            f"{entry.return_pin_count}; required returns at threshold: "
            f"{entry.required_return_pin_count}"
        )
        ratio = (
            "undefined (no return contacts)"
            if entry.signal_to_return_ratio is None
            else f"{entry.signal_to_return_ratio:g} signals per return"
        )
        lines.append(
            f"    Ratio: {ratio}; scope minimum: {entry.minimum_signal_pin_count} signals; "
            f"maximum: {entry.maximum_signal_to_return_ratio:g}"
        )
        for role, pin_map in (
            ("signal", entry.signal_pin_map),
            ("return", entry.return_pin_map),
            ("supply", entry.supply_pin_map),
            ("shield", entry.shield_pin_map),
            ("other", entry.other_pin_map),
            ("unclassified", entry.unclassified_pin_map),
        ):
            if pin_map:
                pins = ", ".join(f"{number}->{pin}" for number, pin in sorted(pin_map.items()))
                lines.append(f"    {role.title()} pins: {pins}")
        lines.append(f"    Basis: {entry.basis}")
        for issue in entry.issues:
            lines.append(f"    Issue: {issue}")

    if distribution.issue is not None:
        lines.append(f"  Coverage issue: {distribution.issue}")
    return lines

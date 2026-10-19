"""Format interface-peer lint coverage evidence."""

from __future__ import annotations

from .design_lint_report_models import DesignLintReport


def peer_reference_report_lines(report: DesignLintReport) -> list[str]:
    """Render digital, USB, serial, and I2C peer-reference coverage sections."""
    lines: list[str] = []
    if report.digital_peer_voltage_coverage:
        lines.append("Direct SPI/UART peer-voltage heuristic coverage:")
        for item in report.digital_peer_voltage_coverage:
            lines.append(
                f"  {item.rule_id}: {item.status} (mode: {item.mode}; "
                f"{item.recognized_endpoint_count} recognized pin function(s), "
                f"{item.assigned_endpoint_count} assigned, "
                f"{item.direct_peer_link_count} direct link(s), "
                f"{item.voltage_comparison_count} voltage comparison(s), "
                f"{item.same_voltage_link_count} same-label, "
                f"{item.different_voltage_link_count} different-label "
                f"({item.mapped_mismatch_link_count} map-covered), "
                f"{item.candidate_group_count} review group(s))"
            )
            if item.authored_map_path is not None:
                lines.append(
                    f"    Authored voltage map: {item.authored_map_path} "
                    f"(SHA-256 {item.authored_map_sha256})"
                )
            lines.append(f"    Native netlist SHA-256: {item.netlist_sha256}")

    usb_peer_coverage = report.usb_peer_reference_coverage

    if usb_peer_coverage is not None:
        has_usb_superspeed_groups = any(
            item.signal_family.startswith("USB SuperSpeed ")
            for item in usb_peer_coverage.endpoint_groups or ()
        )
        lines.append("USB peer-reference heuristic coverage:")
        lines.append(
            f"  {usb_peer_coverage.rule_id}: {usb_peer_coverage.status} "
            f"(mode: {usb_peer_coverage.mode}; "
            f"connector groups {usb_peer_coverage.supported_connector_group_count}/"
            f"{usb_peer_coverage.recognized_connector_group_count}; "
            f"PHY groups {usb_peer_coverage.supported_phy_group_count}/"
            f"{usb_peer_coverage.recognized_phy_group_count}; "
            f"{usb_peer_coverage.incomplete_group_count} incomplete, "
            f"{usb_peer_coverage.dnp_group_count} DNP)"
        )
        status_explanation = {
            "NO_USB_ENDPOINTS": "No supported USB data-pin function groups were recognized in the native netlist.",
            "INCOMPLETE": (
                f"{usb_peer_coverage.incomplete_group_count} recognized endpoint group(s) "
                "lacked complete evidence; any supported paths remain listed below."
            ),
            "NO_SUPPORTED_PEER_PATHS": (
                "No supported USB 2.0 D+/D− or exact direct USB SuperSpeed pair "
                "connector-to-PHY path matched the supported topology."
                if has_usb_superspeed_groups
                else "No direct or single-resistor USB D+/D− connector-to-PHY path matched "
                "the supported topology."
            ),
            "EVALUATED": "At least one supported connector-to-PHY path was checked.",
        }[usb_peer_coverage.status]
        lines.append(f"    Applicability: {status_explanation}")
        if usb_peer_coverage.endpoint_groups:
            lines.append("    Recognized endpoint groups:")
            for endpoint in usb_peer_coverage.endpoint_groups:
                endpoint_role = "PHY" if endpoint.endpoint_role == "phy" else "connector"
                port_group = (
                    f"port {endpoint.port_group}"
                    if endpoint.port_group is not None
                    else endpoint.signal_family
                    if endpoint.signal_family != "USB 2.0 data"
                    else "unnumbered port"
                )
                lines.append(
                    f"      {endpoint_role} {endpoint.reference} ({port_group}): "
                    f"{endpoint.disposition}"
                )
        lines.append(
            f"    {usb_peer_coverage.supported_data_path_count} supported peer path(s): "
            f"{usb_peer_coverage.common_reference_path_count} common-reference, "
            f"{usb_peer_coverage.separate_reference_path_count} separate-reference "
            f"({usb_peer_coverage.mapped_separate_reference_path_count} map-covered; "
            f"{usb_peer_coverage.candidate_group_count} review candidate(s))"
        )
        if usb_peer_coverage.path_entries:
            lines.append("    Matched connector-to-PHY paths:")
            for path in usb_peer_coverage.path_entries:
                connector_family = path.data_path.connector_signal_family
                phy_family = path.data_path.phy_signal_family
                if connector_family == phy_family == "USB 2.0 data":
                    path_label = (
                        f"port {path.data_path.port_group}"
                        if path.data_path.port_group is not None
                        else "unnumbered port"
                    )
                    data_labels = ("D+", "D-")
                else:
                    connector_direction = connector_family.rsplit(" ", 1)[-1]
                    phy_direction = phy_family.rsplit(" ", 1)[-1]
                    path_label = f"USB SuperSpeed {connector_direction} -> {phy_direction}"
                    data_labels = (
                        f"{connector_direction}+ -> {phy_direction}+",
                        f"{connector_direction}- -> {phy_direction}-",
                    )
                connector_reference_pins = ", ".join(
                    f"{item.pin}={item.function}/{item.electrical_type}"
                    for item in path.connector_reference_pins
                )
                phy_reference_pins = ", ".join(
                    f"{item.pin}={item.function}/{item.electrical_type}"
                    for item in path.phy_reference_pins
                )
                lines.append(
                    f"      {path.connector_reference} -> {path.phy_reference} ({path_label}): "
                    f"{path.reference_disposition}; references "
                    f"{path.connector_reference_net} [{connector_reference_pins}] / "
                    f"{path.phy_reference_net} [{phy_reference_pins}]"
                )
                for label, data_line in zip(
                    data_labels,
                    (path.data_path.positive, path.data_path.negative),
                    strict=True,
                ):
                    series = data_line.series_resistor
                    series_text = (
                        f" via {series.reference} ({series.value})" if series is not None else ""
                    )
                    inline = data_line.inline_component
                    if inline is not None:
                        series_text = (
                            f" via {inline.connector_pin} -> {inline.phy_pin} "
                            f"({inline.reference}, mapped inline component)"
                        )
                    shunt_references = tuple(
                        sorted(
                            {
                                item.reference_pin.rsplit(".", 1)[0]
                                for item in data_line.shunt_branches
                            },
                            key=lambda item: (item.casefold(), item),
                        )
                    )
                    shunt_text = (
                        f"; shunts {', '.join(shunt_references)}" if shunt_references else ""
                    )
                    lines.append(
                        f"        {label}: {', '.join(data_line.connector_pins)} "
                        f"({data_line.connector_net}) -> {', '.join(data_line.phy_pins)} "
                        f"({data_line.phy_net}){series_text}{shunt_text}"
                    )
                for shunt in path.data_path.protection_shunts:
                    assignments = ", ".join(shunt.pin_assignments)
                    lines.append(
                        f"        mapped protection shunt: {shunt.reference} "
                        f"({shunt.symbol}; {shunt.footprint}) [{assignments}]"
                    )
        if usb_peer_coverage.unsupported_multi_pin_paths:
            lines.append(
                "    Unsupported multi-pin topology candidates (coverage only; "
                "not a confirmed path or defect):"
            )
            for item in usb_peer_coverage.unsupported_multi_pin_paths:
                port_group = (
                    f"port {item.port_group}" if item.port_group is not None else "unnumbered port"
                )
                lines.append(
                    f"      {item.connector_reference} / {item.phy_reference} ({port_group}): "
                    f"{item.component_reference} ({item.component_symbol}; "
                    f"{item.component_footprint}; {item.component_pin_count} native pins)"
                )
                lines.append(
                    f"        D+: {item.positive_connector_net} "
                    f"[{', '.join(item.positive_connector_component_pins)}] / "
                    f"{item.positive_phy_net} "
                    f"[{', '.join(item.positive_phy_component_pins)}]"
                )
                lines.append(
                    f"        D-: {item.negative_connector_net} "
                    f"[{', '.join(item.negative_connector_component_pins)}] / "
                    f"{item.negative_phy_net} "
                    f"[{', '.join(item.negative_phy_component_pins)}]"
                )
            lines.append(
                "      An exact project-authored data-path map is required to evaluate "
                "these multi-pin topologies."
            )
        if usb_peer_coverage.usb_data_path_map_sha256 is not None:
            lines.append(
                f"    USB data-path map SHA-256: {usb_peer_coverage.usb_data_path_map_sha256}"
            )
        lines.append(f"    Native netlist SHA-256: {usb_peer_coverage.netlist_sha256}")

    serial_peer_coverage = report.serial_peer_reference_coverage

    if serial_peer_coverage is not None:
        lines.append("UART peer-reference heuristic coverage:")
        lines.append(
            f"  {serial_peer_coverage.rule_id}: {serial_peer_coverage.status} "
            f"(mode: {serial_peer_coverage.mode}; "
            f"{serial_peer_coverage.native_peer_link_count} native-function link(s), "
            f"{serial_peer_coverage.label_peer_link_count} label link(s); "
            f"{serial_peer_coverage.supported_reference_link_count} supported, "
            f"{serial_peer_coverage.incomplete_reference_link_count} incomplete; "
            f"{serial_peer_coverage.common_reference_link_count} common-reference, "
            f"{serial_peer_coverage.separate_reference_link_count} separate-reference "
            f"({serial_peer_coverage.mapped_separate_reference_link_count} map-covered; "
            f"{serial_peer_coverage.candidate_group_count} review candidate(s))"
        )
        status_explanation = {
            "NO_DIRECT_PEERS": (
                "No direct TX-to-RX links matched the bounded native-function or "
                "numbered-label checks."
            ),
            "INCOMPLETE": (
                f"{serial_peer_coverage.incomplete_reference_link_count} discovered link(s) "
                "lacked complete explicit reference-pin evidence; supported links remain counted."
            ),
            "EVALUATED": (
                "Every discovered direct serial link had complete explicit reference-pin evidence."
            ),
        }[serial_peer_coverage.status]
        lines.append(f"    Applicability: {status_explanation}")
        if serial_peer_coverage.link_entries:
            lines.append("    Discovered serial links:")
            for entry in serial_peer_coverage.link_entries:
                if entry.discovery_basis == "native_function":
                    basis = "native-function"
                    peers = f"{entry.first_reference} -> {entry.second_reference}"
                else:
                    basis = "channel-label"
                    peers = f"{entry.first_reference} / {entry.second_reference}"
                lines.append(
                    f"      {basis}: {peers} ({entry.signal_group}; "
                    f"nets {', '.join(entry.signal_nets)}; "
                    f"pins {', '.join(entry.signal_pins)}): {entry.disposition}"
                )
        lines.append(f"    Authored serial-peer map: {serial_peer_coverage.authored_map_state}")
        if serial_peer_coverage.authored_map_path is not None:
            lines.append(
                f"    Map source: {serial_peer_coverage.authored_map_path} "
                f"(SHA-256 {serial_peer_coverage.authored_map_source_sha256})"
            )
        if serial_peer_coverage.authored_serial_peer_map_sha256 is not None:
            lines.append(
                "    Typed serial-peer map SHA-256: "
                f"{serial_peer_coverage.authored_serial_peer_map_sha256}"
            )
        lines.append(f"    Native netlist SHA-256: {serial_peer_coverage.netlist_sha256}")
    i2c_peer_coverage = report.i2c_peer_reference_coverage
    if i2c_peer_coverage is not None:
        lines.append("I2C peer-reference heuristic coverage:")
        lines.append(
            f"  {i2c_peer_coverage.rule_id}: {i2c_peer_coverage.status} "
            f"(mode: {i2c_peer_coverage.mode}; "
            f"{i2c_peer_coverage.recognized_endpoint_count} recognized endpoint(s), "
            f"{i2c_peer_coverage.shared_bus_count} shared bus group(s), "
            f"{i2c_peer_coverage.common_reference_bus_count} common-reference, "
            f"{i2c_peer_coverage.incomplete_reference_bus_count} incomplete, "
            f"{i2c_peer_coverage.split_reference_bus_count} split-reference "
            f"({i2c_peer_coverage.candidate_group_count} review candidate(s); "
            f"{i2c_peer_coverage.component_peer_covered_bus_count} covered by component-peer "
            "review)"
        )
        status_explanation = {
            "NO_SHARED_BUS_PEERS": (
                "Fewer than two supported fitted IC endpoints share an exact native SDA/SCL pair."
            ),
            "INCOMPLETE": (
                "At least one shared bus group lacks complete explicit reference-pin evidence."
            ),
            "EVALUATED": (
                "Every discovered shared bus group has complete explicit reference-pin evidence; "
                "split references already covered by component-peer review are not duplicated."
            ),
        }[i2c_peer_coverage.status]
        lines.append(f"    Applicability: {status_explanation}")
        for entry in i2c_peer_coverage.entries:
            participants = ", ".join(entry.participants)
            references = ", ".join(entry.reference_nets) or "none recognized"
            incomplete = (
                f"; incomplete: {', '.join(entry.incomplete_references)}"
                if entry.incomplete_references
                else ""
            )
            lines.append(
                f"    SDA {entry.sda_net} / SCL {entry.scl_net}: {participants}; "
                f"reference nets {references}{incomplete}: {entry.disposition}"
            )
        lines.append(f"    Native netlist SHA-256: {i2c_peer_coverage.netlist_sha256}")
    spi_peer_coverage = report.spi_peer_reference_coverage
    if spi_peer_coverage is not None:
        lines.append("SPI peer-reference heuristic coverage:")
        lines.append(
            f"  {spi_peer_coverage.rule_id}: {spi_peer_coverage.status} "
            f"(mode: {spi_peer_coverage.mode}; "
            f"{spi_peer_coverage.recognized_endpoint_count} recognized endpoint(s), "
            f"{spi_peer_coverage.shared_clock_bus_count} shared clock group(s), "
            f"{spi_peer_coverage.common_reference_bus_count} common-reference, "
            f"{spi_peer_coverage.incomplete_reference_bus_count} incomplete, "
            f"{spi_peer_coverage.split_reference_bus_count} split-reference "
            f"({spi_peer_coverage.candidate_group_count} review candidate(s); "
            f"{spi_peer_coverage.component_peer_covered_bus_count} covered by component-peer "
            "review)"
        )
        status_explanation = {
            "NO_SHARED_CLOCK_PEERS": (
                "Fewer than two supported fitted IC endpoints share one exact native SCK/SCLK net."
            ),
            "INCOMPLETE": (
                "At least one shared-clock group lacks complete explicit reference-pin evidence."
            ),
            "EVALUATED": (
                "Every discovered shared-clock group has complete explicit reference-pin evidence; "
                "split references already covered by component-peer review are not duplicated."
            ),
        }[spi_peer_coverage.status]
        lines.append(f"    Applicability: {status_explanation}")
        for entry in spi_peer_coverage.entries:
            participants = ", ".join(entry.participants)
            references = ", ".join(entry.reference_nets) or "none recognized"
            incomplete = (
                f"; incomplete: {', '.join(entry.incomplete_references)}"
                if entry.incomplete_references
                else ""
            )
            lines.append(
                f"    SCK {entry.clock_net}: {participants}; reference nets {references}"
                f"{incomplete}: {entry.disposition}"
            )
        lines.append(f"    Native netlist SHA-256: {spi_peer_coverage.netlist_sha256}")
    can_peer_coverage = report.can_peer_reference_coverage
    if can_peer_coverage is not None:
        lines.append("CAN peer-reference heuristic coverage:")
        lines.append(
            f"  {can_peer_coverage.rule_id}: {can_peer_coverage.status} "
            f"(mode: {can_peer_coverage.mode}; "
            f"{can_peer_coverage.recognized_endpoint_count} recognized endpoint(s), "
            f"{can_peer_coverage.shared_can_bus_count} shared CAN bus group(s), "
            f"{can_peer_coverage.common_reference_bus_count} common-reference, "
            f"{can_peer_coverage.incomplete_reference_bus_count} incomplete, "
            f"{can_peer_coverage.split_reference_bus_count} split-reference "
            f"({can_peer_coverage.candidate_group_count} review candidate(s); "
            f"{can_peer_coverage.component_peer_covered_bus_count} covered by component-peer "
            "review)"
        )
        status_explanation = {
            "NO_SHARED_CAN_BUSES": (
                "Fewer than two supported fitted IC endpoints share one exact native CANH/CANL pair."
            ),
            "INCOMPLETE": (
                "At least one shared CAN bus group lacks complete explicit reference-pin evidence."
            ),
            "EVALUATED": (
                "Every discovered shared CAN bus group has complete explicit reference-pin "
                "evidence; split references already covered by component-peer review are not "
                "duplicated."
            ),
        }[can_peer_coverage.status]
        lines.append(f"    Applicability: {status_explanation}")
        for entry in can_peer_coverage.entries:
            participants = ", ".join(entry.participants)
            references = ", ".join(entry.reference_nets) or "none recognized"
            incomplete = (
                f"; incomplete: {', '.join(entry.incomplete_references)}"
                if entry.incomplete_references
                else ""
            )
            lines.append(
                f"    CANH {entry.canh_net} / CANL {entry.canl_net}: {participants}; "
                f"reference nets {references}{incomplete}: {entry.disposition}"
            )
        lines.append(f"    Native netlist SHA-256: {can_peer_coverage.netlist_sha256}")
    rs485_peer_coverage = report.rs485_peer_reference_coverage
    if rs485_peer_coverage is not None:
        lines.append("RS-485 peer-reference heuristic coverage:")
        lines.append(
            f"  {rs485_peer_coverage.rule_id}: {rs485_peer_coverage.status} "
            f"(mode: {rs485_peer_coverage.mode}; "
            f"{rs485_peer_coverage.recognized_endpoint_count} mapped endpoint(s), "
            f"{rs485_peer_coverage.shared_pair_count} shared pair group(s), "
            f"{rs485_peer_coverage.common_reference_pair_count} common-reference, "
            f"{rs485_peer_coverage.incomplete_reference_pair_count} incomplete, "
            f"{rs485_peer_coverage.split_reference_pair_count} split-reference "
            f"({rs485_peer_coverage.candidate_group_count} review candidate(s))"
        )
        status_explanation = {
            "NOT_CONFIGURED": "No project-authored RS-485 topology map is configured.",
            "PENDING": "The project marks RS-485 topology review as pending.",
            "NOT_APPLICABLE": "The project records RS-485 topology as not applicable.",
            "NO_SHARED_ENDPOINTS": (
                "No mapped fitted endpoints share one exact native RS-485 line pair."
            ),
            "INCOMPLETE": (
                "At least one shared pair lacks complete explicit reference-pin evidence."
            ),
            "EVALUATED": (
                "Every mapped fitted endpoint group has complete explicit reference-pin evidence."
            ),
        }[rs485_peer_coverage.status]
        lines.append(f"    Applicability: {status_explanation}")
        if rs485_peer_coverage.authored_map_path is not None:
            lines.append(
                f"    Authored RS-485 map: {rs485_peer_coverage.authored_map_path} "
                f"(SHA-256 {rs485_peer_coverage.authored_map_source_sha256})"
            )
        for entry in rs485_peer_coverage.entries:
            participants = ", ".join(entry.participants)
            references = ", ".join(entry.reference_nets) or "none recognized"
            incomplete = (
                f"; incomplete: {', '.join(entry.incomplete_references)}"
                if entry.incomplete_references
                else ""
            )
            lines.append(
                f"    Bus {entry.bus_id} pair {entry.pair_id} "
                f"({entry.line_1_net} / {entry.line_2_net}): {participants}; "
                f"reference nets {references}{incomplete}: {entry.disposition}"
            )
        lines.append(f"    Native netlist SHA-256: {rs485_peer_coverage.netlist_sha256}")
    return lines

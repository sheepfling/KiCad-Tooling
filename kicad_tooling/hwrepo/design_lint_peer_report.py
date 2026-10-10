"""Format interface-peer lint coverage evidence."""

from __future__ import annotations

from .models import DesignLintReport


def peer_reference_report_lines(report: DesignLintReport) -> list[str]:
    """Render digital, USB, and serial peer-reference coverage sections."""
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
                "No direct or single-resistor USB D+/D− connector-to-PHY path matched "
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
                port_group = (
                    f"port {path.data_path.port_group}"
                    if path.data_path.port_group is not None
                    else "unnumbered port"
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
                    f"      {path.connector_reference} -> {path.phy_reference} ({port_group}): "
                    f"{path.reference_disposition}; references "
                    f"{path.connector_reference_net} [{connector_reference_pins}] / "
                    f"{path.phy_reference_net} [{phy_reference_pins}]"
                )
                for label, data_line in (
                    ("D+", path.data_path.positive),
                    ("D-", path.data_path.negative),
                ):
                    series = data_line.series_resistor
                    series_text = (
                        f" via {series.reference} ({series.value})" if series is not None else ""
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
    return lines

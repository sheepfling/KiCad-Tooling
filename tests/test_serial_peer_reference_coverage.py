"""Serial peer-reference applicability and coverage regressions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import text_report
from kicad_tooling.hwrepo.models import DesignLintReport, SerialPeerReferenceCoverageReport
from tests.serial_peer_reference_support import report, serial_peer_map, serial_reference_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


class SerialPeerReferenceCoverageTests:
    def test_reference_coverage_distinguishes_evaluated_incomplete_and_unseen_links(self) -> None:
        split = report(serial_reference_netlist())
        assert (split.serial_peer_reference_coverage) is not None
        assert split.serial_peer_reference_coverage is not None
        assert (
            (
                split.serial_peer_reference_coverage.status,
                split.serial_peer_reference_coverage.native_peer_link_count,
                split.serial_peer_reference_coverage.supported_reference_link_count,
                split.serial_peer_reference_coverage.separate_reference_link_count,
                split.serial_peer_reference_coverage.candidate_group_count,
            )
        ) == (("EVALUATED", 2, 2, 2, 1))

        common = report(
            serial_reference_netlist(output_reference_net="GND", input_reference_net="GND")
        )
        assert common.serial_peer_reference_coverage is not None
        assert (
            (
                common.serial_peer_reference_coverage.status,
                common.serial_peer_reference_coverage.common_reference_link_count,
                common.serial_peer_reference_coverage.candidate_group_count,
            )
        ) == (("EVALUATED", 2, 0))
        common_coverage = common.serial_peer_reference_coverage
        assert common_coverage is not None
        assert ({item.disposition for item in common_coverage.link_entries or ()}) == (
            {"COMMON_REFERENCE"}
        )

        source = serial_reference_netlist()
        incomplete_source = source.model_copy(
            update={
                "pin_functions": {
                    pin: function for pin, function in source.pin_functions.items() if pin != "U2.9"
                }
            }
        )
        incomplete = report(incomplete_source)
        assert incomplete.serial_peer_reference_coverage is not None
        assert (
            (
                incomplete.serial_peer_reference_coverage.status,
                incomplete.serial_peer_reference_coverage.native_peer_link_count,
                incomplete.serial_peer_reference_coverage.incomplete_reference_link_count,
                incomplete.serial_peer_reference_coverage.candidate_group_count,
            )
        ) == (("INCOMPLETE", 2, 2, 0))
        incomplete_coverage = incomplete.serial_peer_reference_coverage
        assert incomplete_coverage is not None
        assert (
            tuple(
                (
                    item.discovery_basis,
                    item.first_reference,
                    item.second_reference,
                    item.signal_group,
                    item.signal_pins,
                    item.disposition,
                )
                for item in incomplete_coverage.link_entries or ()
            )
        ) == (
            (
                ("native_function", "U1", "U2", "UART_A", ("U1.1", "U2.1"), "INCOMPLETE"),
                ("native_function", "U2", "U1", "UART_B", ("U2.2", "U1.2"), "INCOMPLETE"),
            )
        )

        disconnected_source = source.model_copy(
            update={
                "nets": {
                    **source.nets,
                    "UART_A": ("U1.1",),
                    "UART_B": ("U1.2",),
                    "UART_RX_ONLY": ("U2.1",),
                    "UART_TX_ONLY": ("U2.2",),
                }
            }
        )
        disconnected = report(disconnected_source)
        assert disconnected.serial_peer_reference_coverage is not None
        assert (
            (
                disconnected.serial_peer_reference_coverage.status,
                disconnected.serial_peer_reference_coverage.native_peer_link_count,
                disconnected.serial_peer_reference_coverage.label_peer_link_count,
            )
        ) == (("NO_DIRECT_PEERS", 0, 0))

        rendered = text_report(incomplete)
        assert ("UART peer-reference heuristic coverage:") in (rendered)
        assert ("2 discovered link(s) lacked complete explicit reference-pin evidence") in (
            rendered
        )
        assert ("native-function: U1 -> U2 (UART_A; nets UART_A; pins U1.1, U2.1): INCOMPLETE") in (
            rendered
        )
        assert ("Native netlist SHA-256:") in (rendered)

        legacy_payload = incomplete_coverage.model_dump()
        legacy_payload.pop("link_entries")
        assert (
            SerialPeerReferenceCoverageReport.model_validate(legacy_payload).link_entries
        ) is None
        inconsistent_payload = incomplete_coverage.model_dump()
        inconsistent_payload["incomplete_reference_link_count"] = 0
        with pytest.raises(ValidationError, match="Incomplete serial link count"):
            SerialPeerReferenceCoverageReport.model_validate(inconsistent_payload)

    def test_reference_coverage_records_exact_map_suppression(self) -> None:
        source = serial_reference_netlist()
        reviewed = serial_peer_map(
            reference_policy="separate_nets",
            output_reference_net="GND_A",
            input_reference_net="GND_B",
        )
        mapped = report(source, serial_peers=reviewed)
        assert mapped.serial_peer_reference_coverage is not None
        assert (
            (
                mapped.serial_peer_reference_coverage.authored_map_state,
                mapped.serial_peer_reference_coverage.authored_serial_peer_map_sha256 is not None,
                mapped.serial_peer_reference_coverage.separate_reference_link_count,
                mapped.serial_peer_reference_coverage.mapped_separate_reference_link_count,
                mapped.serial_peer_reference_coverage.candidate_group_count,
            )
        ) == (("required", True, 2, 2, 0))
        assert (
            {item.disposition for item in mapped.serial_peer_reference_coverage.link_entries or ()}
        ) == ({"MAP_COVERED_SEPARATE_REFERENCE"})

    def test_schema_one_report_without_serial_coverage_remains_readable(self) -> None:
        payload = report(serial_reference_netlist()).model_dump()
        payload["schema_version"] = "1"
        payload.pop("serial_peer_reference_coverage")

        legacy = DesignLintReport.model_validate(payload)

        assert (legacy.schema_version) == ("1")
        assert (legacy.serial_peer_reference_coverage) is None

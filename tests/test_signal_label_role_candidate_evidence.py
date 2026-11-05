"""Source-binding regressions for cross-protocol pin and net-label roles."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.can_line_polarity import can_line_polarity_label_candidates
from kicad_tooling.hwrepo.design_lint_signal_label_role_candidate_evidence import (
    CanLinePolarityLabelMismatchEvidence,
    I2cSignalLabelRoleMismatchEvidence,
    Rs485DataLabelRoleMismatchEvidence,
    Rs485LineLabelRoleMismatchEvidence,
    SerialTxRxLabelRoleMismatchEvidence,
    SignalLabelRoleMismatchCandidate,
    SpiDataLabelRoleMismatchEvidence,
    project_signal_label_role_mismatch_evidence,
)
from kicad_tooling.hwrepo.i2c_signal_label import i2c_signal_label_role_candidates
from kicad_tooling.hwrepo.rs485_data_label_mismatch import (
    rs485_data_direction_label_candidates,
)
from kicad_tooling.hwrepo.rs485_line_label_mismatch import rs485_line_label_mismatch_candidates
from kicad_tooling.hwrepo.serial_tx_rx_label_mismatch import (
    serial_tx_rx_label_mismatch_candidates,
)
from kicad_tooling.hwrepo.spi_data_label import spi_data_polarity_label_candidates
from tests.design_lint_fixtures import can_netlist
from tests.design_lint_fixtures.i2c_signal_label import i2c_signal_label_netlist
from tests.design_lint_fixtures.rs485_data_label_mismatch import rs485_data_label_netlist
from tests.design_lint_fixtures.rs485_line_label_mismatch import rs485_line_label_mismatch_netlist
from tests.design_lint_fixtures.serial_tx_rx_label_mismatch import serial_tx_rx_label_netlist
from tests.design_lint_fixtures.spi_data_label import spi_data_label_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.evidence_lint]


def test_serial_family_candidates_keep_typed_source_and_existing_wire_fields() -> None:
    can_source = can_netlist("121R").model_copy(
        update={
            "nets": {
                "CAN_HIGH": ("U1.2", "R1.1"),
                "CAN_LOW": ("U1.1", "R1.2"),
            }
        }
    )
    cases = (
        (
            i2c_signal_label_role_candidates(i2c_signal_label_netlist(reversed_labels=True))[0],
            I2cSignalLabelRoleMismatchEvidence,
            {"pin", "pin_function", "pin_role", "net", "net_role"},
        ),
        (
            can_line_polarity_label_candidates(can_source)[0],
            CanLinePolarityLabelMismatchEvidence,
            {"pin", "pin_function", "pin_role", "net", "net_role"},
        ),
        (
            spi_data_polarity_label_candidates(spi_data_label_netlist(reversed_labels=True))[0],
            SpiDataLabelRoleMismatchEvidence,
            {"pin", "pin_function", "pin_role", "net", "net_role"},
        ),
        (
            rs485_data_direction_label_candidates(rs485_data_label_netlist())[0],
            Rs485DataLabelRoleMismatchEvidence,
            {"reference", "pin", "pin_function", "pin_role", "channel", "net", "net_role"},
        ),
        (
            rs485_line_label_mismatch_candidates(rs485_line_label_mismatch_netlist())[0],
            Rs485LineLabelRoleMismatchEvidence,
            {
                "reference",
                "pin",
                "pin_function",
                "pin_role",
                "net",
                "net_role",
                "identity_basis",
            },
        ),
        (
            serial_tx_rx_label_mismatch_candidates(serial_tx_rx_label_netlist())[0],
            SerialTxRxLabelRoleMismatchEvidence,
            {"reference", "pin", "pin_function", "pin_role", "channel", "net", "net_role"},
        ),
    )

    for candidate, source_type, evidence_keys in cases:
        assert isinstance(candidate, SignalLabelRoleMismatchCandidate)
        assert isinstance(candidate.source_evidence, source_type)
        assert set(candidate.evidence) == evidence_keys
        assert (
            candidate.evidence
            == project_signal_label_role_mismatch_evidence(candidate.source_evidence).evidence
        )


def test_corrected_rs485_line_pair_invalidates_the_source_record() -> None:
    candidate = rs485_line_label_mismatch_candidates(rs485_line_label_mismatch_netlist())[0]
    assert isinstance(candidate, SignalLabelRoleMismatchCandidate)
    source = candidate.source_evidence
    assert isinstance(source, Rs485LineLabelRoleMismatchEvidence)
    corrected = rs485_line_label_mismatch_netlist(crossed=False)

    with pytest.raises(ValueError, match="current native pin and label"):
        replace(source, observed=corrected)


def test_corrected_rs485_data_and_serial_labels_invalidate_the_source_records() -> None:
    data_candidate = rs485_data_direction_label_candidates(rs485_data_label_netlist())[0]
    serial_candidate = serial_tx_rx_label_mismatch_candidates(serial_tx_rx_label_netlist())[0]
    assert isinstance(data_candidate, SignalLabelRoleMismatchCandidate)
    assert isinstance(serial_candidate, SignalLabelRoleMismatchCandidate)
    data_source = data_candidate.source_evidence
    serial_source = serial_candidate.source_evidence
    assert isinstance(data_source, Rs485DataLabelRoleMismatchEvidence)
    assert isinstance(serial_source, SerialTxRxLabelRoleMismatchEvidence)

    with pytest.raises(ValueError, match="current native pin and net"):
        replace(data_source, observed=rs485_data_label_netlist(crossed=False))
    with pytest.raises(ValueError, match="paired channel"):
        replace(data_source, paired_net="UART2_TX")
    with pytest.raises(ValueError, match="current native pin and net"):
        replace(serial_source, observed=serial_tx_rx_label_netlist(crossed=False))

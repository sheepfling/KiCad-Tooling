"""Collect SPI signal checks in stable order."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .spi_clock_data_same_net import spi_clock_control_data_same_net_candidates
from .spi_clock_select_label_mismatch import spi_clock_select_label_mismatch_candidates
from .spi_control_same_net import spi_clock_chip_select_same_net_candidates
from .spi_data_label import spi_data_polarity_label_candidates
from .spi_same_net import spi_data_input_output_same_net_candidates
from .spi_shared_chip_select import spi_chip_select_inputs_share_net_candidates
from .spi_shared_data_outputs import spi_data_outputs_share_net_candidates
from .spi_signal_named_rail import spi_signal_on_named_rail_candidates


def spi_signal_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Collect SPI signal checks without owning their predicates."""
    return (
        *spi_data_polarity_label_candidates(observed),
        *spi_clock_select_label_mismatch_candidates(observed),
        *spi_signal_on_named_rail_candidates(observed),
        *spi_data_input_output_same_net_candidates(observed),
        *spi_clock_control_data_same_net_candidates(observed),
        *spi_clock_chip_select_same_net_candidates(observed),
        *spi_chip_select_inputs_share_net_candidates(observed),
        *spi_data_outputs_share_net_candidates(observed),
    )

"""Source-binding regressions for typed SPI same-net candidate variants."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

from kicad_tooling.hwrepo.design_lint_spi_same_net_candidate_evidence import (
    SpiClockDataSameNetEvidence,
    SpiClockSelectSameNetEvidence,
    SpiDataRolesSameNetEvidence,
    SpiSameNetCandidate,
)
from kicad_tooling.hwrepo.spi_clock_data_same_net import (
    spi_clock_control_data_same_net_candidates,
)
from kicad_tooling.hwrepo.spi_control_same_net import spi_clock_chip_select_same_net_candidates
from kicad_tooling.hwrepo.spi_same_net import spi_data_input_output_same_net_candidates
from tests.design_lint_fixtures.spi_clock_control_same_net import (
    spi_clock_chip_select_same_net_netlist,
    spi_clock_control_same_net_netlist,
)
from tests.design_lint_fixtures.spi_data_same_net import spi_data_same_net_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


def test_each_spi_same_net_variant_retains_its_current_native_source() -> None:
    candidates = (
        spi_data_input_output_same_net_candidates(spi_data_same_net_netlist())[0],
        spi_clock_control_data_same_net_candidates(spi_clock_control_same_net_netlist())[0],
        spi_clock_chip_select_same_net_candidates(spi_clock_chip_select_same_net_netlist())[0],
    )
    expected_types = (
        SpiDataRolesSameNetEvidence,
        SpiClockDataSameNetEvidence,
        SpiClockSelectSameNetEvidence,
    )

    for candidate, expected_type in zip(candidates, expected_types, strict=True):
        assert isinstance(candidate, SpiSameNetCandidate)
        assert isinstance(candidate.source_evidence, expected_type)
        assert candidate.evidence
        assert isinstance(candidate.source_evidence.group.roles, MappingProxyType)
        with pytest.raises(ValueError, match="current native netlist"):
            replace(
                candidate.source_evidence,
                observed=candidate.source_evidence.observed.model_copy(update={"nets": {}}),
            )

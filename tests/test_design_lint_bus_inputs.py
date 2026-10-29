"""One native observation must feed every typed bus-theme input."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_bus_inputs import BusCandidateInputs
from kicad_tooling.hwrepo.i2c_address_inputs import I2cAddressCandidateInput
from kicad_tooling.hwrepo.i2c_address_models import I2cAddressCoverageReport
from kicad_tooling.hwrepo.i2c_pullup_inputs import I2cPullupSnifferInput
from kicad_tooling.hwrepo.i2c_pullup_models import I2cPullupHeuristicCoverage
from kicad_tooling.hwrepo.models import NetlistContract

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
]


def test_bus_inputs_reject_mixed_native_observations() -> None:
    observed = NetlistContract(components={}, nets={})
    other = NetlistContract(components={}, nets={"OTHER": ("U1.1",)})
    pullup = I2cPullupSnifferInput(
        observed=observed,
        coverage=I2cPullupHeuristicCoverage(status="NOT_CONFIGURED"),
    )
    current_address = I2cAddressCandidateInput(
        observed=observed,
        address_map=None,
        coverage=I2cAddressCoverageReport(),
    )
    assert (
        BusCandidateInputs(
            observed=observed, i2c_address=current_address, i2c_pullup=pullup
        ).observed
        is observed
    )
    address = I2cAddressCandidateInput(
        observed=other,
        address_map=None,
        coverage=I2cAddressCoverageReport(),
    )

    with pytest.raises(ValueError, match="must share one observed native netlist"):
        BusCandidateInputs(observed=observed, i2c_address=address, i2c_pullup=pullup)

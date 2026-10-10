"""I2C address-map contract validation regressions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.models import (
    I2cAddressBitRequirement,
    I2cAddressMap,
    I2cAddressSegmentRequirement,
)
from tests.design_lint_fixtures.i2c_addresses import responder

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_address_map_rejects_ambiguous_pin_and_segment_declarations() -> None:
    first = responder("U1", address=0x50)
    with pytest.raises(ValidationError):
        I2cAddressBitRequirement(
            bit=7,
            pin="U1.3",
            function="A0",
            low_net="GND",
            high_net="+3V3",
        )
    with pytest.raises(ValidationError, match="unique SDA/SCL net pairs"):
        I2cAddressMap(
            basis="Synthetic duplicate segments use one signal pair",
            segments=(
                I2cAddressSegmentRequirement(
                    id="A",
                    sda_net="I2C_SDA",
                    scl_net="I2C_SCL",
                    responders=(first[1],),
                ),
                I2cAddressSegmentRequirement(
                    id="B",
                    sda_net="I2C_SDA",
                    scl_net="I2C_SCL",
                    responders=(responder("U2", address=0x50, segment="B")[1],),
                ),
            ),
        )

    with pytest.raises(ValidationError, match="cannot share signal nets"):
        I2cAddressMap(
            basis="Synthetic shared endpoint must not declare isolated address domains",
            segments=(
                I2cAddressSegmentRequirement(
                    id="A",
                    sda_net="SDA_A",
                    scl_net="SCL_SHARED",
                    responders=(first[1],),
                ),
                I2cAddressSegmentRequirement(
                    id="B",
                    sda_net="SDA_B",
                    scl_net="SCL_SHARED",
                    responders=(responder("U2", address=0x50, segment="B")[1],),
                ),
            ),
        )

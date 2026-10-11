"""Focused pytest coverage for authored SPI membership and signal contracts."""

from __future__ import annotations

from typing import Literal

import pytest

from kicad_tooling.hwrepo.models import ElectricalCheck, NetlistContract
from kicad_tooling.hwrepo.spi_contract import spi_checks
from kicad_tooling.hwrepo.spi_models import (
    SpiAnalysis,
    SpiBusRequirement,
    SpiDeviceRequirement,
    SpiPinNetRequirement,
)
from tests.electrical_spi_support import spi_netlist, spi_requirement

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _checks(specification: SpiAnalysis, observed: NetlistContract) -> dict[str, ElectricalCheck]:
    return {item.id: item for item in spi_checks(specification, observed)}


def test_spi_contract_checks_membership_chip_selects_and_shared_selection() -> None:
    specification = spi_requirement()
    checks = _checks(specification, spi_netlist(specification))

    assert checks
    assert all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values())
    assert checks["spi/control/device/sensor/route/sck"].status == "PASS"
    assert checks["spi/control/device/memory/route/miso"].status == "PASS"

    disconnected = _checks(
        specification, spi_netlist(specification, fault="device2-cs-disconnected")
    )
    assert disconnected["spi/control/device/memory/pins"].status == "FAIL"
    assert "expected SPI_CS1" in disconnected["spi/control/device/memory/pins"].detail

    wrong_net = _checks(specification, spi_netlist(specification, fault="device2-cs-wrong-net"))
    assert wrong_net["spi/control/device/memory/pins"].status == "FAIL"
    assert "UNEXPECTED_CS" in wrong_net["spi/control/device/memory/pins"].detail

    shared = spi_requirement(shared_select=True)
    shared_checks = _checks(shared, spi_netlist(shared))
    assert all(item.status in {"PASS", "NOT_APPLICABLE"} for item in shared_checks.values())

    invalid_devices = (
        shared.buses[0].devices[0],
        SpiDeviceRequirement.model_validate(
            {
                **shared.buses[0].devices[1].model_dump(),
                "shared_select_group": None,
            }
        ),
    )
    with pytest.raises(ValueError, match="shared without one explicit"):
        SpiBusRequirement(
            id="control",
            basis=shared.buses[0].basis,
            controller=shared.buses[0].controller,
            devices=invalid_devices,
        )


@pytest.mark.parametrize("disposition", ["unconnected", "not_present"])
def test_spi_contract_allows_write_only_devices(
    disposition: Literal["unconnected", "not_present"],
) -> None:
    specification = spi_requirement(device2_miso=disposition)
    checks = _checks(specification, spi_netlist(specification))

    assert checks["spi/control/device/memory/route/miso"].status == "NOT_APPLICABLE"
    assert all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values())


def test_spi_contract_checks_buffered_miso_endpoints() -> None:
    buffered = spi_requirement(buffered_miso=True, device2_miso="not_present")
    checks = _checks(buffered, spi_netlist(buffered))

    assert checks["spi/control/bridge/U9/pins"].status == "PASS"
    assert checks["spi/control/device/sensor/route/miso"].status == "PASS"
    assert (
        "Internal bridge behavior is not verified"
        in checks["spi/control/device/sensor/route/miso"].detail
    )

    wrong_bridge = _checks(buffered, spi_netlist(buffered, fault="bridge-output-wrong-net"))
    assert wrong_bridge["spi/control/bridge/U9/pins"].status == "FAIL"
    assert wrong_bridge["spi/control/device/sensor/route/miso"].status == "FAIL"


def test_spi_contract_requires_controller_mapping_for_every_device_chip_select() -> None:
    specification = spi_requirement()
    bus = specification.buses[0]
    with pytest.raises(ValueError, match="has no declared controller pin"):
        SpiBusRequirement(
            id="control",
            basis=bus.basis,
            controller=bus.controller.model_copy(
                update={"chip_selects": bus.controller.chip_selects[:1]}
            ),
            devices=bus.devices,
        )

    shared = spi_requirement(shared_select=True).buses[0]
    with pytest.raises(ValueError, match="Every declared SPI controller chip-select"):
        SpiBusRequirement(
            id=shared.id,
            basis=shared.basis,
            controller=shared.controller.model_copy(
                update={
                    "chip_selects": (
                        *shared.controller.chip_selects,
                        SpiPinNetRequirement(pin="U1.5", net="SPI_CS1"),
                    )
                }
            ),
            devices=shared.devices,
        )

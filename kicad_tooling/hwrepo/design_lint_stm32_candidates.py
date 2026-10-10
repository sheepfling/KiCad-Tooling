"""Translate STM32 CubeMX project-map coverage and mismatch observations."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import Stm32PinMapCoverageReport


def stm32_candidates(
    stm32_pin_map_coverage: Stm32PinMapCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Build firmware pin-map coverage findings from the authored project contract."""
    found: list[Candidate] = []
    if stm32_pin_map_coverage is not None:
        for device in stm32_pin_map_coverage.unmapped_devices:
            found.append(
                Candidate(
                    rule_id="mcu.stm32_cubemx_pin_map",
                    subject=f"{device.reference}: STM32 CubeMX pin-map coverage is missing",
                    message=(
                        "This fitted component is identified as an STM32 device, but the project "
                        "has no explicit CubeMX pin-map contract for it. Confirm that CubeMX is "
                        "the firmware source; if so, map every package pin to a KiCad symbol pin "
                        "or record a reasoned exclusion. This name-based discovery prompt does "
                        "not establish that the device is configured by CubeMX."
                    ),
                    evidence={
                        "reference": (device.reference,),
                        "part": (device.observed_part,),
                        "symbol": (device.observed_symbol or "<unknown>",),
                        "native_netlist_sha256": (device.netlist_sha256,),
                    },
                )
            )
        for mismatch in stm32_pin_map_coverage.mismatches:
            expected_labels = (
                ("<not checked>",)
                if mismatch.accepted_ioc_gpio_labels is None
                else tuple(
                    "<absent>" if item is None else item
                    for item in mismatch.accepted_ioc_gpio_labels
                )
            )
            found.append(
                Candidate(
                    rule_id="mcu.stm32_cubemx_pin_map",
                    subject=(
                        f"{mismatch.reference}.{mismatch.port_pin}: "
                        "CubeMX and KiCad pin map differs from the project contract"
                    ),
                    message=(
                        "A project-mapped STM32 package pin disagrees with the authored "
                        "CubeMX/KiCad pin-map contract. Review the MCU pinout, schematic net, "
                        "and firmware configuration. " + "; ".join(mismatch.issues)
                    ),
                    evidence={
                        "mcu_reference": (mismatch.reference,),
                        "package_pin": (mismatch.port_pin,),
                        "symbol_pin": (f"{mismatch.reference}.{mismatch.symbol_pin}",),
                        "expected_net": (mismatch.expected_net,),
                        "observed_net": mismatch.observed_nets or ("<unconnected>",),
                        "accepted_ioc_signal": mismatch.accepted_ioc_signals,
                        "observed_ioc_signal": (mismatch.observed_ioc_signal or "<missing>",),
                        "accepted_ioc_gpio_label": expected_labels,
                        "observed_ioc_gpio_label": (
                            mismatch.observed_ioc_gpio_label or "<absent>",
                        ),
                        "ioc_path": (mismatch.ioc_path,),
                        "ioc_sha256": (mismatch.ioc_sha256,),
                        "map_sha256": (mismatch.map_sha256,),
                        "native_netlist_sha256": (mismatch.netlist_sha256,),
                    },
                )
            )
    return tuple(found)

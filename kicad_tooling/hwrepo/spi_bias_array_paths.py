"""Source-bound resistor-array channel evidence for SPI bias contracts."""

from __future__ import annotations

from dataclasses import dataclass

from .models import NetlistContract
from .resistor_array_paths import (
    ResistorArrayNetlistEvidence,
    resistor_array_channel_issue,
    resistor_array_component_issues,
)
from .spi_models import SpiAnalysis


@dataclass(frozen=True, slots=True)
class SpiBiasArrayChannelEvidence:
    """Native identity and pin-map result for one authored array channel."""

    reference: str
    channel_id: str
    signal_net: str
    rail_net: str
    resistance_ohms: float
    issues: tuple[str, ...]

    @property
    def matches(self) -> bool:
        return not self.issues


def spi_bias_array_channel_evidence(
    analysis: SpiAnalysis,
    observed: NetlistContract,
) -> tuple[SpiBiasArrayChannelEvidence, ...]:
    """Compare every authored array channel with exact native component evidence."""
    evidence = ResistorArrayNetlistEvidence.from_netlist(observed)
    results: list[SpiBiasArrayChannelEvidence] = []
    for array in analysis.chip_select_pullup_arrays:
        component_issues = resistor_array_component_issues(
            evidence,
            reference=array.reference,
            expected_symbol=array.expected_symbol,
            expected_footprint=array.expected_footprint,
            expected_value=array.expected_value,
            expected_part_id=array.expected_part_id,
            channel_pins=tuple(
                (channel.signal_pin, channel.rail_pin) for channel in array.channels
            ),
            unmapped_pin_reasons=array.unmapped_pin_reasons,
            component_kind="mapped SPI chip-select pull-up",
        )
        for channel in array.channels:
            channel_issue = resistor_array_channel_issue(
                evidence,
                reference=array.reference,
                channel_id=channel.id,
                pin_a=channel.signal_pin,
                pin_b=channel.rail_pin,
                net_a=channel.signal_net,
                net_b=channel.rail_net,
            )
            issues = (*component_issues, *((channel_issue,) if channel_issue else ()))
            results.append(
                SpiBiasArrayChannelEvidence(
                    reference=array.reference,
                    channel_id=channel.id,
                    signal_net=channel.signal_net,
                    rail_net=channel.rail_net,
                    resistance_ohms=channel.resistance_ohms,
                    issues=issues,
                )
            )
    return tuple(results)


def spi_bias_array_checks(
    analysis: SpiAnalysis,
    observed: NetlistContract,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return stable check IDs and issues for the mapped array channels."""
    return tuple(
        (
            f"spi/bias-array/{item.reference}/{item.channel_id}",
            item.issues,
        )
        for item in spi_bias_array_channel_evidence(analysis, observed)
    )

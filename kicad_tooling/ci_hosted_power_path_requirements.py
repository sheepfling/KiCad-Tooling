"""Synthetic source-to-load maps for hosted power-path fixture cases."""

from __future__ import annotations

from .hwrepo.models import (
    PowerPathElementRequirement,
    PowerPathEndpointRequirement,
    PowerPathMap,
    PowerPathRequirement,
)


def power_path_requirement_map() -> PowerPathMap:
    path_map = PowerPathMap(
        basis="Synthetic reviewed source-to-load requirement",
        paths=(
            PowerPathRequirement(
                id="source-through-bead-to-load",
                basis="Synthetic schematic requires the fitted ferrite bead in the path",
                start=PowerPathEndpointRequirement(
                    reference="U1",
                    pin="U1.1",
                    symbol="Synthetic:PowerSource",
                    footprint="Synthetic:PowerSource",
                    net="VIN",
                ),
                end=PowerPathEndpointRequirement(
                    reference="U2",
                    pin="U2.1",
                    symbol="Synthetic:PowerLoad",
                    footprint="Synthetic:PowerLoad",
                    net="VLOAD",
                ),
                elements=(
                    PowerPathElementRequirement(
                        reference="FB1",
                        symbol="Device:FerriteBead",
                        footprint="Synthetic:0603",
                        side_a_pin="FB1.1",
                        side_b_pin="FB1.2",
                        side_a_net="VIN",
                        side_b_net="VLOAD",
                    ),
                ),
            ),
        ),
    )

    return path_map

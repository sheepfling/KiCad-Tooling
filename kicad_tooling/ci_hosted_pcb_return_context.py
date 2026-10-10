"""Typed fixture and case contexts for native PCB return-path checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeAlias

from .hwrepo.models import ElectricalCheck, ProjectConfig
from .hwrepo.pcb_connectivity_observations import PcbPadConnectivityObservation
from .hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot


class PcbReturnLog(Protocol):
    directory: Path

    def event(self, stage: str, status: str, **details: str | float) -> None: ...


PcbReturnFixtureCase: TypeAlias = tuple[
    str, str, str, bool, int | None, tuple[int, ...] | None, bool | None, bool | None
]


@dataclass(slots=True)
class PcbReturnFixtureContext:
    root: Path
    project: str
    config: ProjectConfig
    fixture_root: Path
    fixtures: tuple[PcbReturnFixtureCase, ...]
    log: PcbReturnLog


@dataclass(slots=True)
class PcbReturnCaseEvidence:
    fixture_id: str
    scenario: str
    expected_connected: bool
    expected_islands: int | None
    expected_island_indices: tuple[int, ...] | None
    expected_tie_dnp: bool | None
    expected_isolated: bool | None
    root: Path
    config: ProjectConfig
    fixture_config: ProjectConfig
    scratch: Path
    snapshot: PcbConnectivitySnapshot
    first: PcbPadConnectivityObservation | None
    second: PcbPadConnectivityObservation | None
    checks: tuple[ElectricalCheck, ...]
    connectivity_check: ElectricalCheck | None
    observed_connected: bool
    is_via_fixture: bool
    failures: list[str]
    via_identity_repeatable: bool


def prepare_pcb_return_fixture_context(
    root: Path, project: str, image: str, log: PcbReturnLog
) -> PcbReturnFixtureContext:
    """Prepare source-bound return-path fixture cases."""
    from .hwrepo.electrical import selected_config

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"PCB return-path native fixtures do not cover KiCad {config.kicad_version}"
        )
    fixture_root = Path(__file__).resolve().parent / "hwrepo/fixtures"
    fixtures = (
        (
            "alternate-layer-via",
            "pcb-return-alternate-layer-via.kicad_pcb",
            "direct",
            True,
            None,
            None,
            None,
            None,
        ),
        (
            "alternate-layer-open",
            "pcb-return-alternate-layer-open.kicad_pcb",
            "direct",
            False,
            None,
            None,
            None,
            None,
        ),
        (
            "zone-connected",
            "pcb-return-zone-connected.kicad_pcb",
            "direct",
            True,
            1,
            (0, 0),
            None,
            None,
        ),
        (
            "unstitched-planes",
            "pcb-return-unstitched-planes.kicad_pcb",
            "direct",
            False,
            None,
            None,
            None,
            None,
        ),
        (
            "stitched-planes",
            "pcb-return-stitched-planes.kicad_pcb",
            "direct",
            True,
            None,
            None,
            None,
            None,
        ),
        (
            "zone-unanchored-island",
            "pcb-return-zone-unanchored-island.kicad_pcb",
            "direct",
            True,
            2,
            None,
            None,
            None,
        ),
        ("zone-split", "pcb-return-zone-split.kicad_pcb", "direct", False, 2, (0, 1), None, None),
        (
            "zone-through-hole-split",
            "pcb-return-zone-through-hole-split.kicad_pcb",
            "direct",
            False,
            2,
            (0, 1),
            None,
            None,
        ),
        (
            "net-tie-connected",
            "pcb-return-net-tie-connected.kicad_pcb",
            "bond",
            True,
            None,
            None,
            False,
            None,
        ),
        ("net-tie-dnp", "pcb-return-net-tie-dnp.kicad_pcb", "bond", False, None, None, True, None),
        (
            "isolation-open",
            "pcb-return-isolation-open.kicad_pcb",
            "isolation",
            True,
            None,
            None,
            None,
            True,
        ),
        (
            "isolation-bridged",
            "pcb-return-isolation-bridged.kicad_pcb",
            "isolation",
            True,
            None,
            None,
            False,
            False,
        ),
    )
    return PcbReturnFixtureContext(
        root=root,
        project=project,
        config=config,
        fixture_root=fixture_root,
        fixtures=fixtures,
        log=log,
    )

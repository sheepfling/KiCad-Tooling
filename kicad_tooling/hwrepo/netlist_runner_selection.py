"""Select the shared netlist runner from an operation's explicit mode."""

from __future__ import annotations

from typing import Literal

from .contract_coach import (
    AutoNetlistRunner,
    ContainerNetlistRunner,
    LocalNetlistRunner,
    NetlistRunner,
)


def select_netlist_runner(
    runner_mode: Literal["auto", "local", "container"], cli: str
) -> NetlistRunner:
    """Create the runner selected by an electrical or purchasing operation."""
    if runner_mode == "local":
        return LocalNetlistRunner(cli)
    if runner_mode == "container":
        return ContainerNetlistRunner()
    return AutoNetlistRunner(cli)

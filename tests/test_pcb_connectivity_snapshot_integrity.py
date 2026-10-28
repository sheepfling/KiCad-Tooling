"""Reject internally inconsistent native PCB pad-connectivity evidence."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.design_lint_fixtures.pcb_return_paths import pad, snapshot

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]


def test_connected_pad_component_cannot_mix_native_net_assignments() -> None:
    with pytest.raises(ValidationError, match="connected pads have different nets"):
        snapshot(
            (
                pad("J1.7", "RETURN_A", connected=("J1.7", "J2.7")),
                pad("J2.7", "RETURN_B", connected=("J1.7", "J2.7")),
            )
        )


def test_connected_pad_component_membership_must_be_reciprocal() -> None:
    with pytest.raises(ValidationError, match="membership must be symmetric"):
        snapshot(
            (
                pad("J1.7", connected=("J1.7", "J2.7")),
                pad("J2.7"),
            )
        )


def test_connected_pad_component_accepts_case_insensitive_references() -> None:
    observed = snapshot(
        (
            pad("j1.7", connected=("J1.7", "j2.7")),
            pad("J2.7", connected=("j1.7", "J2.7")),
        )
    )

    assert tuple(item.pad for item in observed.pads) == ("j1.7", "J2.7")

"""Named identity context and evidence projection for component-peer rules."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.component_peer_pin_identity import (
    ComponentPeerPinIdentityContext,
    component_peer_pin_identity_context,
)
from kicad_tooling.hwrepo.component_peer_pin_scan import PeerPinAssignmentOutlier

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.architecture]


def test_part_id_context_keeps_identity_and_message_fields_named() -> None:
    group = PeerPinAssignmentOutlier(
        symbol="Synthetic:Module",
        pin_number="7",
        electrical_type="input",
        assignments={},
        peer_identity_basis="part_id",
        peer_identity="MODULE-7",
        peer_symbols=("Synthetic:ModuleA", "Synthetic:ModuleB"),
    )

    context = component_peer_pin_identity_context(group)

    assert isinstance(context, ComponentPeerPinIdentityContext)
    assert context.subject_identity == "PART_ID MODULE-7"
    assert context.identity_description == (
        "the same native PART_ID 'MODULE-7' across distinct native symbols"
    )
    assert context.independent_net_note == (
        "a shared PART_ID does not require peer pins to share a net"
    )
    assert context.evidence == {
        "peer_group_basis": ("part_id",),
        "peer_group_identity": ("MODULE-7",),
        "peer_group_symbols": ("Synthetic:ModuleA", "Synthetic:ModuleB"),
    }


def test_exact_symbol_context_projects_the_legacy_symbol_field() -> None:
    group = PeerPinAssignmentOutlier(
        symbol="Synthetic:Module",
        pin_number="7",
        electrical_type="input",
        assignments={},
        peer_identity_basis="exact_symbol",
        peer_identity="Synthetic:Module",
        peer_symbols=("Synthetic:Module",),
    )

    context = component_peer_pin_identity_context(group)

    assert context.subject_identity == "Synthetic:Module"
    assert context.evidence == {
        "peer_group_basis": ("exact_symbol",),
        "peer_group_identity": ("Synthetic:Module",),
        "peer_group_symbols": ("Synthetic:Module",),
        "symbol": ("Synthetic:Module",),
    }

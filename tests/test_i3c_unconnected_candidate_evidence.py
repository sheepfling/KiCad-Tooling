"""I3C one-sided-open findings retain their exact scan records."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_i3c_unconnected_candidate_evidence import (
    I3cUnconnectedCandidate,
    I3cUnconnectedFindingEvidence,
    project_i3c_unconnected_evidence,
)
from kicad_tooling.hwrepo.i3c_unconnected_pins import UnconnectedI3cSignalPin


def test_i3c_projection_preserves_the_open_pin_and_assigned_peer() -> None:
    source = I3cUnconnectedFindingEvidence(
        UnconnectedI3cSignalPin(
            pin="U1.2",
            function="SDA1",
            role="SDA",
            channel="1",
            paired_pin="U1.3",
            paired_function="SCL1",
            paired_net="I3C_SCL",
        )
    )
    candidate = I3cUnconnectedCandidate.from_source_evidence(
        source,
        subject="U1.2: SDA1",
        message="Review the partial I3C path.",
    )

    assert dict(project_i3c_unconnected_evidence(source).evidence) == {
        "U1.2": (),
        "function": ("SDA1",),
        "i3c_role": ("SDA",),
        "i3c_channel": ("1",),
        "paired_pin": ("U1.3",),
        "paired_function": ("SCL1",),
        "paired_net": ("I3C_SCL",),
    }
    assert candidate.source_evidence is source


def test_i3c_projection_preserves_the_unindexed_channel_fallback() -> None:
    source = I3cUnconnectedFindingEvidence(
        UnconnectedI3cSignalPin(
            pin="U2.4",
            function="SCL",
            role="SCL",
            channel=None,
            paired_pin="U2.5",
            paired_function="SDA",
            paired_net="I3C_SDA",
        )
    )

    assert project_i3c_unconnected_evidence(source).evidence["i3c_channel"] == ("unindexed",)


def test_i3c_candidate_rejects_a_projection_mismatch() -> None:
    source = I3cUnconnectedFindingEvidence(
        UnconnectedI3cSignalPin("U1.2", "SDA1", "SDA", "1", "U1.3", "SCL1", "I3C_SCL")
    )

    with pytest.raises(ValueError, match="typed source projection"):
        I3cUnconnectedCandidate(
            rule_id="bus.i3c_unconnected_pin",
            subject="review",
            message="inspect",
            evidence={"U1.2": (), "i3c_role": ("SCL",)},
            source_evidence=source,
        )

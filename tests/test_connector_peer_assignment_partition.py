"""Source-reviewed connector scopes are explicit, read-only records."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_comparison_scope_types import ConnectorComparisonScope
from kicad_tooling.hwrepo.connector_identity import (
    PeerAssignmentPartition,
    partition_peer_assignments,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.architecture]


def test_missing_scope_returns_one_named_unscoped_partition() -> None:
    assignments = {"J1.1": ("GND_A",), "J2.1": ("GND_B",)}

    (partition,) = partition_peer_assignments(assignments, None)

    assert isinstance(partition, PeerAssignmentPartition)
    assert partition.peer_assignment_group is None
    assert dict(partition.assignments_by_pin) == assignments
    assert partition.peer_assignment_basis == ()


def test_current_scope_keeps_group_assignments_and_review_basis_together() -> None:
    assignments = {
        "J1.1": ("GND_A",),
        "J2.1": ("GND_B",),
        "J3.1": ("SDA",),
    }
    groups = {
        "J1": ConnectorComparisonScope("Returns", "Reviewed J1 in return group"),
        "J2": ConnectorComparisonScope("Returns", "Reviewed J2 in return group"),
        "J3": ConnectorComparisonScope("Signals", "Reviewed J3 in signal group"),
    }

    partitions = partition_peer_assignments(assignments, groups)

    assert tuple(
        (
            item.peer_assignment_group,
            dict(item.assignments_by_pin),
            item.peer_assignment_basis,
        )
        for item in partitions
    ) == (
        (
            "Returns",
            {"J1.1": ("GND_A",), "J2.1": ("GND_B",)},
            (
                "J1: Returns; Reviewed J1 in return group",
                "J2: Returns; Reviewed J2 in return group",
            ),
        ),
        (
            "Signals",
            {"J3.1": ("SDA",)},
            ("J3: Signals; Reviewed J3 in signal group",),
        ),
    )
    with pytest.raises(TypeError):
        partitions[0].assignments_by_pin["J1.1"] = ("OTHER",)  # type: ignore[index]


def test_incomplete_scope_does_not_return_partially_reviewed_groups() -> None:
    assignments = {"J1.1": ("GND_A",), "J2.1": ("GND_B",)}
    groups = {"J1": ConnectorComparisonScope("Returns", "Reviewed J1 in return group")}

    (partition,) = partition_peer_assignments(assignments, groups)

    assert partition.peer_assignment_group is None
    assert dict(partition.assignments_by_pin) == assignments
    assert partition.peer_assignment_basis == ()

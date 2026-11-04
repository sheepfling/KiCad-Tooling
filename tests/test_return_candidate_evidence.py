"""Return-domain projections keep report fields tied to typed scanner records."""

from __future__ import annotations

from collections.abc import MutableMapping
from operator import setitem
from typing import cast

import pytest

from kicad_tooling.hwrepo.connector_return_pins import ConnectorReturnCoverage
from kicad_tooling.hwrepo.design_lint_return_candidate_evidence import (
    ConnectorNoReturnEvidence,
    NumberedReturnEvidence,
    ReturnCandidateSource,
    ReturnDomainCandidate,
    UnroledReturnLabelsEvidence,
    project_return_candidate_evidence,
)
from kicad_tooling.hwrepo.return_net_models import ReturnNetGroup


@pytest.mark.parametrize(
    ("source", "rule_id", "evidence"),
    [
        pytest.param(
            ConnectorNoReturnEvidence(
                ConnectorReturnCoverage(
                    reference="J1",
                    symbol="Connector:MultiPin",
                    connected_pin_count=3,
                    pins={"J1.1": ("SDA",), "J1.2": ("SCL",)},
                )
            ),
            "connector.no_connected_return",
            {"J1.1": ("SDA",), "J1.2": ("SCL",)},
            id="connector-without-return-role",
        ),
        pytest.param(
            ConnectorNoReturnEvidence(
                ConnectorReturnCoverage(
                    reference="J1",
                    symbol="Connector:MultiPin",
                    connected_pin_count=3,
                    pins={"J1.1": ("SDA",)},
                ),
                return_named_net_candidates=("J1.1: GND_SIGNAL",),
            ),
            "connector.no_connected_return",
            {
                "J1.1": ("SDA",),
                "return_named_net_candidates": ("J1.1: GND_SIGNAL",),
            },
            id="connector-return-label-needs-role",
        ),
        pytest.param(
            NumberedReturnEvidence(
                ReturnNetGroup(
                    stem="GNDA",
                    nets={"GNDA1": ("J1.1",), "GNDA2": ("J2.1",)},
                )
            ),
            "net.numbered_returns",
            {"GNDA1": ("J1.1",), "GNDA2": ("J2.1",)},
            id="numbered-returns",
        ),
        pytest.param(
            UnroledReturnLabelsEvidence(
                ReturnNetGroup(
                    stem="return-like net labels without explicit pin roles",
                    nets={"GNDA": ("J1.1",), "GNDD": ("J2.1",)},
                )
            ),
            "net.return_labels_without_pin_roles",
            {"GNDA": ("J1.1",), "GNDD": ("J2.1",)},
            id="unroled-return-labels",
        ),
    ],
)
def test_return_projection_preserves_the_typed_source_and_report_fields(
    source: ReturnCandidateSource,
    rule_id: str,
    evidence: dict[str, tuple[str, ...]],
) -> None:
    projection = project_return_candidate_evidence(source)
    candidate = ReturnDomainCandidate.from_source_evidence(
        source,
        subject="review return domain",
        message="inspect the interface",
    )

    assert projection.rule_id == rule_id
    assert dict(projection.evidence) == evidence
    assert candidate.source_evidence is source
    assert candidate.rule_id == rule_id
    assert dict(candidate.evidence) == evidence


def test_return_candidate_rejects_a_report_projection_mismatch() -> None:
    source = NumberedReturnEvidence(
        ReturnNetGroup(stem="GNDA", nets={"GNDA1": ("J1.1",), "GNDA2": ("J2.1",)})
    )

    with pytest.raises(ValueError, match="typed source projection"):
        ReturnDomainCandidate(
            rule_id="net.numbered_returns",
            subject="review",
            message="inspect",
            evidence={"GNDA1": ("OTHER",)},
            source_evidence=source,
        )


def test_connector_return_scan_copies_and_freezes_its_pin_map() -> None:
    input_map = {"J1.1": ("SDA",)}
    source = ConnectorReturnCoverage("J1", "Connector:MultiPin", 3, input_map)
    input_map["J1.1"] = ("OTHER",)

    assert source.pins == {"J1.1": ("SDA",)}
    with pytest.raises(TypeError):
        setitem(cast(MutableMapping[str, tuple[str, ...]], source.pins), "J1.2", ("SCL",))


def test_return_net_group_copies_and_freezes_its_net_map() -> None:
    input_map = {"GNDA1": ("J1.1",)}
    source = ReturnNetGroup(stem="GNDA", nets=input_map)
    input_map["GNDA1"] = ("J2.1",)

    assert source.nets == {"GNDA1": ("J1.1",)}
    assert source.model_dump_json() == '{"stem":"GNDA","nets":{"GNDA1":["J1.1"]}}'
    with pytest.raises(TypeError):
        setitem(cast(MutableMapping[str, tuple[str, ...]], source.nets), "GNDA2", ("J2.1",))

"""Authored return-distribution candidates retain report and entry evidence."""

from __future__ import annotations

from operator import setitem
from typing import Literal

import pytest

from kicad_tooling.hwrepo.connector_return_distribution_models import (
    ConnectorReturnDistributionCoverageReport,
    ConnectorReturnDistributionEntry,
)
from kicad_tooling.hwrepo.design_lint_return_distribution_candidate_evidence import (
    ConnectorReturnDistributionCandidate,
    ConnectorReturnDistributionFindingEvidence,
    project_return_distribution_evidence,
)
from kicad_tooling.hwrepo.design_lint_return_distribution_candidates import (
    return_distribution_candidates,
)


def _entry(
    *,
    status: Literal["COMPLETE", "BELOW_SCOPE", "OUT_OF_RANGE", "INCOMPLETE"] = "OUT_OF_RANGE",
    signal_pin_map: dict[str, str] | None = None,
) -> ConnectorReturnDistributionEntry:
    return ConnectorReturnDistributionEntry(
        id="external-link",
        connector_reference="J1",
        interface_id="usb-port",
        status=status,
        signal_pin_map=({"1": "J1.1", "2": "J1.2"} if signal_pin_map is None else signal_pin_map),
        return_pin_map={"3": "J1.3"},
        supply_pin_map={"4": "J1.4"},
        shield_pin_map={"5": "J1.5"},
        other_pin_map={"6": "J1.6"},
        unclassified_pin_map={"7": "J1.7"},
        signal_pin_count=2,
        return_pin_count=1,
        required_return_pin_count=2,
        signal_to_return_ratio=2.0,
        minimum_signal_pin_count=2,
        maximum_signal_to_return_ratio=1.0,
        basis="Reviewed external interface contact budget",
        issues=("required return contact missing",),
    )


def _coverage(
    entry: ConnectorReturnDistributionEntry,
) -> ConnectorReturnDistributionCoverageReport:
    return ConnectorReturnDistributionCoverageReport(
        status="COMPLETE",
        netlist_sha256="a" * 64,
        interface_catalog_sha256="b" * 64,
        entries=(entry,),
    )


def test_projection_preserves_existing_evidence_and_retains_source_report() -> None:
    entry = _entry()
    coverage = _coverage(entry)
    source = ConnectorReturnDistributionFindingEvidence(coverage, entry)
    projection = project_return_distribution_evidence(source)
    candidate = ConnectorReturnDistributionCandidate.from_source_evidence(
        source,
        subject="J1: reviewed return-contact distribution",
        message="Review the pin allocation.",
    )

    assert projection.rule_id == "connector.return_distribution"
    assert dict(projection.evidence) == {
        "profile": ("external-link",),
        "connector": ("J1",),
        "interface": ("usb-port",),
        "signal_contact_count": ("2",),
        "signal_pins": ("interface 1 -> J1.1", "interface 2 -> J1.2"),
        "return_contact_count": ("1",),
        "return_pins": ("interface 3 -> J1.3",),
        "supply_pins_excluded": ("interface 4 -> J1.4",),
        "shield_pins_excluded": ("interface 5 -> J1.5",),
        "other_pins_excluded": ("interface 6 -> J1.6",),
        "unclassified_pins": ("interface 7 -> J1.7",),
        "required_return_contact_count": ("2",),
        "signal_to_return_ratio": ("2 signals per return",),
        "minimum_signal_pin_count": ("2",),
        "maximum_signal_to_return_ratio": ("1",),
        "basis": ("Reviewed external interface contact budget",),
        "issues": ("required return contact missing",),
    }
    assert candidate.source_evidence.coverage is coverage
    assert candidate.source_evidence.entry is entry
    assert candidate.evidence == projection.evidence


def test_unbound_connector_and_undefined_ratio_keep_the_existing_projection() -> None:
    entry = _entry(status="INCOMPLETE", signal_pin_map={})
    entry = entry.model_copy(
        update={"connector_reference": None, "return_pin_count": 0, "signal_to_return_ratio": None}
    )
    coverage = ConnectorReturnDistributionCoverageReport(
        status="INCOMPLETE",
        netlist_sha256="a" * 64,
        interface_catalog_sha256="b" * 64,
        entries=(entry,),
    )

    evidence = project_return_distribution_evidence(
        ConnectorReturnDistributionFindingEvidence(coverage, entry)
    ).evidence

    assert evidence["connector"] == ("<no bound connector>",)
    assert evidence["signal_pins"] == ()
    assert evidence["signal_to_return_ratio"] == ("undefined (no return contacts)",)


def test_candidate_source_pin_maps_are_immutable_and_still_serialize_as_mappings() -> None:
    signal_pins = {"1": "J1.1"}
    entry = _entry(signal_pin_map=signal_pins)
    coverage = _coverage(entry)
    signal_pins["1"] = "J9.9"

    assert entry.signal_pin_map == {"1": "J1.1"}
    model_dump = entry.model_dump(mode="python")
    json_dump = entry.model_dump_json()
    for field_name in (
        "signal_pin_map",
        "return_pin_map",
        "supply_pin_map",
        "shield_pin_map",
        "other_pin_map",
        "unclassified_pin_map",
    ):
        source_map = getattr(entry, field_name)
        with pytest.raises(TypeError):
            setitem(source_map, "99", "J1.99")
        assert isinstance(model_dump[field_name], dict)
        assert f'"{field_name}":{{' in json_dump
    assert '"entries":[{"id":"external-link"' in coverage.model_dump_json()


def test_finding_source_requires_the_exact_entry_from_its_coverage_report() -> None:
    coverage_entry = _entry()
    other_entry = _entry()
    coverage = _coverage(coverage_entry)
    assert other_entry == coverage_entry
    assert other_entry is not coverage_entry

    with pytest.raises(ValueError, match="must belong to its source coverage report"):
        ConnectorReturnDistributionFindingEvidence(coverage, other_entry)


def test_finding_source_requires_scanned_coverage_and_an_open_entry() -> None:
    entry = _entry()
    blocked_coverage = ConnectorReturnDistributionCoverageReport(
        status="BLOCKED",
        entries=(entry,),
        issue="Synthetic source mismatch",
    )
    with pytest.raises(ValueError, match="requires scanned coverage"):
        ConnectorReturnDistributionFindingEvidence(blocked_coverage, entry)

    complete_entry = _entry(status="COMPLETE")
    with pytest.raises(ValueError, match="requires an open entry"):
        ConnectorReturnDistributionFindingEvidence(_coverage(complete_entry), complete_entry)


def test_blocked_or_unrequested_coverage_does_not_create_candidates() -> None:
    entry = _entry()
    blocked = ConnectorReturnDistributionCoverageReport(
        status="BLOCKED",
        entries=(entry,),
        issue="Synthetic source mismatch",
    )
    unrequested = ConnectorReturnDistributionCoverageReport(entries=(entry,))

    assert return_distribution_candidates(blocked) == ()
    assert return_distribution_candidates(unrequested) == ()


def test_candidate_rejects_evidence_that_differs_from_its_source() -> None:
    entry = _entry()
    source = ConnectorReturnDistributionFindingEvidence(_coverage(entry), entry)

    with pytest.raises(ValueError, match="typed source projection"):
        ConnectorReturnDistributionCandidate(
            rule_id="connector.return_distribution",
            subject="review",
            message="inspect",
            evidence={"profile": ("wrong",)},
            source_evidence=source,
        )

"""Keep typed I2C source records authoritative behind stable finding projections."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_i2c_pullup_candidate_evidence import (
    I2cPullupCandidate,
    I2cPullupCandidateEvidence,
    project_i2c_pullup_evidence,
)
from kicad_tooling.hwrepo.design_lint_i2c_pullup_candidates import (
    i2c_pullup_theme_candidates,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.i2c_pullup_heuristics import (
    i2c_buses_with_low_equivalent_pullup_resistance,
    i2c_buses_with_multiple_pullup_rail_families,
    i2c_buses_without_local_pullups,
    i2c_pullup_heuristic_coverage,
)
from kicad_tooling.hwrepo.i2c_pullup_inputs import I2cPullupSnifferInput
from kicad_tooling.hwrepo.i2c_pullup_models import I2cPullupHeuristicCoverage
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures import (
    i2c_netlist,
    i2c_netlist_with_parallel_sda,
    i2c_netlist_with_pullup_rails,
)
from tests.electrical_i2c_support import (
    i2c_series_pullup_netlist,
    i2c_series_pullup_requirement,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _assert_typed_candidate_projection(
    observed: NetlistContract,
    coverage: I2cPullupHeuristicCoverage,
    source: I2cPullupCandidateEvidence,
) -> None:
    projection = project_i2c_pullup_evidence(source)
    candidate = next(
        item
        for item in i2c_pullup_theme_candidates(
            I2cPullupSnifferInput(observed=observed, coverage=coverage)
        )
        if item.rule_id == projection.rule_id
    )

    assert isinstance(candidate, I2cPullupCandidate)
    assert candidate.source_evidence == source
    assert candidate.evidence == projection.evidence
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)


def test_each_i2c_pullup_rule_retains_typed_source_and_stable_wire_evidence() -> None:
    missing_netlist = i2c_netlist()
    (missing_source,) = i2c_buses_without_local_pullups(missing_netlist)
    _assert_typed_candidate_projection(
        missing_netlist,
        I2cPullupHeuristicCoverage(status="NOT_CONFIGURED"),
        missing_source,
    )

    low_resistance_netlist = i2c_netlist_with_parallel_sda()
    (low_resistance_source,) = i2c_buses_with_low_equivalent_pullup_resistance(
        low_resistance_netlist
    )
    _assert_typed_candidate_projection(
        low_resistance_netlist,
        I2cPullupHeuristicCoverage(status="NOT_CONFIGURED"),
        low_resistance_source,
    )

    rail_family_netlist = i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",))
    (rail_family_source,) = i2c_buses_with_multiple_pullup_rail_families(rail_family_netlist)
    _assert_typed_candidate_projection(
        rail_family_netlist,
        I2cPullupHeuristicCoverage(status="NOT_CONFIGURED"),
        rail_family_source,
    )

    voltage_netlist = i2c_series_pullup_netlist()
    voltage_coverage = i2c_pullup_heuristic_coverage(
        voltage_netlist,
        netlist_sha256="a" * 64,
        source_path="projects/synthetic/electrical.json",
        source_sha256="b" * 64,
        state="required",
        spec=i2c_series_pullup_requirement(),
    )
    voltage_source = next(
        entry for entry in voltage_coverage.voltage_entries if entry.status == "OPEN"
    )
    _assert_typed_candidate_projection(voltage_netlist, voltage_coverage, voltage_source)


def test_i2c_candidate_rejects_a_wire_projection_that_disagrees_with_source() -> None:
    (source,) = i2c_buses_with_low_equivalent_pullup_resistance(i2c_netlist_with_parallel_sda())
    projection = project_i2c_pullup_evidence(source)
    wrong_evidence = dict(projection.evidence)
    wrong_evidence["SDA"] = ("OTHER_NET",)

    with pytest.raises(ValueError, match="must match its typed source projection"):
        I2cPullupCandidate(
            rule_id=projection.rule_id,
            subject="Synthetic I2C bus",
            message="Synthetic projection consistency check",
            evidence=wrong_evidence,
            source_evidence=source,
        )

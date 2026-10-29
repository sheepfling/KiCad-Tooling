"""Catalog validation after every design-lint candidate source has run."""

from __future__ import annotations

from typing import cast

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo import design_lint_evaluation_candidates
from kicad_tooling.hwrepo.design_lint import candidates, evaluate, fingerprint, text_report
from kicad_tooling.hwrepo.design_lint_pcb_component_inventory_candidates import (
    pcb_component_inventory_candidates,
)
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.design_lint_rule_types import DesignLintRuleId
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy
from tests.design_lint_fixtures import coach, i2c_netlist, observed
from tests.design_lint_fixtures.pcb_component_inventory import (
    coach as pcb_coach,
)
from tests.design_lint_fixtures.pcb_component_inventory import (
    complete_report,
    snapshot,
)
from tests.design_lint_fixtures.pcb_component_inventory import (
    netlist as pcb_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint]


@pytest.mark.parametrize("source", ("theme", "native_sidecar"))
def test_appended_candidate_sources_require_an_active_catalog_rule(
    monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    unknown = Candidate(
        rule_id=cast(DesignLintRuleId, "power.uncatalogued_extension"),
        subject="synthetic uncatalogued candidate",
        message="This extension has no active catalog entry.",
        evidence={},
    )
    native_candidates = ()
    if source == "theme":
        monkeypatch.setattr(
            design_lint_evaluation_candidates,
            "regulator_required_passive_candidates",
            lambda _observed, _map: (unknown,),
        )
    else:
        native_candidates = (unknown,)

    with pytest.raises(ValueError, match="candidates emit rules absent from the active catalog"):
        evaluate(
            "synthetic-candidate-catalog",
            coach(observed()),
            DesignLintPolicy(),
            pcb_native_drc_candidates=native_candidates,
        )


@pytest.mark.parametrize("ignored", (False, True))
def test_duplicate_candidate_identity_blocks_disposition(ignored: bool) -> None:
    netlist = i2c_netlist(pullups=())
    duplicate = next(
        item for item in candidates(netlist) if item.rule_id == "bus.i2c_missing_pullup"
    )
    key = fingerprint(duplicate)
    policy = DesignLintPolicy(
        ignores=(
            (DesignLintIgnore(rule_id=duplicate.rule_id, fingerprint=key, reason="Reviewed bus"),)
            if ignored
            else ()
        )
    )
    report = evaluate(
        "duplicate-candidate", coach(netlist), policy, pcb_native_drc_candidates=(duplicate,)
    )
    assert report.status == "BLOCKED"
    assert key in report.issues[0]
    assert "Multiple candidates share fingerprint" in report.issues[0]
    assert not report.findings
    assert "Findings: unavailable or incomplete because evaluation is blocked" in text_report(
        report
    )
    assert DesignLintReport.model_validate_json(report.model_dump_json()) == report


def test_duplicate_disposition_retains_peer_and_mapped_coverage() -> None:
    netlist = i2c_netlist(pullups=())
    normal = evaluate("duplicate-candidate", coach(netlist), DesignLintPolicy())
    duplicate = next(
        item for item in candidates(netlist) if item.rule_id == "bus.i2c_missing_pullup"
    )
    report = evaluate(
        "duplicate-candidate",
        coach(netlist),
        DesignLintPolicy(),
        pcb_native_drc_candidates=(duplicate,),
    )
    assert report.status == "BLOCKED"
    assert normal.i2c_peer_reference_coverage is not None
    assert normal.mapped_check_runs
    for name in (
        "digital_peer_voltage_coverage",
        "usb_peer_reference_coverage",
        "serial_peer_reference_coverage",
        "i2c_peer_reference_coverage",
        "spi_peer_reference_coverage",
        "can_peer_reference_coverage",
        "rs485_peer_reference_coverage",
        "mapped_check_runs",
    ):
        assert getattr(report, name) == getattr(normal, name)
    peer = report.i2c_peer_reference_coverage
    assert peer is not None
    mismatched_peer = type(peer).model_validate({**peer.model_dump(), "netlist_sha256": "f" * 64})
    with pytest.raises(ValidationError, match="I2C peer-reference coverage must use"):
        DesignLintReport.model_validate(
            {**report.model_dump(), "i2c_peer_reference_coverage": mismatched_peer}
        )


def test_empty_blocked_report_is_not_presented_as_a_complete_finding_list() -> None:
    blocked = DesignLintReport(
        status="BLOCKED", project_id="board", issues=("Native evidence unavailable",)
    )
    complete = DesignLintReport(status="PASS", project_id="board")
    phrase = "Findings: unavailable or incomplete because evaluation is blocked"
    assert phrase in text_report(blocked)
    assert phrase not in text_report(complete)


def test_duplicate_inventory_candidate_preserves_blocked_evidence() -> None:
    netlist = pcb_netlist(components={"U1": "Package_SO:SOIC-8"})
    coverage = complete_report(
        netlist, snapshot("U1", footprint_by_reference={"U1": "Package_TSSOP:TSSOP-8"})
    )
    (candidate,) = pcb_component_inventory_candidates(coverage)
    report = evaluate(
        "duplicate-inventory",
        pcb_coach(netlist),
        DesignLintPolicy(),
        pcb_component_inventory_coverage=coverage,
        pcb_native_drc_candidates=(candidate,),
    )
    assert report.status == "BLOCKED"
    assert report.pcb_component_inventory == coverage
    assert "Multiple candidates share fingerprint" in report.issues[0]
    with pytest.raises(ValidationError, match="must match its comparison rows"):
        DesignLintReport.model_validate({**report.model_dump(), "status": "PASS"})
    with pytest.raises(ValidationError, match="must use this report's native netlist"):
        DesignLintReport.model_validate({**report.model_dump(), "netlist_sha256": "f" * 64})


def test_wrong_ignore_with_inventory_preserves_blocked_evidence() -> None:
    netlist = pcb_netlist(components={"U1": "Package_SO:SOIC-8"})
    coverage = complete_report(
        netlist, snapshot("U1", footprint_by_reference={"U1": "Package_TSSOP:TSSOP-8"})
    )
    (candidate,) = pcb_component_inventory_candidates(coverage)
    policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id="bus.i2c_missing_pullup",
                fingerprint=fingerprint(candidate),
                reason="Wrong rule",
            ),
        )
    )
    report = evaluate(
        "wrong-ignore", pcb_coach(netlist), policy, pcb_component_inventory_coverage=coverage
    )
    assert report.status == "BLOCKED"
    assert report.pcb_component_inventory == coverage
    assert "names the wrong rule" in report.issues[0]

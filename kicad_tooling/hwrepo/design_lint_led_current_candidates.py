"""Project-mapped LED current-window findings from source-bound netlists."""

from __future__ import annotations

from .design_lint_led_current_candidate_evidence import (
    LedCurrentRangeCandidate,
    LedCurrentRangeFindingEvidence,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .led_current_models import LedCurrentMap
from .led_current_range import scan_led_current_map
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "component.mapped_led_current_range_mismatch"


def led_current_range_candidates(
    observed: NetlistContract,
    led_map: LedCurrentMap | None,
    netlist_sha256: str | None,
) -> tuple[Candidate, ...]:
    """Review only explicitly mapped LED paths with incomplete or out-of-range evidence."""
    if led_map is None:
        return ()
    entries = scan_led_current_map(led_map, observed, netlist_sha256)
    return tuple(
        LedCurrentRangeCandidate.from_source_evidence(
            LedCurrentRangeFindingEvidence(
                led_map=led_map,
                observed=observed,
                netlist_sha256=netlist_sha256,
                entry=entry,
            )
        )
        for entry in entries
        if entry.status != "MATCHED"
    )

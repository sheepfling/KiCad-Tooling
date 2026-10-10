"""Schematic geometry reports for deterministic synthetic verification."""

from __future__ import annotations

import hashlib
from pathlib import Path

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.schematic_geometry import scan_wire_ends_on_pin_lines
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    JUNCTION_MARKED_CROSSING,
    UNMARKED_CROSSING,
)

_ROOT = Path(__file__).resolve().parents[2]
_KICAD_VERSION = "10.0.6"
_RULE_ID = "schematic.unmarked_wire_crossing"
_POLICY = DesignLintPolicy(
    rules=(
        DesignLintRuleOverride(
            rule_id=_RULE_ID,
            mode="review",
            reason="Synthetic source-bound hash-seed regression",
        ),
    )
)


def _report(source_path: Path) -> dict[str, object]:
    observed = NetlistContract(components={}, nets={})
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    relative_path = source_path.relative_to(_ROOT).as_posix()
    scan = scan_wire_ends_on_pin_lines(
        source_path.read_bytes(),
        source_path=relative_path,
        kicad_version=_KICAD_VERSION,
        unconnected_pins=frozenset(),
    )
    report = evaluate(
        "synthetic-schematic-wire-crossing",
        coach(observed, netlist_sha256),
        _POLICY,
        schematic_geometry=scan,
    )
    return report.model_dump(mode="json")


def report_cases() -> dict[str, object]:
    return {
        "schematic_wire_crossing_fault": _report(UNMARKED_CROSSING),
        "schematic_wire_crossing_junction_control": _report(JUNCTION_MARKED_CROSSING),
    }

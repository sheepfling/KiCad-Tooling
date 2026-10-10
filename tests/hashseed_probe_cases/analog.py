"""Source-mapped analog reports for deterministic synthetic verification."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel

from kicad_tooling.hwrepo.models import DesignLintReport
from tests.test_crystal_networks import crystal_map, crystal_netlist, report
from tests.test_rc_filters import rc_filter_map, rc_filter_netlist
from tests.test_rc_filters import report as rc_filter_report
from tests.test_regulator_feedback import (
    regulator_feedback_map,
    regulator_netlist,
)
from tests.test_regulator_feedback import (
    report as regulator_feedback_report,
)


def _digest(model: BaseModel) -> str:
    return hashlib.sha256(model.model_dump_json().encode("utf-8")).hexdigest()


def _case(
    requirement: BaseModel,
    observed: BaseModel,
    result: DesignLintReport,
) -> dict[str, object]:
    return {
        "requirement_sha256": _digest(requirement),
        "netlist_sha256": _digest(observed),
        "report": result.model_dump(mode="json"),
    }


def mapped_crystal_network_report(*, fault: bool) -> dict[str, object]:
    """Serialize a mapped crystal-node fault or its valid control."""
    requirement = crystal_map()
    observed = crystal_netlist(fault="wrong-capacitor-node" if fault else None)
    result = report(observed, requirement, netlist_sha256=_digest(observed))
    return _case(requirement, observed, result)


def mapped_regulator_feedback_report(*, fault: bool) -> dict[str, object]:
    """Serialize a mapped feedback-divider range fault or its valid control."""
    requirement = regulator_feedback_map()
    observed = regulator_netlist(fault="upper-resistor-outside-range" if fault else None)
    result = regulator_feedback_report(observed, requirement, netlist_sha256=_digest(observed))
    return _case(requirement, observed, result)


def mapped_rc_filter_report(*, fault: bool) -> dict[str, object]:
    """Serialize a mapped RC cutoff fault or its valid control."""
    requirement = rc_filter_map()
    observed = rc_filter_netlist(capacitor_value="220nF" if fault else "100nF")
    result = rc_filter_report(observed, requirement, netlist_sha256=_digest(observed))
    return _case(requirement, observed, result)


def report_cases() -> dict[str, object]:
    return {
        "mapped_crystal_network_fault": mapped_crystal_network_report(fault=True),
        "mapped_crystal_network_control": mapped_crystal_network_report(fault=False),
        "mapped_regulator_feedback_fault": mapped_regulator_feedback_report(fault=True),
        "mapped_regulator_feedback_control": mapped_regulator_feedback_report(fault=False),
        "mapped_rc_filter_fault": mapped_rc_filter_report(fault=True),
        "mapped_rc_filter_control": mapped_rc_filter_report(fault=False),
    }

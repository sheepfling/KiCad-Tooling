"""Theme-specific candidate translators for PCB measurements and rule coverage."""

from __future__ import annotations

from .design_lint_pcb_differential_pair_coverage_evidence import (
    PcbDifferentialPairCoverageCandidate,
    PcbDifferentialPairCoverageFindingEvidence,
)
from .design_lint_pcb_inputs import PcbCandidateInputs
from .design_lint_pcb_keepout_candidate_evidence import (
    PcbKeepoutCandidate,
    PcbKeepoutFindingEvidence,
)
from .design_lint_pcb_rf_antenna_candidate_evidence import (
    PcbRfAntennaCandidate,
    PcbRfAntennaFindingEvidence,
)
from .design_lint_pcb_signal_path_coverage_evidence import (
    PcbSignalPathCoverageCandidate,
    PcbSignalPathCoverageFindingEvidence,
)
from .design_lint_pcb_switching_loop_candidate_evidence import (
    PcbSwitchingLoopCandidate,
    PcbSwitchingLoopFindingEvidence,
)
from .design_lint_pcb_touch_pad_clearance_candidate_evidence import (
    touch_pad_clearance_violations,
)
from .design_lint_types import Candidate
from .pcb_drc_models import (
    PcbDifferentialPairRuleCoverageReport,
    PcbSignalPathRuleCoverageReport,
)
from .pcb_keepout_models import (
    PcbKeepoutCoverageReport,
)
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageReport,
)
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceCoverageReport


def scan_pcb_requirement_candidates(inputs: PcbCandidateInputs) -> tuple[Candidate, ...]:
    """Route the PCB group's resolved requirement coverage to its translators."""
    return pcb_requirement_coverage_candidates(
        pcb_switching_loop_coverage=inputs.switching_loop,
        pcb_differential_pair_coverage=inputs.differential_pair,
        pcb_signal_path_coverage=inputs.signal_path,
        pcb_keepout_coverage=inputs.keepout,
        pcb_rf_module_antenna_coverage=inputs.rf_antenna,
        pcb_touch_pad_clearance_coverage=inputs.touch_pad_clearance,
    )


def pcb_requirement_coverage_candidates(
    *,
    pcb_switching_loop_coverage: PcbSwitchingLoopCoverageReport | None = None,
    pcb_differential_pair_coverage: PcbDifferentialPairRuleCoverageReport | None = None,
    pcb_signal_path_coverage: PcbSignalPathRuleCoverageReport | None = None,
    pcb_keepout_coverage: PcbKeepoutCoverageReport | None = None,
    pcb_rf_module_antenna_coverage: PcbRfModuleAntennaCoverageReport | None = None,
    pcb_touch_pad_clearance_coverage: PcbTouchPadClearanceCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Translate authored PCB requirement coverage gaps into review candidates."""
    found: list[Candidate] = []
    if pcb_switching_loop_coverage is not None:
        for entry in pcb_switching_loop_coverage.entries:
            if entry.status == "COMPLETE" and entry.maximum_area_um2 is not None:
                continue
            found.append(
                PcbSwitchingLoopCandidate.from_source_evidence(
                    PcbSwitchingLoopFindingEvidence(
                        report=pcb_switching_loop_coverage,
                        entry=entry,
                    ),
                    subject=f"{entry.id}: return net {entry.return_net}",
                    message=(
                        "Review the mapped switching-current loop, measured trace chains, and "
                        "return-plane evidence. The area is a polygon through authored pad "
                        "centers; trace lengths use native endpoint geometry. Neither establishes "
                        "the full current path or estimates parasitics, emissions, stability, or "
                        "electrical performance."
                    ),
                )
            )
    if pcb_differential_pair_coverage is not None:
        for entry in pcb_differential_pair_coverage.entries:
            if entry.status != "INCOMPLETE":
                continue
            found.append(
                PcbDifferentialPairCoverageCandidate.from_source_evidence(
                    PcbDifferentialPairCoverageFindingEvidence(
                        report=pcb_differential_pair_coverage,
                        entry=entry,
                    ),
                    subject=f"{entry.id}: {entry.positive_net} / {entry.negative_net}",
                    message=(
                        "This project-authored differential-pair requirement is missing an exact, "
                        "active native DRC rule or supported pair identity. Review the pair map, "
                        "KiCad rule file, and ignored-check settings."
                    ),
                )
            )
    if pcb_signal_path_coverage is not None:
        for entry in pcb_signal_path_coverage.entries:
            if entry.status != "INCOMPLETE":
                continue
            subject = (
                f"{entry.id}: {entry.net} {entry.from_pad} to {entry.to_pad}"
                if entry.kind == "path"
                else f"{entry.id}: {entry.from_pad_pattern} to {entry.to_pad_pattern} bundle"
            )
            found.append(
                PcbSignalPathCoverageCandidate.from_source_evidence(
                    PcbSignalPathCoverageFindingEvidence(
                        report=pcb_signal_path_coverage,
                        entry=entry,
                    ),
                    subject=subject,
                    message=(
                        "This mapped PCB signal-path requirement lacks exact active native DRC "
                        "coverage or its mapped pads do not match source-bound board evidence. "
                        "Review the path map, native rule, and endpoint connectivity."
                    ),
                )
            )
    if pcb_keepout_coverage is not None:
        for entry in pcb_keepout_coverage.entries:
            if entry.status != "INCOMPLETE":
                continue
            found.append(
                PcbKeepoutCandidate.from_source_evidence(
                    PcbKeepoutFindingEvidence(
                        report=pcb_keepout_coverage,
                        entry=entry,
                    ),
                    subject=f"{entry.id}: named keepout {entry.name}",
                    message=(
                        "This named PCB keepout differs from its project-reviewed geometry, "
                        "copper-layer, or restriction signature. Review the independent source "
                        "requirement and the native rule area before updating either record."
                    ),
                )
            )
    if pcb_rf_module_antenna_coverage is not None:
        for entry in pcb_rf_module_antenna_coverage.entries:
            if entry.status != "INCOMPLETE":
                continue
            found.append(
                PcbRfAntennaCandidate.from_source_evidence(
                    PcbRfAntennaFindingEvidence(
                        report=pcb_rf_module_antenna_coverage,
                        entry=entry,
                    ),
                    subject=f"{entry.reference}: {entry.disposition} antenna requirement",
                    message=(
                        "This RF module does not match the project-authored schematic and PCB "
                        "identity, fitted state, feed net, or placement-relative antenna keepout. "
                        "Review the independent module documentation and native source evidence."
                    ),
                )
            )
    if pcb_touch_pad_clearance_coverage is not None:
        found.extend(touch_pad_clearance_violations(pcb_touch_pad_clearance_coverage))
    return tuple(found)

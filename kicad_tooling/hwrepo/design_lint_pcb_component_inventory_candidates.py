"""PCB component inventory finding translation for design-lint reports."""

from __future__ import annotations

from .design_lint_types import Candidate
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport


def pcb_component_inventory_candidates(
    report: PcbComponentInventoryCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Translate source-bound inventory gaps and missing placements into findings."""
    if report is None or report.status in {"NOT_APPLICABLE", "DISABLED"}:
        return ()
    if report.status == "BLOCKED":
        candidates = [
            Candidate(
                rule_id="pcb.schematic_component_inventory",
                subject="native PCB footprint inventory unavailable",
                message=(
                    "The source-bound PCB footprint inventory could not be compared with the "
                    "native schematic netlist. No placement conclusion is available."
                ),
                evidence={
                    "coverage_issue": (report.issue or "unavailable",),
                    "netlist_sha256": (
                        () if report.netlist_sha256 is None else (report.netlist_sha256,)
                    ),
                    "board_path": (() if report.board_path is None else (report.board_path,)),
                    "board_sha256": (() if report.board_sha256 is None else (report.board_sha256,)),
                },
            ),
            Candidate(
                rule_id="pcb.schematic_pcb_dnp_mismatch",
                subject="schematic and PCB population comparison unavailable",
                message=(
                    "The source-bound schematic DNP state could not be compared with the native PCB. "
                    "No population-consistency conclusion is available."
                ),
                evidence={
                    "coverage_issue": (report.issue or "unavailable",),
                    "netlist_sha256": (
                        () if report.netlist_sha256 is None else (report.netlist_sha256,)
                    ),
                    "board_path": (() if report.board_path is None else (report.board_path,)),
                    "board_sha256": (() if report.board_sha256 is None else (report.board_sha256,)),
                    "snapshot_sha256": (
                        () if report.snapshot_sha256 is None else (report.snapshot_sha256,)
                    ),
                },
            ),
        ]
        if report.value_comparison_status == "BLOCKED":
            candidates.append(
                Candidate(
                    rule_id="pcb.schematic_pcb_value_mismatch",
                    subject="schematic and PCB component value comparison unavailable",
                    message=(
                        "The source-bound schematic and native PCB value fields could not be "
                        "compared. No value-consistency conclusion is available."
                    ),
                    evidence={
                        "coverage_issue": (
                            report.value_comparison_issue or report.issue or "unavailable",
                        ),
                        "netlist_sha256": (
                            () if report.netlist_sha256 is None else (report.netlist_sha256,)
                        ),
                        "board_path": (() if report.board_path is None else (report.board_path,)),
                        "board_sha256": (
                            () if report.board_sha256 is None else (report.board_sha256,)
                        ),
                        "snapshot_sha256": (
                            () if report.snapshot_sha256 is None else (report.snapshot_sha256,)
                        ),
                        "snapshot_schema": (
                            () if report.snapshot_schema is None else (report.snapshot_schema,)
                        ),
                    },
                )
            )
        return tuple(candidates)
    candidates = [
        Candidate(
            rule_id="pcb.schematic_component_inventory",
            subject=f"{item.reference}: schematic footprint absent from PCB",
            message=(
                "This fitted schematic component has an assigned footprint, but the source-bound "
                "native PCB snapshot has no footprint with the same reference. Confirm whether "
                "the component is intentionally off-board; otherwise restore its board placement. "
                "This check does not infer electrical role, assembly intent, or manufacturability."
            ),
            evidence={
                "reference": (item.reference,),
                "assigned_footprint": (item.assigned_footprint,),
                "netlist_sha256": (report.netlist_sha256 or "unavailable",),
                "board_path": (report.board_path or "unavailable",),
                "board_sha256": (report.board_sha256 or "unavailable",),
                "snapshot_sha256": (report.snapshot_sha256 or "unavailable",),
                "snapshot_schema": (report.snapshot_schema or "unavailable",),
                "kicad_version": (report.kicad_version or "unavailable",),
                "image": (report.image or "unavailable",),
                "probe_sha256": (report.probe_sha256 or "unavailable",),
            },
        )
        for item in report.missing_placements
    ]
    candidates.extend(
        Candidate(
            rule_id="pcb.schematic_component_inventory",
            subject=f"{item.reference}: schematic and PCB footprint identities differ",
            message=(
                "The schematic assigns a different footprint identity from the source-bound PCB. "
                "Confirm the intended package or document the approved alternate; differing IDs "
                "can be intentional, and this exact-name comparison does not establish pad or "
                "geometry equivalence."
            ),
            evidence={
                "reference": (item.reference,),
                "assigned_footprint": (item.assigned_footprint,),
                "placed_footprint": (item.placed_footprint,),
                "netlist_sha256": (report.netlist_sha256 or "unavailable",),
                "board_path": (report.board_path or "unavailable",),
                "board_sha256": (report.board_sha256 or "unavailable",),
                "snapshot_sha256": (report.snapshot_sha256 or "unavailable",),
                "snapshot_schema": (report.snapshot_schema or "unavailable",),
                "kicad_version": (report.kicad_version or "unavailable",),
                "image": (report.image or "unavailable",),
                "probe_sha256": (report.probe_sha256 or "unavailable",),
            },
        )
        for item in report.footprint_mismatches
    )
    candidates.extend(
        Candidate(
            rule_id="pcb.schematic_pcb_dnp_mismatch",
            subject=(
                f"{item.reference}: schematic and PCB DNP states differ"
                if item.variant is None
                else f"{item.reference}: schematic and PCB DNP states differ in {item.variant}"
            ),
            message=(
                "The schematic and placed PCB footprint disagree whether this component is marked "
                "DNP. Confirm the intended assembly variant and align the two CAD records. This "
                "compares CAD flags only; it does not establish physical population."
            ),
            evidence={
                "reference": (item.reference,),
                "schematic_dnp": (str(item.schematic_dnp).lower(),),
                "board_dnp": (str(item.board_dnp).lower(),),
                "netlist_sha256": (report.netlist_sha256 or "unavailable",),
                "board_path": (report.board_path or "unavailable",),
                "board_sha256": (report.board_sha256 or "unavailable",),
                "snapshot_sha256": (report.snapshot_sha256 or "unavailable",),
                "snapshot_schema": (report.snapshot_schema or "unavailable",),
                "kicad_version": (report.kicad_version or "unavailable",),
                "image": (report.image or "unavailable",),
                "probe_sha256": (report.probe_sha256 or "unavailable",),
                **_variant_population_evidence(report, item.variant),
            },
        )
        for item in report.population_mismatches
    )
    if report.variant_population.status == "BLOCKED":
        variant_coverage = report.variant_population
        candidates.append(
            Candidate(
                rule_id="pcb.schematic_pcb_dnp_mismatch",
                subject="named variant DNP comparison unavailable",
                message=(
                    "The project declares one or more named variants, but source-bound schematic "
                    "and PCB exports could not be paired for every variant. No variant population "
                    "consistency conclusion is available."
                ),
                evidence={
                    "coverage_issue": (variant_coverage.issue or "unavailable",),
                    "project_path": (
                        ()
                        if variant_coverage.project_path is None
                        else (variant_coverage.project_path,)
                    ),
                    "project_sha256": (
                        ()
                        if variant_coverage.project_sha256 is None
                        else (variant_coverage.project_sha256,)
                    ),
                    "schematic_path": (
                        ()
                        if variant_coverage.schematic_path is None
                        else (variant_coverage.schematic_path,)
                    ),
                    "schematic_sha256": (
                        ()
                        if variant_coverage.schematic_sha256 is None
                        else (variant_coverage.schematic_sha256,)
                    ),
                    "board_path": (
                        ()
                        if variant_coverage.board_path is None
                        else (variant_coverage.board_path,)
                    ),
                    "board_sha256": (
                        ()
                        if variant_coverage.board_sha256 is None
                        else (variant_coverage.board_sha256,)
                    ),
                    "kicad_version": (
                        ()
                        if variant_coverage.kicad_version is None
                        else (variant_coverage.kicad_version,)
                    ),
                    "image": (() if variant_coverage.image is None else (variant_coverage.image,)),
                    "board_variant_probe_sha256": (
                        ()
                        if variant_coverage.board_variant_probe_sha256 is None
                        else (variant_coverage.board_variant_probe_sha256,)
                    ),
                    "board_variant_request_sha256": (
                        ()
                        if variant_coverage.board_variant_request_sha256 is None
                        else (variant_coverage.board_variant_request_sha256,)
                    ),
                    "board_variant_command_sha256": (
                        ()
                        if variant_coverage.board_variant_command_sha256 is None
                        else (variant_coverage.board_variant_command_sha256,)
                    ),
                    "partial_variant_exports": tuple(
                        f"{item.variant}:{item.netlist_sha256}:"
                        f"{item.board_all_positions_sha256}:{item.board_fitted_positions_sha256}"
                        for item in variant_coverage.evidence
                    ),
                },
            )
        )
    if report.value_comparison_status == "BLOCKED":
        candidates.append(
            Candidate(
                rule_id="pcb.schematic_pcb_value_mismatch",
                subject="native PCB footprint values unavailable",
                message=(
                    "Source-bound PCB value evidence is incomplete, including any declared named "
                    "variant exports. No value-consistency conclusion is available."
                ),
                evidence={
                    "coverage_issue": (
                        report.value_comparison_issue or "value comparison unavailable",
                    ),
                    "netlist_sha256": (report.netlist_sha256 or "unavailable",),
                    "board_path": (report.board_path or "unavailable",),
                    "board_sha256": (report.board_sha256 or "unavailable",),
                    "snapshot_sha256": (report.snapshot_sha256 or "unavailable",),
                    "snapshot_schema": (report.snapshot_schema or "unavailable",),
                    "kicad_version": (report.kicad_version or "unavailable",),
                    "image": (report.image or "unavailable",),
                    "probe_sha256": (report.probe_sha256 or "unavailable",),
                },
            )
        )
    candidates.extend(
        Candidate(
            rule_id="pcb.schematic_pcb_value_mismatch",
            subject=(
                f"{item.reference}: schematic and PCB value fields differ"
                if item.variant is None
                else f"{item.reference}: schematic and PCB value fields differ in {item.variant}"
            ),
            message=(
                "The same-name schematic and PCB variant value fields differ as text. Review which "
                "value should appear for this assembly variant. This comparison does not establish "
                "electrical equivalence, part identity, physical population, or assembly intent."
                if item.variant is not None
                else "The schematic value and placed PCB footprint value differ as text. Review which "
                "value should appear in the fabrication source; this comparison does not establish "
                "electrical equivalence, part identity, physical population, or assembly intent."
            ),
            evidence={
                "reference": (item.reference,),
                "schematic_value": (item.schematic_value,),
                "board_value": (item.board_value,),
                "netlist_sha256": (report.netlist_sha256 or "unavailable",),
                "board_path": (report.board_path or "unavailable",),
                "board_sha256": (report.board_sha256 or "unavailable",),
                "snapshot_sha256": (report.snapshot_sha256 or "unavailable",),
                "snapshot_schema": (report.snapshot_schema or "unavailable",),
                "kicad_version": (report.kicad_version or "unavailable",),
                "image": (report.image or "unavailable",),
                "probe_sha256": (report.probe_sha256 or "unavailable",),
                **_variant_population_evidence(report, item.variant),
            },
        )
        for item in report.value_mismatches
    )
    return tuple(sorted(candidates, key=lambda item: item.subject.casefold()))


def _variant_population_evidence(
    report: PcbComponentInventoryCoverageReport,
    variant: str | None,
) -> dict[str, tuple[str, ...]]:
    if variant is None:
        return {}
    evidence = next(
        (item for item in report.variant_population.evidence if item.variant == variant),
        None,
    )
    if evidence is None:
        return {"variant": (variant,), "variant_evidence": ("unavailable",)}
    coverage = report.variant_population
    return {
        "variant": (variant,),
        "variant_project_path": (() if coverage.project_path is None else (coverage.project_path,)),
        "variant_project_sha256": (
            () if coverage.project_sha256 is None else (coverage.project_sha256,)
        ),
        "variant_schematic_path": (
            () if coverage.schematic_path is None else (coverage.schematic_path,)
        ),
        "variant_schematic_sha256": (
            () if coverage.schematic_sha256 is None else (coverage.schematic_sha256,)
        ),
        "variant_board_path": (() if coverage.board_path is None else (coverage.board_path,)),
        "variant_board_sha256": (() if coverage.board_sha256 is None else (coverage.board_sha256,)),
        "variant_board_probe_path": (
            ()
            if coverage.board_variant_probe_path is None
            else (coverage.board_variant_probe_path,)
        ),
        "variant_board_probe_sha256": (
            ()
            if coverage.board_variant_probe_sha256 is None
            else (coverage.board_variant_probe_sha256,)
        ),
        "variant_board_request_path": (
            ()
            if coverage.board_variant_request_path is None
            else (coverage.board_variant_request_path,)
        ),
        "variant_board_request_sha256": (
            ()
            if coverage.board_variant_request_sha256 is None
            else (coverage.board_variant_request_sha256,)
        ),
        "variant_board_probe_command_path": (
            ()
            if coverage.board_variant_command_path is None
            else (coverage.board_variant_command_path,)
        ),
        "variant_board_probe_command_sha256": (
            ()
            if coverage.board_variant_command_sha256 is None
            else (coverage.board_variant_command_sha256,)
        ),
        "variant_kicad_version": (
            () if coverage.kicad_version is None else (coverage.kicad_version,)
        ),
        "variant_image": (() if coverage.image is None else (coverage.image,)),
        "variant_netlist_path": (evidence.netlist_path,),
        "variant_netlist_sha256": (evidence.netlist_sha256,),
        "variant_netlist_command_path": (evidence.netlist_command_path,),
        "variant_netlist_command_sha256": (evidence.netlist_command_sha256,),
        "variant_board_all_positions_path": (evidence.board_all_positions_path,),
        "variant_board_all_positions_sha256": (evidence.board_all_positions_sha256,),
        "variant_board_all_command_path": (evidence.board_all_command_path,),
        "variant_board_all_command_sha256": (evidence.board_all_command_sha256,),
        "variant_board_fitted_positions_path": (evidence.board_fitted_positions_path,),
        "variant_board_fitted_positions_sha256": (evidence.board_fitted_positions_sha256,),
        "variant_board_fitted_command_path": (evidence.board_fitted_command_path,),
        "variant_board_fitted_command_sha256": (evidence.board_fitted_command_sha256,),
    }

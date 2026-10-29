"""Synthetic named-variant regressions for fitted PCB requirements."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_pcb_required_fitted_reference_candidates import (
    pcb_required_fitted_reference_candidates,
)
from kicad_tooling.hwrepo.design_lint_pcb_required_fitted_reference_report import (
    required_fitted_reference_report_lines,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbVariantPopulationCoverage,
    PcbVariantPopulationEvidence,
)
from kicad_tooling.hwrepo.pcb_component_population import PcbVariantPopulationSource
from kicad_tooling.hwrepo.pcb_required_fitted_reference_checks import (
    required_fitted_reference_map_sha256,
)
from kicad_tooling.hwrepo.pcb_required_fitted_reference_models import (
    PcbRequiredFittedReference,
    PcbRequiredFittedReferenceMap,
    PcbRequiredFittedReferenceVariant,
)
from kicad_tooling.hwrepo.pcb_variant_population_capture import PcbVariantPopulationCapture
from tests.design_lint_fixtures.pcb_component_inventory import (
    netlist,
    required_fitted_reference_coverage,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]
RULE = "pcb.required_fitted_reference"
FOOTPRINT = "Synthetic:Probe_Module"
VARIANT = "Synthetic Assembly A"


def _variant_map(name: str = VARIANT) -> PcbRequiredFittedReferenceMap:
    return PcbRequiredFittedReferenceMap(
        basis="synthetic approved named-assembly requirement",
        variants=(
            PcbRequiredFittedReferenceVariant(
                variant=name,
                requirements=(
                    PcbRequiredFittedReference(
                        reference="U1",
                        footprint=FOOTPRINT,
                        basis="U1 is required in this assembly",
                    ),
                ),
            ),
        ),
    )


def _variant_capture(source: PcbVariantPopulationSource) -> PcbVariantPopulationCapture:
    evidence = PcbVariantPopulationEvidence(
        variant=source.variant,
        netlist_path="build/design-lint/variant/netlist.xml",
        netlist_sha256="1" * 64,
        netlist_command_path="build/design-lint/variant/netlist.command.json",
        netlist_command_sha256="2" * 64,
        board_all_positions_path="build/design-lint/variant/board-all.csv",
        board_all_positions_sha256="3" * 64,
        board_all_command_path="build/design-lint/variant/board-all.command.json",
        board_all_command_sha256="4" * 64,
        board_fitted_positions_path="build/design-lint/variant/board-fitted.csv",
        board_fitted_positions_sha256="5" * 64,
        board_fitted_command_path="build/design-lint/variant/board-fitted.command.json",
        board_fitted_command_sha256="6" * 64,
    )
    coverage = PcbVariantPopulationCoverage(
        status="COMPLETE",
        project_path="projects/synthetic/controller.kicad_pro",
        project_sha256="7" * 64,
        schematic_path="projects/synthetic/controller.kicad_sch",
        schematic_sha256="8" * 64,
        board_path="projects/synthetic/controller.kicad_pcb",
        board_sha256="9" * 64,
        kicad_version="10.0.5",
        image="registry.example/kicad:10.0.5@sha256:" + "a" * 64,
        board_variant_probe_path="build/design-lint/variant/probe.py",
        board_variant_probe_sha256="b" * 64,
        board_variant_request_path="build/design-lint/variant/request.json",
        board_variant_request_sha256="c" * 64,
        board_variant_command_path="build/design-lint/variant/probe.command.json",
        board_variant_command_sha256="d" * 64,
        evidence=(evidence,),
    )
    return PcbVariantPopulationCapture(sources=(source,), coverage=coverage)


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_named_variant_requirement_catches_matching_schematic_and_board_dnp() -> None:
    base = netlist(components={"U1": FOOTPRINT})
    board = snapshot("U1", footprint_by_reference={"U1": FOOTPRINT})
    source = PcbVariantPopulationSource(
        variant=VARIANT,
        netlist=netlist(components={"U1": FOOTPRINT}, dnp=("U1",)),
        board_references=("U1",),
        fitted_board_references=(),
    )
    coverage = required_fitted_reference_coverage(
        base,
        board,
        _variant_map(),
        variant_population=_variant_capture(source),
    )
    required = coverage.required_fitted_reference_coverage
    assert required.status == "COMPLETE"
    assert required.requirement_count == 1
    (mismatch,) = required.mismatches
    assert (mismatch.reference, mismatch.variant) == ("U1", VARIANT)
    assert mismatch.violations == ("schematic_component_dnp", "board_footprint_dnp")

    (candidate,) = pcb_required_fitted_reference_candidates(coverage)
    assert candidate.subject.startswith(f"U1 in variant '{VARIANT}'")
    assert candidate.evidence["variant"] == (VARIANT,)
    assert candidate.evidence["variant_evidence"] == (
        "tool=10.0.5@registry.example/kicad:10.0.5@sha256:" + "a" * 64,
        "project=projects/synthetic/controller.kicad_pro@" + "7" * 64,
        "schematic=projects/synthetic/controller.kicad_sch@" + "8" * 64,
        "board=projects/synthetic/controller.kicad_pcb@" + "9" * 64,
        "variant_probe=build/design-lint/variant/probe.py@" + "b" * 64,
        "variant_request=build/design-lint/variant/request.json@" + "c" * 64,
        "variant_probe_command=build/design-lint/variant/probe.command.json@" + "d" * 64,
        f"{VARIANT}:netlist=build/design-lint/variant/netlist.xml@" + "1" * 64,
        f"{VARIANT}:netlist_command=build/design-lint/variant/netlist.command.json@" + "2" * 64,
        f"{VARIANT}:board_all=build/design-lint/variant/board-all.csv@" + "3" * 64,
        f"{VARIANT}:board_all_command=build/design-lint/variant/board-all.command.json@" + "4" * 64,
        f"{VARIANT}:board_fitted=build/design-lint/variant/board-fitted.csv@" + "5" * 64,
        f"{VARIANT}:board_fitted_command=build/design-lint/variant/board-fitted.command.json@"
        + "6" * 64,
    )
    assert any(
        f"U1 in variant '{VARIANT}'" in line
        for line in required_fitted_reference_report_lines(coverage)
    )


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_named_variant_fitted_requirement_is_quiet_and_missing_exports_block() -> None:
    base = netlist(components={"U1": FOOTPRINT})
    board = snapshot("U1", footprint_by_reference={"U1": FOOTPRINT})
    fitted_source = PcbVariantPopulationSource(
        variant=VARIANT,
        netlist=netlist(components={"U1": FOOTPRINT}),
        board_references=("U1",),
        fitted_board_references=("U1",),
    )
    fitted = required_fitted_reference_coverage(
        base,
        board,
        _variant_map(),
        variant_population=_variant_capture(fitted_source),
    )
    assert fitted.required_fitted_reference_coverage.status == "COMPLETE"
    assert fitted.required_fitted_reference_coverage.mismatches == ()
    assert pcb_required_fitted_reference_candidates(fitted) == ()

    unavailable = required_fitted_reference_coverage(base, board, _variant_map())
    required = unavailable.required_fitted_reference_coverage
    assert required.status == "BLOCKED"
    assert "no complete source-bound native export" in (required.issue or "")
    (candidate,) = pcb_required_fitted_reference_candidates(unavailable)
    assert candidate.evidence["coverage_issue"] == (required.issue,)


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_variant_names_resolve_case_insensitively_and_map_hash_is_order_stable() -> None:
    requirement = PcbRequiredFittedReference(
        reference="U1", footprint=FOOTPRINT, basis="variant requirement"
    )
    requirements = _variant_map("synthetic assembly a")
    source = PcbVariantPopulationSource(
        variant=VARIANT,
        netlist=netlist(components={"U1": FOOTPRINT}),
        board_references=("U1",),
        fitted_board_references=("U1",),
    )
    report = required_fitted_reference_coverage(
        netlist(components={"U1": FOOTPRINT}),
        snapshot("U1", footprint_by_reference={"U1": FOOTPRINT}),
        requirements,
        variant_population=_variant_capture(source),
    )
    assert report.required_fitted_reference_coverage.status == "COMPLETE"
    assert report.required_fitted_reference_coverage.mismatches == ()

    second = PcbRequiredFittedReferenceVariant(
        variant="Synthetic Assembly B",
        requirements=(requirement,),
    )
    reordered = requirements.model_copy(update={"variants": (*requirements.variants, second)})
    assert required_fitted_reference_map_sha256(reordered) == required_fitted_reference_map_sha256(
        reordered.model_copy(update={"variants": tuple(reversed(reordered.variants))})
    )


def test_complete_variant_capture_rejects_sources_without_matching_evidence_names() -> None:
    source = PcbVariantPopulationSource(
        variant=VARIANT,
        netlist=netlist(components={"U1": FOOTPRINT}),
        board_references=("U1",),
        fitted_board_references=("U1",),
    )
    capture = _variant_capture(source)
    changed_name = PcbVariantPopulationSource(
        variant="Different Assembly",
        netlist=source.netlist,
        board_references=source.board_references,
        fitted_board_references=source.fitted_board_references,
    )

    with pytest.raises(ValueError, match="must match the source-bound evidence inventory"):
        PcbVariantPopulationCapture(sources=(changed_name,), coverage=capture.coverage)

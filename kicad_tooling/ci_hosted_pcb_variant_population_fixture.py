"""Exact KiCad fault/control evidence for named-variant population and values."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .ci_hosted_pcb_fixture_support import (
    HostedPcbFixtureFailure,
    capture_verified_pcb_snapshot,
    prepare_pcb_fixture,
)
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.evidence import digest
from .hwrepo.pcb_component_inventory import evaluate_native_component_inventory_coverage
from .hwrepo.pcb_component_population import compare_variant_population_source
from .hwrepo.pcb_required_fitted_reference_checks import compare_required_fitted_references
from .hwrepo.pcb_required_fitted_reference_models import (
    PcbRequiredFittedReference,
    PcbRequiredFittedReferenceMap,
    PcbRequiredFittedReferenceVariant,
)
from .hwrepo.pcb_variant_population_capture import (
    capture_variant_population,
)
from .validate import hashes

VARIANT = "Synthetic Assembly A"


def pcb_variant_population_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Run native named-variant exports against synthetic faults and controls."""
    context = prepare_pcb_fixture(
        root,
        project=project,
        image=image,
        log=log,
        lane="PCB named-variant population",
        scratch_prefix="pcb-variant-population",
    )
    fixture_root = tooling_checkout_root() / ("tests/fixtures/design_lint/named-variant-population")
    schematic_root = tooling_checkout_root() / (
        "tests/fixtures/design_lint/component-inventory-footprint-identity"
    )
    source_directory = context.root / "projects/synthetic-variant-population"
    source_root = source_directory.relative_to(context.root).as_posix()
    project_source = fixture_root / "variant.kicad_pro"
    cases: dict[
        str,
        tuple[Path, Path, tuple[str, ...] | None, tuple[bool, bool]],
    ] = {
        "board-only-dnp": (
            schematic_root / "control.kicad_sch",
            fixture_root / "board-u1-dnp.kicad_pcb",
            ("U1",),
            (False, True),
        ),
        "schematic-only-dnp": (
            schematic_root / "population-schematic-dnp.kicad_sch",
            fixture_root / "board-fitted.kicad_pcb",
            ("U1",),
            (True, False),
        ),
        "both-fitted": (
            schematic_root / "control.kicad_sch",
            fixture_root / "board-fitted.kicad_pcb",
            (),
            (False, False),
        ),
        "board-missing-variant": (
            schematic_root / "control.kicad_sch",
            schematic_root / "control.kicad_pcb",
            None,
            (False, False),
        ),
        "variant-value-fault": (
            schematic_root / "control.kicad_sch",
            fixture_root / "board-u1-variant-value-mismatch.kicad_pcb",
            (),
            (False, False),
        ),
    }
    expected_fixture_hashes = {
        project_source: "c2e8cac912a1257972f849bae9f142a3ca771de283f4f37571bcf07c1c75fcb3",
        fixture_root / "board-u1-dnp.kicad_pcb": (
            "27441e0849367c46395e50350e608828dba742c4933571e52013400b33402107"
        ),
        fixture_root / "board-fitted.kicad_pcb": (
            "3d8b2a60b9f847a6a530acf1f146734c64c9437d600c6683c1123b1f13aead76"
        ),
        fixture_root / "board-u1-variant-value-mismatch.kicad_pcb": (
            "398e5cd2258e4c59e33f1badf50835a67ff330fc41b0a493727e53b51c1a5e2c"
        ),
        schematic_root / "control.kicad_sch": (
            "3acf612f93c0f2f48c6b469928ab9366fc2374644966b9bf07087c8a4cd808f8"
        ),
        schematic_root / "population-schematic-dnp.kicad_sch": (
            "7f185318b3941f10901f8e27bc29b13030ca771e4ff7d3418c09e18a6428c269"
        ),
        schematic_root / "control.kicad_pcb": (
            "23a19d40848ad3b6136f163ccf3ab64c53fef9185d696cde96323b66415d8913"
        ),
    }
    source_hashes: dict[str, str] = {}
    capture_hashes: dict[str, dict[str, str]] = {}
    probe_hashes: dict[str, str] = {}
    variant_value_control = False
    variant_value_fault = False
    variant_value_coverage_blocked = False

    try:
        for source, expected in expected_fixture_hashes.items():
            if digest(source) != expected:
                raise ValueError(f"Named-variant fixture digest changed: {source.name}")
        source_directory.mkdir(parents=True, exist_ok=False)
        for case, (
            schematic_source,
            board_source,
            expected_mismatches,
            expected_state,
        ) in cases.items():
            case_directory = source_directory / case
            case_directory.mkdir()
            project_base = case_directory / "control"
            schematic = project_base.with_suffix(".kicad_sch")
            board = project_base.with_suffix(".kicad_pcb")
            project_file = project_base.with_suffix(".kicad_pro")
            shutil.copyfile(schematic_source, schematic)
            shutil.copyfile(board_source, board)
            shutil.copyfile(project_source, project_file)

            project_relative = project_file.relative_to(context.root).as_posix()
            variant_config = context.config.model_copy(
                update={"project": project_relative, "source_roots": (source_root,)}
            )
            observed_source_hashes = hashes(context.root, variant_config.source_roots)
            source_hashes.update(
                {
                    f"{case}.{name}": value
                    for name, value in observed_source_hashes.items()
                    if name
                    in {
                        schematic.relative_to(context.root).as_posix(),
                        board.relative_to(context.root).as_posix(),
                        project_file.relative_to(context.root).as_posix(),
                    }
                }
            )
            capture = capture_variant_population(
                context.root,
                variant_config,
                context.scratch / f"{case}-capture",
                expected_source_hashes=observed_source_hashes,
                kicad_version=context.config.kicad_version,
            )
            if capture.coverage.board_variant_probe_sha256 is None:
                raise ValueError(
                    f"Native {case} capture omitted the board-variant probe receipt: "
                    f"{capture.coverage.issue or 'no issue reported'}"
                )
            probe_hashes[case] = capture.coverage.board_variant_probe_sha256
            if expected_mismatches is None:
                if (
                    capture.coverage.status != "BLOCKED"
                    or "refusing to compare a default-variant fallback"
                    not in (capture.coverage.issue or "")
                    or capture.sources
                    or capture.coverage.evidence
                ):
                    raise ValueError("Native missing-variant control did not fail closed")
                continue
            if capture.coverage.status != "COMPLETE" or len(capture.sources) != 1:
                raise ValueError(
                    capture.coverage.issue or f"Native {case} variant capture is incomplete"
                )
            source = capture.sources[0]
            mismatches = tuple(item.reference for item in compare_variant_population_source(source))
            if mismatches != expected_mismatches:
                raise ValueError(f"Native {case} variant DNP comparison changed: {mismatches}")
            observed_state = (
                any(reference.casefold() == "u1" for reference in source.netlist.dnp_components),
                "u1" not in {reference.casefold() for reference in source.fitted_board_references},
            )
            if observed_state != expected_state:
                raise ValueError(
                    f"Native {case} variant population state changed: {observed_state}"
                )
            board_hash = observed_source_hashes[board.relative_to(context.root).as_posix()]
            snapshot_receipt = context.scratch / f"{case}-required-reference-pcb-receipt"
            board_snapshot = capture_verified_pcb_snapshot(
                context,
                variant_config,
                snapshot_receipt,
                expected_board_sha256=board_hash,
                purpose=f"{case} required fitted-reference PCB",
            )
            required_map = PcbRequiredFittedReferenceMap(
                basis="synthetic native fixture requires U1 in the named assembly",
                variants=(
                    PcbRequiredFittedReferenceVariant(
                        variant=VARIANT,
                        requirements=(
                            PcbRequiredFittedReference(
                                reference="U1",
                                footprint="Synthetic:Probe_Module",
                                basis="U1 must be fitted in this native variant fixture",
                            ),
                        ),
                    ),
                ),
            )
            required_mismatches = compare_required_fitted_references(
                required_map,
                source.netlist,
                board_snapshot,
                variants=capture.sources,
            )
            observed_required_violations = (
                () if not required_mismatches else required_mismatches[0].violations
            )
            expected_required_violations = {
                "board-only-dnp": ("board_footprint_dnp",),
                "schematic-only-dnp": ("schematic_component_dnp",),
                "both-fitted": (),
                "variant-value-fault": (),
            }[case]
            if observed_required_violations != expected_required_violations:
                raise ValueError(
                    "Native named-variant fitted-reference results changed: "
                    f"{observed_required_violations}"
                )
            if case in {"both-fitted", "variant-value-fault"}:
                variant_evidence = capture.coverage.evidence[0]
                value_coverage = evaluate_native_component_inventory_coverage(
                    source.netlist,
                    board_snapshot,
                    mode="off",
                    netlist_sha256=variant_evidence.netlist_sha256,
                    board_path=board.relative_to(context.root).as_posix(),
                    board_sha256=board_hash,
                    snapshot_path=(snapshot_receipt / "snapshot.json")
                    .relative_to(context.root)
                    .as_posix(),
                    snapshot_sha256=digest(snapshot_receipt / "snapshot.json"),
                    probe_sha256=capture.coverage.board_variant_probe_sha256 or "0" * 64,
                    value_mode="review",
                    variant_population=capture,
                )
                if context.config.kicad_version == "10.0.0":
                    if source.board_values is not None:
                        raise ValueError(
                            "KiCad 10.0.0 unexpectedly supplied variant PCB value evidence"
                        )
                    if value_coverage.value_comparison_status != "BLOCKED" or not (
                        value_coverage.value_comparison_issue
                        and "PCB value export is unavailable"
                        in value_coverage.value_comparison_issue
                    ):
                        raise ValueError(
                            "KiCad 10.0.0 did not block its unsupported variant-value export"
                        )
                    variant_value_coverage_blocked = True
                else:
                    if value_coverage.value_comparison_status != "COMPLETE":
                        raise ValueError(
                            "Native named-variant value coverage did not complete: "
                            f"{value_coverage.value_comparison_issue}"
                        )
                    value_mismatches = value_coverage.value_mismatches
                    if case == "both-fitted":
                        if value_mismatches or source.board_values is None:
                            raise ValueError("Native named-variant value control was not quiet")
                        variant_value_control = True
                    elif (
                        len(value_mismatches) != 1
                        or value_mismatches[0].reference != "U1"
                        or value_mismatches[0].variant != VARIANT
                        or value_mismatches[0].board_value != "Synthetic variant stale label"
                        or value_mismatches[0].schematic_value != "Synthetic identity probe"
                    ):
                        raise ValueError(
                            f"Native named-variant value fault changed: {value_mismatches}"
                        )
                    else:
                        variant_value_fault = True
            evidence = capture.coverage.evidence[0]
            capture_hashes[case] = {
                "netlist": evidence.netlist_sha256,
                "board_all_positions": evidence.board_all_positions_sha256,
                "board_fitted_positions": evidence.board_fitted_positions_sha256,
                "required_reference_snapshot": digest(snapshot_receipt / "snapshot.json"),
            }

        log.event(
            "pcb-variant-population-fixture/screen",
            "PASS",
            project=project,
            kicad_version=context.config.kicad_version,
            variant=VARIANT,
            board_only_dnp="U1",
            schematic_only_dnp="U1",
            both_fitted_mismatches="",
            missing_board_variant_blocked="true",
            variant_value_fault=str(variant_value_fault).lower(),
            variant_value_control=str(variant_value_control).lower(),
            variant_value_coverage_blocked=str(variant_value_coverage_blocked).lower(),
            source_hashes=json.dumps(source_hashes, sort_keys=True),
            native_export_hashes=json.dumps(capture_hashes, sort_keys=True),
            board_variant_probe_hashes=json.dumps(probe_hashes, sort_keys=True),
            board_variant_presence_probed="true",
        )
    except Exception as exc:
        log.event(
            "pcb-variant-population-fixture/screen",
            "FAIL",
            project=project,
            kicad_version=context.config.kicad_version,
            error=str(exc),
        )
        raise HostedPcbFixtureFailure(str(exc)) from exc

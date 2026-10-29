"""Cross-source integrity for PCB evidence grouped in a design-lint report."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from kicad_tooling.hwrepo.pcb_decoupling_models import PcbDecouplingCoverageReport
from kicad_tooling.hwrepo.pcb_keepout_models import PcbKeepoutCoverageReport
from kicad_tooling.hwrepo.pcb_protection_path_models import PcbProtectionPathCoverageReport
from kicad_tooling.hwrepo.pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from kicad_tooling.hwrepo.pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from kicad_tooling.hwrepo.pcb_switching_loop_models import PcbSwitchingLoopCoverageReport
from kicad_tooling.hwrepo.pcb_touch_pad_clearance_models import PcbTouchPadClearanceCoverageReport
from kicad_tooling.hwrepo.pcb_track_width_models import PcbTrackWidthCoverageReport

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint, pytest.mark.pcb_lint]

_BOARD_A = "a" * 64
_BOARD_B = "b" * 64


def _pcb_reports(
    *, board_a: str = _BOARD_A, board_b: str = _BOARD_A, version_a: str = "10.0.5",
    version_b: str = "10.0.5", image_a: str = "sha256:image-a", image_b: str = "sha256:image-a",
) -> dict[str, object]:
    return {
        "pcb_decoupling": PcbDecouplingCoverageReport(
            status="BLOCKED",
            board_sha256=board_a,
            kicad_version=version_a,
            image=image_a,
            issue="Synthetic evidence gap",
        ),
        "pcb_rf_module_antenna_coverage": PcbRfModuleAntennaCoverageReport(
            status="BLOCKED",
            board_sha256=board_b,
            kicad_version=version_b,
            image=image_b,
            issue="Synthetic evidence gap",
        ),
    }


def _report(
    pcb_reports: dict[str, object], *, netlist_sha256: str | None = None
) -> DesignLintReport:
    return DesignLintReport.model_validate(
        {
            "status": "BLOCKED",
            "project_id": "synthetic-pcb-source-consistency",
            "netlist_sha256": netlist_sha256,
            **pcb_reports,
        }
    )


def test_report_rejects_pcb_coverage_from_different_board_revisions() -> None:
    with pytest.raises(ValueError, match="PCB coverage reports must use one board SHA-256"):
        _report(_pcb_reports(board_b=_BOARD_B))


def test_report_rejects_pcb_coverage_from_different_kicad_versions() -> None:
    with pytest.raises(ValueError, match="PCB coverage reports must use one KiCad version"):
        _report(_pcb_reports(version_b="10.0.0"))


def test_report_rejects_pcb_coverage_from_different_native_images() -> None:
    with pytest.raises(ValueError, match="PCB coverage reports must use one native image"):
        _report(_pcb_reports(image_b="sha256:image-b"))


def test_report_accepts_pcb_evidence_from_one_board_and_toolchain() -> None:
    report = _report(_pcb_reports())

    assert report.status == "BLOCKED"
    assert report.pcb_decoupling.board_sha256 == _BOARD_A
    assert report.pcb_rf_module_antenna_coverage.board_sha256 == _BOARD_A


@pytest.mark.parametrize(
    ("field_name", "coverage"),
    (
        (
            "pcb_component_inventory",
            PcbComponentInventoryCoverageReport(
                status="BLOCKED", netlist_sha256=_BOARD_B, issue="Synthetic evidence gap"
            ),
        ),
        (
            "pcb_decoupling",
            PcbDecouplingCoverageReport(
                status="BLOCKED", netlist_sha256=_BOARD_B, issue="Synthetic evidence gap"
            ),
        ),
        (
            "pcb_keepout_coverage",
            PcbKeepoutCoverageReport(
                status="BLOCKED", netlist_sha256=_BOARD_B, issue="Synthetic evidence gap"
            ),
        ),
        (
            "pcb_protection_path",
            PcbProtectionPathCoverageReport(
                status="BLOCKED", netlist_sha256=_BOARD_B, issue="Synthetic evidence gap"
            ),
        ),
        (
            "pcb_reference_plane",
            PcbReferencePlaneCoverageReport(
                status="BLOCKED", netlist_sha256=_BOARD_B, issue="Synthetic evidence gap"
            ),
        ),
        (
            "pcb_rf_module_antenna_coverage",
            PcbRfModuleAntennaCoverageReport(
                status="BLOCKED", netlist_sha256=_BOARD_B, issue="Synthetic evidence gap"
            ),
        ),
        (
            "pcb_switching_loop",
            PcbSwitchingLoopCoverageReport(
                status="BLOCKED", netlist_sha256=_BOARD_B, issue="Synthetic evidence gap"
            ),
        ),
        (
            "pcb_touch_pad_clearance_coverage",
            PcbTouchPadClearanceCoverageReport(
                status="BLOCKED", netlist_sha256=_BOARD_B, issue="Synthetic evidence gap"
            ),
        ),
        (
            "pcb_track_width",
            PcbTrackWidthCoverageReport(
                status="BLOCKED", netlist_sha256=_BOARD_B, issue="Synthetic evidence gap"
            ),
        ),
    ),
)
def test_report_rejects_pcb_coverage_from_a_different_netlist(
    field_name: str, coverage: object
) -> None:
    with pytest.raises(ValueError, match="coverage must use this report's native netlist"):
        _report({field_name: coverage}, netlist_sha256=_BOARD_A)


def test_report_accepts_pcb_netlist_coverage_bound_to_its_current_netlist() -> None:
    report = _report(
        {
            "pcb_decoupling": PcbDecouplingCoverageReport(
                status="BLOCKED", netlist_sha256=_BOARD_A, issue="Synthetic evidence gap"
            )
        },
        netlist_sha256=_BOARD_A,
    )

    assert report.netlist_sha256 == _BOARD_A
    assert report.pcb_decoupling.netlist_sha256 == _BOARD_A

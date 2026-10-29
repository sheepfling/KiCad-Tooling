"""Cross-source integrity for PCB evidence grouped in a design-lint report."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.pcb_decoupling_models import PcbDecouplingCoverageReport
from kicad_tooling.hwrepo.pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport

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


def _report(pcb_reports: dict[str, object]) -> DesignLintReport:
    return DesignLintReport.model_validate(
        {
            "status": "BLOCKED",
            "project_id": "synthetic-pcb-source-consistency",
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

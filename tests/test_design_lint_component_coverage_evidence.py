"""Source binding for component-map evidence embedded in design-lint reports."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.connector_return_distribution_models import (
    ConnectorReturnDistributionCoverageReport,
)
from kicad_tooling.hwrepo.crystal_network_models import CrystalNetworkCoverageReport
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.i2c_address_models import I2cAddressCoverageReport
from kicad_tooling.hwrepo.rc_filter_models import RcFilterCoverageReport
from kicad_tooling.hwrepo.regulator_feedback_models import RegulatorFeedbackCoverageReport

pytestmark = [pytest.mark.design_lint, pytest.mark.evidence_lint]

_REPORT_NETLIST_HASH = "a" * 64
_STALE_NETLIST_HASH = "b" * 64
_INTERFACE_CATALOG_HASH = "c" * 64


@pytest.mark.parametrize(
    ("field_name", "coverage"),
    (
        (
            "i2c_address_coverage",
            I2cAddressCoverageReport(status="COMPLETE", netlist_sha256=_STALE_NETLIST_HASH),
        ),
        (
            "crystal_network_coverage",
            CrystalNetworkCoverageReport(status="COMPLETE", netlist_sha256=_STALE_NETLIST_HASH),
        ),
        (
            "regulator_feedback_coverage",
            RegulatorFeedbackCoverageReport(
                status="COMPLETE", netlist_sha256=_STALE_NETLIST_HASH
            ),
        ),
        (
            "rc_filter_coverage",
            RcFilterCoverageReport(status="COMPLETE", netlist_sha256=_STALE_NETLIST_HASH),
        ),
        (
            "connector_return_distribution",
            ConnectorReturnDistributionCoverageReport(
                status="COMPLETE",
                netlist_sha256=_STALE_NETLIST_HASH,
                interface_catalog_sha256=_INTERFACE_CATALOG_HASH,
            ),
        ),
    ),
)
def test_report_rejects_component_coverage_bound_to_another_netlist(
    field_name: str, coverage: object
) -> None:
    with pytest.raises(ValueError, match="must use this report's native netlist"):
        DesignLintReport.model_validate(
            {
                "status": "PASS",
                "project_id": "synthetic-source-evidence",
                "netlist_sha256": _REPORT_NETLIST_HASH,
                field_name: coverage,
            }
        )


def test_return_distribution_requires_the_report_interface_catalog_binding() -> None:
    with pytest.raises(ValueError, match="must use this report's interface catalog"):
        DesignLintReport.model_validate(
            {
                "status": "PASS",
                "project_id": "synthetic-source-evidence",
                "netlist_sha256": _REPORT_NETLIST_HASH,
                "connector_return_distribution": ConnectorReturnDistributionCoverageReport(
                    status="COMPLETE",
                    netlist_sha256=_REPORT_NETLIST_HASH,
                    interface_catalog_sha256=_INTERFACE_CATALOG_HASH,
                ),
            }
        )


def test_report_accepts_component_coverage_bound_to_its_current_sources() -> None:
    catalog_hash = _INTERFACE_CATALOG_HASH
    report = DesignLintReport.model_validate(
        {
            "status": "PASS",
            "project_id": "synthetic-source-evidence",
            "netlist_sha256": _REPORT_NETLIST_HASH,
            "i2c_address_coverage": I2cAddressCoverageReport(
                status="COMPLETE", netlist_sha256=_REPORT_NETLIST_HASH
            ),
            "crystal_network_coverage": CrystalNetworkCoverageReport(
                status="INCOMPLETE", netlist_sha256=_REPORT_NETLIST_HASH
            ),
            "regulator_feedback_coverage": RegulatorFeedbackCoverageReport(
                status="COMPLETE", netlist_sha256=_REPORT_NETLIST_HASH
            ),
            "rc_filter_coverage": RcFilterCoverageReport(
                status="COMPLETE", netlist_sha256=_REPORT_NETLIST_HASH
            ),
            "connector_coverage": ConnectorCoverageReport(
                status="COMPLETE",
                scope="Synthetic connector scope",
                inventory_review_basis="Synthetic independent inventory review",
                interface_catalog_sha256=catalog_hash,
            ),
            "connector_return_distribution": ConnectorReturnDistributionCoverageReport(
                status="COMPLETE",
                netlist_sha256=_REPORT_NETLIST_HASH,
                interface_catalog_sha256=catalog_hash,
            ),
        }
    )

    assert report.netlist_sha256 == _REPORT_NETLIST_HASH

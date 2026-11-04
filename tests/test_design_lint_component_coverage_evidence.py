"""Source binding for component-map evidence embedded in design-lint reports."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.connector_return_distribution_models import (
    ConnectorReturnDistributionCoverageReport,
)
from kicad_tooling.hwrepo.control_input_models import ControlInputBiasHeuristicCoverage
from kicad_tooling.hwrepo.crystal_network_models import CrystalNetworkCoverageReport
from kicad_tooling.hwrepo.design_lint_mapped_topology_models import DesignLintMappedCheckRun
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.digital_peer_voltage_models import DigitalPeerVoltageRuleCoverage
from kicad_tooling.hwrepo.i2c_address_models import I2cAddressCoverageReport
from kicad_tooling.hwrepo.i2c_pullup_models import I2cPullupHeuristicCoverage
from kicad_tooling.hwrepo.rc_filter_models import RcFilterCoverageReport
from kicad_tooling.hwrepo.regulator_feedback_models import RegulatorFeedbackCoverageReport
from tests.design_lint_evidence_fixtures import (
    crystal_coverage as _crystal_coverage,
)
from tests.design_lint_evidence_fixtures import (
    external_protection_coverage as _external_protection_coverage,
)
from tests.design_lint_evidence_fixtures import (
    rc_filter_coverage as _rc_filter_coverage,
)
from tests.design_lint_evidence_fixtures import (
    regulator_coverage as _regulator_coverage,
)

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
        *(
            (
                "external_protection_coverage",
                _external_protection_coverage(status, _STALE_NETLIST_HASH),
            )
            for status in ("COMPLETE", "INCOMPLETE", "UNDECLARED")
        ),
        (
            "crystal_network_coverage",
            _crystal_coverage(_STALE_NETLIST_HASH),
        ),
        (
            "regulator_feedback_coverage",
            _regulator_coverage(_STALE_NETLIST_HASH),
        ),
        (
            "rc_filter_coverage",
            _rc_filter_coverage(_STALE_NETLIST_HASH),
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
    with pytest.raises(
        ValueError,
        match="must use this report's native netlist|different or unavailable native netlist hash",
    ):
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


def test_peer_coverage_requires_a_top_level_report_netlist_digest() -> None:
    peer_coverage = DigitalPeerVoltageRuleCoverage(
        rule_id="bus.spi_peer_voltage_review",
        status="NO_SUPPORTED_ENDPOINTS",
        mode="review",
        netlist_sha256=_REPORT_NETLIST_HASH,
        authored_map_state="not_configured",
    )
    with pytest.raises(
        ValueError, match="Digital-peer voltage coverage must use this report's netlist"
    ):
        DesignLintReport.model_validate(
            {
                "status": "PASS",
                "project_id": "synthetic-source-evidence",
                "digital_peer_voltage_coverage": (peer_coverage,),
            }
        )


@pytest.mark.parametrize(
    ("field_name", "coverage"),
    (
        (
            "control_input_bias_coverage",
            ControlInputBiasHeuristicCoverage(
                status="COMPLETE", netlist_sha256=_REPORT_NETLIST_HASH
            ),
        ),
        (
            "i2c_pullup_heuristic_coverage",
            I2cPullupHeuristicCoverage(status="COMPLETE", netlist_sha256=_REPORT_NETLIST_HASH),
        ),
    ),
)
def test_report_rejects_other_evidence_with_missing_top_level_netlist_hash(
    field_name: str, coverage: object
) -> None:
    with pytest.raises(ValueError, match="coverage must use this report's native netlist"):
        DesignLintReport.model_validate(
            {
                "status": "PASS",
                "project_id": "synthetic-source-evidence",
                field_name: coverage,
            }
        )


def test_evaluated_mapped_check_requires_a_top_level_report_netlist_hash() -> None:
    run = DesignLintMappedCheckRun(
        rule_id="power.mapped_series_path_mismatch",
        status="EVALUATED",
        mode="review",
        map_sha256=_INTERFACE_CATALOG_HASH,
        netlist_sha256=_REPORT_NETLIST_HASH,
        requirement_count=1,
    )

    with pytest.raises(
        ValueError, match="Mapped-check execution coverage must use this report's native netlist"
    ):
        DesignLintReport.model_validate(
            {
                "status": "PASS",
                "project_id": "synthetic-source-evidence",
                "mapped_check_runs": (run,),
            }
        )


def test_report_accepts_component_coverage_bound_to_its_current_sources() -> None:
    catalog_hash = _INTERFACE_CATALOG_HASH
    report = DesignLintReport.model_validate(
        {
            "status": "PASS",
            "project_id": "synthetic-source-evidence",
            "netlist_sha256": _REPORT_NETLIST_HASH,
            "digital_peer_voltage_coverage": (
                DigitalPeerVoltageRuleCoverage(
                    rule_id="bus.spi_peer_voltage_review",
                    status="NO_SUPPORTED_ENDPOINTS",
                    mode="review",
                    netlist_sha256=_REPORT_NETLIST_HASH,
                    authored_map_state="not_configured",
                ),
            ),
            "i2c_address_coverage": I2cAddressCoverageReport(
                status="COMPLETE", netlist_sha256=_REPORT_NETLIST_HASH
            ),
            "crystal_network_coverage": CrystalNetworkCoverageReport(),
            "regulator_feedback_coverage": RegulatorFeedbackCoverageReport(),
            "rc_filter_coverage": RcFilterCoverageReport(),
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


def test_blocked_component_coverage_retains_its_original_netlist_identity() -> None:
    blocked = I2cAddressCoverageReport(
        status="BLOCKED",
        netlist_sha256=_STALE_NETLIST_HASH,
        issue="The supplied coverage uses an earlier native netlist",
    )

    report = DesignLintReport.model_validate(
        {
            "status": "BLOCKED",
            "project_id": "synthetic-source-evidence",
            "netlist_sha256": _REPORT_NETLIST_HASH,
            "i2c_address_coverage": blocked,
            "issues": (blocked.issue,),
        }
    )

    assert report.i2c_address_coverage.status == "BLOCKED"
    assert report.i2c_address_coverage.netlist_sha256 == _STALE_NETLIST_HASH

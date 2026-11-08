"""Digest-pinned native acceptance for generic connector SPI role triads."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel

from .ci_hosted_generic_connector_fixture_lane import generic_connector_fixture_lane
from .ci_hosted_spi_generic_connector_cases import (
    SPI_GENERIC_CONNECTOR_SOURCE_HASHES,
    spi_connector_role_map,
    spi_generic_connector_fixture_sources,
)
from .ci_hosted_support import HostedLog
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_policy_models import DesignLintPolicy
from .hwrepo.electrical import selected_config

RULE_ID = "bus.spi_generic_connector_triad_review"
RETURN_RULE_ID = "connector.spi_triad_without_return_review"


def spi_generic_connector_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export the SPI fault and named control with the exact KiCad image."""
    observations = generic_connector_fixture_lane(
        root,
        project=project,
        image=image,
        log=log,
        protocol="spi",
        rule_id=RULE_ID,
        source_hashes=SPI_GENERIC_CONNECTOR_SOURCE_HASHES,
        fixture_sources=spi_generic_connector_fixture_sources(),
        expected_subject="J1: generic pins match SPI clock and both data roles",
        expected_evidence=(
            (
                "other_connector_contacts",
                (
                    "J1.4 function=Pin_4 nets=AUX",
                    "J1.5 function=VCC nets=unassigned",
                ),
            ),
        ),
        role_evidence=(
            (
                "clock",
                "clock_net",
                "clock_generic_connector_pins",
                "U1.1",
                "J1.1",
            ),
            (
                "controller-to-peripheral data",
                "controller-to-peripheral data_net",
                "controller-to-peripheral data_generic_connector_pins",
                "U1.2",
                "J1.2",
            ),
            (
                "peripheral-to-controller data",
                "peripheral-to-controller data_net",
                "peripheral-to-controller data_generic_connector_pins",
                "U1.3",
                "J1.3",
            ),
        ),
    )
    observed = observations["fault"]
    normalized = json.dumps(
        BaseModel.model_dump(observed, mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    netlist_hash = hashlib.sha256(normalized).hexdigest()
    config = selected_config(root, project)
    for case, has_return_role in (("fault", False), ("control", True)):
        coverage = spi_connector_role_map(observed, has_return_role=has_return_role)
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=f"synthetic-native-spi-return-{project}-{case}",
            observed=observed,
            netlist_sha256=netlist_hash,
        )
        report = evaluate(coach.project_id, coach, DesignLintPolicy(), coverage)
        findings = tuple(item for item in report.findings if item.rule_id == RETURN_RULE_ID)
        expected_count = 1 if case == "fault" else 0
        if len(findings) != expected_count:
            raise ValueError(
                f"Native SPI return {case} expected {expected_count} review(s), got {len(findings)}"
            )
        if findings and findings[0].evidence.get("connector") != ("J1",):
            raise ValueError("Native SPI return review omitted the exact connector reference")
        log.event(
            f"generic-connector/spi/return/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=image,
            source_sha256=SPI_GENERIC_CONNECTOR_SOURCE_HASHES["fault"],
            normalized_netlist_sha256=netlist_hash,
            return_role_mapped=has_return_role,
            finding_count=len(findings),
        )

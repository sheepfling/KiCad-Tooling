"""Validate native contact rating fixture evidence and controls."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from .ci_hosted_component_rating_context import ComponentRatingFixtureContext
from .hwrepo.contracts import read_kicad_erc_report
from .hwrepo.evidence import digest
from .validate import read_netlist

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


from .hwrepo.connector_contact_rating_models import (
    ConnectorContactCurrentRequirement,
    ConnectorContactRatingAnalysis,
    ConnectorContactRatingRequirement,
)
from .hwrepo.connector_contact_ratings import connector_contact_rating_checks
from .hwrepo.models import (
    NetlistContract,
)


def verify_connector_contact_rating_fixture(
    context: ComponentRatingFixtureContext, log: HostedLog
) -> None:
    root = context.root
    project = context.project
    config = context.config
    pinned = context.pinned
    contact_fixture = context.contact_fixture
    contact_fixture_sha256 = context.contact_fixture_sha256
    scratch = context.scratch
    output = context.output
    contact_parsed: dict[str, NetlistContract] = {}
    contact_normalized_hashes: dict[str, str] = {}
    contact_erc_hashes: dict[str, str] = {}
    contact_erc_types: dict[str, tuple[tuple[str, str], ...]] = {}
    for run in ("first", "repeat"):
        netlist_path = output / f"contact.{run}.netlist.xml"
        erc_path = output / f"contact.{run}.erc.json"
        if not netlist_path.is_file() or not erc_path.is_file():
            raise ValueError(
                "Native connector contact-rating fixture omitted a repeated export or ERC"
            )
        observed_contact = read_netlist(netlist_path)
        normalized = json.dumps(
            observed_contact.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        contact_normalized_hashes[run] = hashlib.sha256(normalized).hexdigest()
        contact_parsed[run] = observed_contact
        erc_report = read_kicad_erc_report(erc_path)
        if erc_report.kicad_version != config.kicad_version:
            raise ValueError(
                "Native connector contact-rating ERC version differs from its pinned KiCad version"
            )
        contact_erc_types[run] = tuple(
            sorted((item.type, item.severity) for item in erc_report.violations)
        )
        errors = tuple(item for item in contact_erc_types[run] if item[1] == "error")
        if errors:
            raise ValueError(f"Synthetic contact-rating schematic has native ERC errors: {errors}")
        contact_erc_hashes[run] = hashlib.sha256(
            json.dumps(contact_erc_types[run], separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
    if contact_normalized_hashes["first"] != contact_normalized_hashes["repeat"]:
        raise ValueError("Native connector contact-rating exports differ after normalization")
    if contact_erc_hashes["first"] != contact_erc_hashes["repeat"]:
        raise ValueError("Native connector contact-rating ERC results differ after normalization")

    contact_observed = contact_parsed["first"]

    def contact_check(maximum_expected_current_a: float) -> tuple[str, tuple[str, ...]]:
        contact = ConnectorContactCurrentRequirement(
            id="contact-current",
            pin_number="1",
            expected_function="Pin_1",
            expected_net="CONTACT_CURRENT",
            rated_current_a=3.0,
            derated_allowable_current_a=2.0,
            maximum_expected_current_a=maximum_expected_current_a,
            maximum_utilization_fraction=0.8,
            rating_source="Synthetic connector specification, contact-current table",
            rating_conditions="Synthetic 20 C ambient, two loaded contacts, stated wire gauge",
            derating_basis="Synthetic project review for the stated test conditions",
            load_basis="Synthetic maximum DC load assigned to this individual contact",
        )
        requirement = ConnectorContactRatingRequirement(
            id="host-connector",
            reference="J1",
            expected_symbol="Connector_Generic:Conn_01x02",
            expected_footprint="Synthetic:Header_1x02",
            expected_part_id="SYNTHETIC-HEADER-2P-3A",
            native_pin_numbers=("1", "2"),
            contacts=(contact,),
        )
        spec = ConnectorContactRatingAnalysis(
            basis="Synthetic per-contact connector current comparison",
            requirements=(requirement,),
        )
        checks = connector_contact_rating_checks(spec, contact_observed)
        margin = next(item for item in checks if item.id.endswith("/utilization"))
        unexpected = tuple(
            item.id
            for item in checks
            if not item.id.endswith("/utilization") and item.status != "PASS"
        )
        if unexpected:
            raise ValueError(f"Native contact identity and pin map did not pass: {unexpected}")
        return margin.status, tuple(item.id for item in checks if item.status != "PASS")

    contact_control_status, contact_control_open = contact_check(1.6)
    contact_fault_status, contact_fault_open = contact_check(1.61)
    if contact_control_status != "PASS" or contact_control_open:
        raise ValueError("Native connector contact-rating equality control did not pass")
    if contact_fault_status != "FAIL" or len(contact_fault_open) != 1:
        raise ValueError("Native connector contact over-utilization fault was not detected")

    contact_receipt = (scratch / "native.command.json").relative_to(root).as_posix()
    log.event(
        "connector-contact-rating-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        fixture_sha256=contact_fixture_sha256,
        first_netlist_sha256=digest(output / "contact.first.netlist.xml"),
        repeat_netlist_sha256=digest(output / "contact.repeat.netlist.xml"),
        normalized_netlist_sha256=contact_normalized_hashes["first"],
        repeat_normalized_netlist_sha256=contact_normalized_hashes["repeat"],
        normalized_erc_sha256=contact_erc_hashes["first"],
        repeat_normalized_erc_sha256=contact_erc_hashes["repeat"],
        native_erc_types=";".join(
            f"{kind}:{severity}" for kind, severity in contact_erc_types["first"]
        )
        or "none",
        native_erc_error_types="none",
        repeatable="true",
        repeatability_basis="normalized_netlist_and_erc_types",
        command_receipt=contact_receipt,
    )
    for case, maximum_current_a, status in (
        ("control", 1.6, contact_control_status),
        ("over-limit-fault", 1.61, contact_fault_status),
    ):
        log.event(
            f"connector-contact-rating-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            fixture_sha256=contact_fixture_sha256,
            normalized_netlist_sha256=contact_normalized_hashes["first"],
            normalized_erc_sha256=contact_erc_hashes["first"],
            native_erc_error_types="none",
            maximum_expected_current_a=maximum_current_a,
            utilization_status=status,
            repeatable="true",
        )
    if digest(contact_fixture) != contact_fixture_sha256:
        raise ValueError("Synthetic connector contact-rating fixture changed during native export")

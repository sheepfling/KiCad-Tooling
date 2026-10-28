"""Source-bound native review gate for returns across peer connector types."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import MappingProxyType

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog, normalized_erc_report_bytes, tooling_checkout_root
from .hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from .hwrepo.connector_coverage_models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    ConnectorReviewsDocument,
)
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_kicad_erc_report, read_model, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.evidence import digest
from .hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    InterfacesCatalog,
    NetlistContract,
)
from .validate import read_netlist

MIXED_INTERFACE_RETURN_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
_RULE_ID = "connector.repeated_pin_function"
_SCOPE_RULE_ID = "connector.return_supply_scope_singleton"
_FIXTURE_RELATIVE_ROOT = Path("tests/fixtures/design_lint/mixed-interface-return-peers")
_SOURCE_HASHES = MappingProxyType(
    {
        "fault": "53af59844b37ac7181a99e22a5bc14cd868ef33083361590cd627e8907e3fb83",
        "control": "b0731cac3cba8b946e905a41f2f9251c459573f699d2c2990b2574c4ba7f5c45",
    }
)
_INTERFACE_SHA256 = "e1216ee351d3fcdddd720f2bc6f0e2068bbc9d85e777aa4914c4af8102cb8b99"
_CONNECTOR_REVIEWS_SHA256 = "a1ec6317ef6207572c89605a5c0ef1448fe7e5a62b2ec5383edea598dda2d0bc"
_SEPARATE_RETURN_REVIEWS_SHA256 = "fcbebe5c7c83a15d82daf1ae43c25f461bcd3809b4e9c02f4eaca1a0c8ae3329"


def _connector_reviews(
    path: Path,
) -> tuple[tuple[str, ...], tuple[ConnectorInterfaceReview, ...], ConnectorInventoryReview]:
    source = read_model(path, ConnectorReviewsDocument)
    reviews = source.connector_reviews
    inventory = source.inventory_review
    interface_ids = tuple(sorted({item.interface_id for item in reviews if item.interface_id}))
    return interface_ids, reviews, inventory


def _normalized_sha256(value: NetlistContract) -> str:
    normalized = json.dumps(
        value.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def mixed_interface_return_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native exports and map-evaluated fault/control returns across USB and serial peers."""
    root = root.resolve()
    if (version, image) not in MIXED_INTERFACE_RETURN_TOOLCHAINS:
        raise ValueError(f"Mixed-interface return fixtures do not cover KiCad {version}")
    pinned = pinned_image(image)
    fixture_root = tooling_checkout_root() / _FIXTURE_RELATIVE_ROOT
    sources = {case: fixture_root / f"{case}.kicad_sch" for case in ("fault", "control")}
    source_hashes = MappingProxyType({case: digest(source) for case, source in sources.items()})
    if source_hashes != _SOURCE_HASHES:
        raise ValueError("Mixed-interface return sources differ from the reviewed hashes")
    interfaces_path = fixture_root / "interfaces.json"
    reviews_path = fixture_root / "connector-reviews.json"
    separate_return_reviews_path = fixture_root / "connector-reviews-separate-return-groups.json"
    interface_sha256 = digest(interfaces_path)
    reviews_sha256 = digest(reviews_path)
    separate_return_reviews_sha256 = digest(separate_return_reviews_path)
    if (
        interface_sha256 != _INTERFACE_SHA256
        or reviews_sha256 != _CONNECTOR_REVIEWS_SHA256
        or separate_return_reviews_sha256 != _SEPARATE_RETURN_REVIEWS_SHA256
    ):
        raise ValueError("Mixed-interface connector maps differ from the reviewed hashes")
    interfaces_model = InterfacesCatalog.model_validate_json(
        interfaces_path.read_text(encoding="utf-8")
    )
    interfaces = {item.id: item for item in interfaces_model.interfaces}
    project_interfaces, connector_reviews, inventory_review = _connector_reviews(reviews_path)
    scoped_interfaces, scoped_reviews, scoped_inventory_review = _connector_reviews(
        separate_return_reviews_path
    )
    if scoped_interfaces != project_interfaces or scoped_inventory_review != inventory_review:
        raise ValueError("Separate return scopes changed the reviewed interface inventory")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"mixed-interface-returns-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    output = scratch / "output"
    output.mkdir()
    for case, source in sources.items():
        shutil.copyfile(source, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic {case} source changed while preparing native input")

    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{version}"\n'
        "for case in fault control; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/$case.$run.netlist.xml" "/fixtures/$case.kicad_sch"\n'
        "    kicad-cli sch erc --format json --severity-all "
        '      --output "/output/$case.$run.erc.json" "/fixtures/$case.kicad_sch"\n'
        "  done\n"
        "done\n"
    )
    argv = (
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",
        *user,
        "-e",
        "HOME=/tmp/kicad-mixed-interface-returns",
        "-v",
        f"{inputs}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        script,
    )
    log.event(
        "mixed-interface-return-fixture/native-export",
        "START",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(
            f"Native mixed-interface return export failed: {command.stderr or command.error}"
        )

    expected_nets = {
        "fault": {
            "USB1_D+": ("J1.1",),
            "USB1_D-": ("J1.2",),
            "SERIAL_TX": ("J2.1",),
            "SERIAL_RX": ("J2.2",),
            "COMMON_RETURN": ("J1.3", "J2.3"),
            "USB2_D+": ("J3.1",),
            "USB2_D-": ("J3.2",),
            "USB2_RETURN": ("J3.3",),
        },
        "control": {
            "USB1_D+": ("J1.1",),
            "USB1_D-": ("J1.2",),
            "SERIAL_TX": ("J2.1",),
            "SERIAL_RX": ("J2.2",),
            "COMMON_RETURN": ("J1.3", "J2.3", "J3.3"),
            "USB2_D+": ("J3.1",),
            "USB2_D-": ("J3.2",),
        },
    }
    normalized_hashes: dict[tuple[str, str], str] = {}
    erc_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    coverage_statuses: dict[str, str] = {}
    observations: dict[str, NetlistContract] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted mixed-interface {case} evidence")
            observed = read_netlist(netlist_path)
            observations[case] = observed
            if observed.component_pin_numbers.get("J1") != ("1", "2", "3"):
                raise ValueError("Native USB1 connector pin inventory changed")
            if observed.component_pin_numbers.get("J2") != ("1", "2", "3"):
                raise ValueError("Native serial connector pin inventory changed")
            if observed.component_pin_numbers.get("J3") != ("1", "2", "3"):
                raise ValueError("Native USB2 connector pin inventory changed")
            if observed.pin_functions.get("J2.3") != "Pin_3":
                raise ValueError("Native serial return pin lost its generic function marker")
            actual_nets = {name: observed.nets.get(name) for name in expected_nets[case]}
            if actual_nets != expected_nets[case]:
                raise ValueError(
                    f"Native mixed-interface {case} assignments changed: "
                    f"expected={expected_nets[case]!r}, actual={actual_nets!r}"
                )
            normalized_hashes[case, run] = _normalized_sha256(observed)
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version or any(
                item.severity == "error" for item in erc.violations
            ):
                raise ValueError(f"Native ERC reported errors for mixed-interface {case}")
            erc_hashes[case, run] = hashlib.sha256(normalized_erc_report_bytes(erc)).hexdigest()
            coverage = evaluate_connector_coverage(
                observed,
                project_interfaces,
                connector_reviews,
                interfaces=interfaces,
                interface_catalog_path=interfaces_path.relative_to(root).as_posix(),
                interface_catalog_sha256=interface_sha256,
                inventory_review=inventory_review,
            )
            if coverage.status != "COMPLETE" or any(
                item.status != "COVERED" for item in coverage.entries
            ):
                raise ValueError(f"Mapped connector coverage is incomplete for {case}")
            coverage_statuses[case] = coverage.status
            project_id = f"synthetic-mixed-interface-return-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=digest(netlist_path),
            )
            reports[case, run] = evaluate(
                project_id,
                coach,
                DesignLintPolicy(),
                connector_coverage=coverage,
            )

    for case in sources:
        if normalized_hashes[case, "first"] != normalized_hashes[case, "repeat"]:
            raise ValueError(f"Native mixed-interface {case} netlist export is not repeatable")
        if erc_hashes[case, "first"] != erc_hashes[case, "repeat"]:
            raise ValueError(f"Native mixed-interface {case} ERC export is not repeatable")
        target_findings = tuple(
            item for item in reports[case, "first"].findings if item.rule_id == _RULE_ID
        )
        scope_findings = tuple(
            item for item in reports[case, "first"].findings if item.rule_id == _SCOPE_RULE_ID
        )
        if case == "fault":
            if len(target_findings) != 1 or target_findings[0].mode != "review":
                raise ValueError("Split mixed-interface returns lost their review finding")
            expected_return_assignments = {
                "J1.3": ("COMMON_RETURN",),
                "J2.3": ("COMMON_RETURN",),
                "J3.3": ("USB2_RETURN",),
            }
            if any(
                target_findings[0].evidence.get(pin) != nets
                for pin, nets in expected_return_assignments.items()
            ):
                raise ValueError("Mixed-interface return review lost exact native pin evidence")
            if (
                target_findings[0].evidence.get("return_comparison_group") != ("external-returns",)
                or len(target_findings[0].evidence.get("return_comparison_basis", ())) != 3
            ):
                raise ValueError("Mixed-interface return review lost reviewed scope evidence")
            if scope_findings:
                raise ValueError(
                    "One shared return-comparison scope should retain all connector peers"
                )
        elif target_findings:
            raise ValueError("Common mixed-interface return control retained a review finding")
        elif scope_findings:
            raise ValueError("Common return control retained a singleton-scope finding")
        log.event(
            f"mixed-interface-return-fixture/{case}",
            "PASS",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            source_sha256=source_hashes[case],
            interface_catalog_sha256=interface_sha256,
            connector_reviews_sha256=reviews_sha256,
            normalized_netlist_sha256=normalized_hashes[case, "first"],
            repeat_normalized_netlist_sha256=normalized_hashes[case, "repeat"],
            normalized_erc_sha256=erc_hashes[case, "first"],
            repeat_normalized_erc_sha256=erc_hashes[case, "repeat"],
            connector_coverage=coverage_statuses[case],
            findings=";".join(item.subject for item in target_findings) or "none",
            erc_errors="none",
            repeatable="true",
        )
    scoped_coverage = evaluate_connector_coverage(
        observations["fault"],
        scoped_interfaces,
        scoped_reviews,
        interfaces=interfaces,
        interface_catalog_path=interfaces_path.relative_to(root).as_posix(),
        interface_catalog_sha256=interface_sha256,
        inventory_review=scoped_inventory_review,
    )
    if scoped_coverage.status != "COMPLETE" or any(
        item.status != "COVERED" for item in scoped_coverage.entries
    ):
        raise ValueError("Separate return comparison coverage is incomplete")
    scoped_report = evaluate(
        "synthetic-mixed-interface-separate-return-scopes",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-mixed-interface-separate-return-scopes",
            observed=observations["fault"],
            netlist_sha256=normalized_hashes["fault", "first"],
        ),
        DesignLintPolicy(),
        connector_coverage=scoped_coverage,
    )
    scoped_findings = tuple(item for item in scoped_report.findings if item.rule_id == _RULE_ID)
    if scoped_findings:
        raise ValueError("Separate source-reviewed return scopes retained a cross-group prompt")
    singleton_scope_findings = tuple(
        item for item in scoped_report.findings if item.rule_id == _SCOPE_RULE_ID
    )
    if len(singleton_scope_findings) != 1 or singleton_scope_findings[0].evidence.get(
        "isolated_references"
    ) != ("J3",):
        raise ValueError("Singleton reviewed return scope did not produce its coverage prompt")
    log.event(
        "mixed-interface-return-fixture/separate-scope-control",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        interface_catalog_sha256=interface_sha256,
        connector_reviews_sha256=separate_return_reviews_sha256,
        native_source_case="fault",
        native_source_sha256=_SOURCE_HASHES["fault"],
        normalized_netlist_sha256=normalized_hashes["fault", "first"],
        connector_coverage=scoped_coverage.status,
        findings="none",
        scope_findings=";".join(item.rule_id for item in singleton_scope_findings),
        isolated_references=";".join(singleton_scope_findings[0].evidence["isolated_references"]),
    )
    log.event(
        "mixed-interface-return-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        source_hashes=",".join(f"{key}:{value}" for key, value in source_hashes.items()),
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()

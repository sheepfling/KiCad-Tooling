"""Reviewed supplier payloads with durable, single-attempt external submissions.

Preparation is entirely local. Submission discloses the reviewed BOM to DigiKey
for an external review list; it never purchases parts or retries an uncertain POST.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from pydantic import TypeAdapter

from . import digikey_handoff
from .contract_coach import project_context
from .contracts import parse_model_text, read_model, repo_path, write_model
from .discovery import load_registry
from .evidence import digest
from .mcp_files import read_regular_bytes
from .mcp_workflow import artifact_file, selected_project
from .models import (
    Digest,
    DigiKeyHandoffPayload,
    PartsCatalog,
    PurchasingReport,
    SupplierHandoffPlan,
    SupplierHandoffReport,
)
from .parts_workflow import input_hashes, preferences_path
from .purchasing import plan as purchasing_plan
from .purchasing import read_components

_DIGEST: TypeAdapter[str] = TypeAdapter(Digest)
_MAX_DOCUMENT = 2 * 1024 * 1024


def _artifact(root: Path, value: str) -> Path:
    path = artifact_file(root, value)
    if path.suffix != ".json" or path.stat().st_size > _MAX_DOCUMENT:
        raise ValueError("Select a JSON review artifact no larger than 2 MiB")
    return path


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _payload_digest(payload: DigiKeyHandoffPayload) -> str:
    content = payload.model_dump_json(by_alias=True).encode("utf-8")
    if len(content) > 1_048_576:
        raise ValueError("This BOM exceeds the supplier's 1 MiB handoff limit")
    return hashlib.sha256(content).hexdigest()


def _current(root: Path, expected: dict[str, str | None]) -> None:
    for name, expected_hash in expected.items():
        path = repo_path(root, name)
        if expected_hash is None:
            if path.exists():
                raise ValueError(f"{name} appeared after the review; prepare a fresh handoff")
        elif not path.is_file() or digest(path) != expected_hash:
            raise ValueError(f"{name} changed after the review; prepare a fresh handoff")


def _order(root: Path, project_id: str, path: Path, expected_sha256: str | None = None) -> tuple[PurchasingReport, str]:
    """Recheck actual saved evidence and recompute the purchasing projection."""
    project = selected_project(root, project_id)
    content, _ = read_regular_bytes(path, maximum=_MAX_DOCUMENT)
    observed_sha256 = hashlib.sha256(content).hexdigest()
    if expected_sha256 is not None and observed_sha256 != expected_sha256:
        raise ValueError("Parts review changed since handoff preparation")
    report = parse_model_text(content.decode("utf-8"), PurchasingReport)
    if report.project_id != project_id:
        raise ValueError("Parts review belongs to a different project")
    if (report.status != "READY_FOR_ORDER_REVIEW" or report.plan is None
            or report.evidence is None or report.evidence.status != "READY_FOR_REVIEW"
            or report.netlist_sha256 is None):
        raise ValueError("Complete a source-bound parts review before preparing a supplier handoff")
    _, _, current_source = project_context(root, project_id)
    if (current_source != report.source_hashes
            or report.evidence.source_hashes != report.source_hashes
            or report.evidence.netlist_sha256 != report.netlist_sha256
            or report.evidence.native_status != report.native_status):
        raise ValueError("Parts evidence changed or does not match the current project")
    # A review can use an explicit preferences file. Require the common policy
    # inputs and verify every recorded input, without guessing which preferences
    # source supplied its separately retained, explicitly reviewed quantities.
    required = set(input_hashes(root, project_id, None))
    required.discard(_relative(root, preferences_path(root, project_id, None)))
    if not required.issubset(report.input_hashes):
        raise ValueError("Parts review is missing required policy input hashes")
    _current(root, dict(report.input_hashes))
    netlist = artifact_file(root, _relative(root, path.parent / "netlist.xml"))
    if digest(netlist) != report.netlist_sha256:
        raise ValueError("Parts netlist changed; prepare a fresh parts review")
    registry = load_registry(root)
    catalog = read_model(repo_path(root, registry.catalogs.parts), PartsCatalog)
    recalculated = purchasing_plan(
        read_components(netlist), catalog, report.plan.preferences, project.component_identity.part_ids,
    )
    if recalculated != report.plan:
        raise ValueError("Parts review differs from its current netlist and catalog")
    return report, observed_sha256


def prepare_supplier_handoff(
    root: Path, project_id: str, parts_report: str, output: Path,
) -> SupplierHandoffReport:
    """Retain the exact source-bound payload for review, without contacting a supplier."""
    root = root.resolve()
    report_path = _artifact(root, parts_report)
    report, report_sha = _order(root, project_id, report_path)
    assert report.plan is not None
    payload = digikey_handoff.build_payload(report.plan)
    payload_sha = _payload_digest(payload)
    conditions: dict[str, str | None] = dict(report.input_hashes)
    conditions.update(input_hashes(root, project_id, None))
    default_preferences = preferences_path(root, project_id, None)
    conditions.setdefault(_relative(root, default_preferences), None)
    conditions[parts_report] = report_sha
    conditions[_relative(root, report_path.parent / "netlist.xml")] = report.netlist_sha256
    _current(root, conditions)
    _, _, current_source = project_context(root, project_id)
    if current_source != report.source_hashes:
        raise ValueError("Project source changed during handoff preparation")
    output = repo_path(root, _relative(root, output))
    if (not output.is_relative_to(root / "build") or output == root / "build"
            or (output.exists() and (not output.is_dir() or any(output.iterdir())))):
        raise ValueError("Supplier preparation needs a fresh empty receipt below build/")
    output.mkdir(parents=True, exist_ok=True)
    handoff = output / "handoff.json"
    spec = SupplierHandoffPlan(
        project_id=project_id, parts_report=parts_report, report_sha256=report_sha,
        payload=payload, payload_sha256=payload_sha, source_hashes=report.source_hashes,
        preconditions=conditions,
    )
    write_model(handoff, spec)
    # A separate wire JSON makes the external disclosure directly inspectable.
    (output / "payload.json").write_bytes(payload.model_dump_json(by_alias=True).encode("utf-8"))
    result = SupplierHandoffReport(
        status="PREPARED", project_id=project_id, handoff=_relative(root, handoff),
        handoff_sha256=digest(handoff), payload_sha256=payload_sha,
    )
    write_model(output / "report.json", result)
    return result


def _validate_handoff(
    root: Path, path: Path, expected_sha256: str,
) -> SupplierHandoffPlan:
    content, _ = read_regular_bytes(path, maximum=_MAX_DOCUMENT)
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError("Supplier handoff changed; inspect it and use its current SHA-256")
    spec = parse_model_text(content.decode("utf-8"), SupplierHandoffPlan)
    report_path = _artifact(root, spec.parts_report)
    report, _ = _order(root, spec.project_id, report_path, spec.report_sha256)
    if report.source_hashes != spec.source_hashes:
        raise ValueError("Supplier handoff source differs from the parts review")
    assert report.plan is not None
    if (digikey_handoff.build_payload(report.plan) != spec.payload
            or _payload_digest(spec.payload) != spec.payload_sha256):
        raise ValueError("Supplier payload differs from the reviewed parts projection")
    _current(root, dict(spec.preconditions))
    if digest(path) != expected_sha256:
        raise ValueError("Supplier handoff changed while being checked")
    return spec


def _sync_directory(path: Path) -> None:
    # POSIX directory fsync retains the new marker name as well as its contents.
    # Windows has no portable directory descriptor; the file itself is flushed.
    if os.name == "posix":
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _finish(path: Path, result: SupplierHandoffReport) -> None:
    # An initial UNCERTAIN receipt already exists. An interrupted replacement
    # leaves that durable no-retry marker intact.
    descriptor, temporary = tempfile.mkstemp(prefix=".handoff-", dir=path.parent)
    staged = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(result.model_dump_json(indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, path)
        _sync_directory(path.parent)
    finally:
        staged.unlink(missing_ok=True)


def submit_supplier_handoff(
    root: Path, handoff: str, expected_sha256: str,
) -> SupplierHandoffReport:
    """Submit the exact reviewed payload once; retain uncertain delivery without retry."""
    root = root.resolve()
    expected_sha256 = _DIGEST.validate_python(expected_sha256, strict=True)
    path = _artifact(root, handoff)
    spec = _validate_handoff(root, path, expected_sha256)
    parent = repo_path(root, "build/supplier-submissions")
    parent.mkdir(parents=True, exist_ok=True)
    receipt = repo_path(root, f"build/supplier-submissions/{expected_sha256}.json")
    initial = SupplierHandoffReport(
        status="UNCERTAIN", project_id=spec.project_id, handoff=handoff,
        handoff_sha256=expected_sha256, payload_sha256=spec.payload_sha256,
        attempt_receipt=_relative(root, receipt),
        issues=(("An external submission attempt was reserved. Delivery is unconfirmed; "
                 "check DigiKey before preparing a new review. This handoff will not retry."),),
    )
    try:
        # Exclusive creation serializes independent processes and copied handles.
        with receipt.open("x", encoding="utf-8") as stream:
            stream.write(initial.model_dump_json(indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        _sync_directory(parent)
    except FileExistsError:
        previous_bytes, _ = read_regular_bytes(_artifact(root, _relative(root, receipt)), maximum=_MAX_DOCUMENT)
        previous = parse_model_text(previous_bytes.decode("utf-8"), SupplierHandoffReport)
        if (previous.handoff_sha256 != expected_sha256
                or previous.payload_sha256 != spec.payload_sha256
                or previous.project_id != spec.project_id
                or previous.attempt_receipt != _relative(root, receipt)):

            raise ValueError("Supplier attempt receipt does not match this reviewed handoff") from None
        return previous.model_copy(update={"handoff": handoff})
    try:
        # Check again after reserving the durable attempt; failed preconditions
        # intentionally consume it instead of risking an ambiguous later retry.
        _validate_handoff(root, path, expected_sha256)
        reply = digikey_handoff.send(spec.payload, list_name=spec.project_id)
        result = initial.model_copy(update={"status": "SENT", "single_use_url": reply.single_use_url,
                                            "issues": ()})
    except (OSError, ValueError) as error:
        result = initial.model_copy(update={"issues": (str(error), initial.issues[0])})
    try:
        _validate_handoff(root, path, expected_sha256)
    except (OSError, ValueError) as error:
        result = result.model_copy(update={"status": "BLOCKED", "issues": (
            str(error), ("DigiKey may already have received the earlier BOM; it no longer "
                         "represents the current reviewed source. No automatic retry was made."),
        )})
    _finish(receipt, result)
    return result

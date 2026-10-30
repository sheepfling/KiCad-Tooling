"""Review one saved measured-voltage channel against project-authored limits."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

from pydantic import BaseModel

from .artifact_access import read_regular_bytes
from .contract_coach import receipt_directory
from .contracts import parse_model_text, repo_path, write_model
from .evidence import digest
from .measured_series import (
    MAX_SOURCE_BYTES,
    parse_measured_samples,
)
from .measured_series_models import MeasuredSeriesReport
from .measured_series_receipts import (
    RETAINED_MEASUREMENT_ARTIFACTS,
    measured_artifact_issues,
    read_measured_receipt,
)
from .physical_voltage_html import render_physical_voltage
from .physical_voltage_models import (
    PhysicalVoltageReviewReport,
    RequirementState,
    VoltageCapture,
    VoltageRequirement,
    VoltageViolation,
)
from .project_source_access import project_owned_source_path

Model = TypeVar("Model", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class VoltageInputs:
    measured_path: Path
    measured_sha256: str
    measured: MeasuredSeriesReport
    capture_path: Path
    capture_sha256: str
    capture: VoltageCapture
    requirement_path: Path | None
    requirement_sha256: str | None
    requirement_state: RequirementState
    requirement: VoltageRequirement | None
    source_current: bool
    artifact_issues: tuple[str, ...]
    times: tuple[Decimal, ...]
    values: tuple[Decimal, ...]
    issues: tuple[str, ...]


def _read_project_model(
    root: Path, project_id: str, selected: Path, model: type[Model]
) -> tuple[Path, str, Model]:
    path, _ = project_owned_source_path(root, project_id, selected, ".json")
    raw, _ = read_regular_bytes(path, maximum=1024 * 1024)
    return path, hashlib.sha256(raw).hexdigest(), parse_model_text(raw.decode("utf-8"), model)


def _requirement(
    root: Path, project_id: str, selected: Path | None
) -> tuple[Path | None, str | None, RequirementState, VoltageRequirement | None, tuple[str, ...]]:
    if selected is None:
        return None, None, "NOT_SELECTED", None, ("No requirement was selected.",)
    path, _ = project_owned_source_path(root, project_id, selected, ".json", require_existing=False)
    if not path.is_file():
        return path, None, "MISSING", None, ("Selected requirement file is missing.",)
    raw, _ = read_regular_bytes(path, maximum=1024 * 1024)
    checksum = hashlib.sha256(raw).hexdigest()
    try:
        requirement = parse_model_text(raw.decode("utf-8"), VoltageRequirement)
    except (UnicodeDecodeError, ValueError) as exc:
        return path, checksum, "INVALID", None, (f"Requirement is invalid: {exc}",)
    return path, checksum, "CURRENT", requirement, ()


def _load_inputs(
    root: Path,
    project_id: str,
    measured_receipt: Path,
    capture_file: Path,
    requirement_file: Path | None,
) -> VoltageInputs:
    selected, measured, measured_sha = read_measured_receipt(root, project_id, measured_receipt)
    capture_path, capture_sha, capture = _read_project_model(
        root, project_id, capture_file, VoltageCapture
    )
    if capture.project_id != project_id:
        raise ValueError("Capture context identifies a different project")
    req_path, req_sha, req_state, requirement, req_issues = _requirement(
        root, project_id, requirement_file
    )
    issues: list[str] = list(req_issues)
    if requirement is not None and requirement.project_id != project_id:
        issues.append("Requirement identifies a different project.")
        requirement = None
        req_state = "INVALID"
    source_current = False
    try:
        source, _ = project_owned_source_path(root, project_id, Path(capture.source_csv), ".csv")
        raw_current, _ = read_regular_bytes(source, maximum=MAX_SOURCE_BYTES)
        source_current = hashlib.sha256(raw_current).hexdigest() == capture.source_sha256
    except (OSError, ValueError):
        pass
    if not source_current:
        issues.append("Project-owned measurement CSV is missing or differs from the capture hash.")
    if measured.source != capture.source_csv or measured.source_sha256 != capture.source_sha256:
        issues.append("Measured receipt source identity differs from the capture context.")
    artifact_issues = measured_artifact_issues(selected, measured)
    issues.extend(artifact_issues)
    if measured.status != "PASS":
        issues.append("Measured-series import did not pass; inspect its retained errors.")
    times: tuple[Decimal, ...] = ()
    values: tuple[Decimal, ...] = ()
    if measured.status == "PASS" and not artifact_issues:
        try:
            raw_saved, _ = read_regular_bytes(
                selected.parent / "source.csv", maximum=MAX_SOURCE_BYTES
            )
            all_times, groups = parse_measured_samples(
                raw_saved, measured.time_column, measured.time_unit, measured.channels
            )
            matches = [
                index
                for index, channel in enumerate(measured.channels)
                if channel.column == capture.channel
            ]
            if not matches:
                issues.append("Capture channel is absent from the selected measured receipt.")
            else:
                times = all_times
                values = groups[matches[0]]
            if measured.samples != len(all_times):
                issues.append("Measured receipt sample count differs from retained source CSV.")
                artifact_issues = (*artifact_issues, "Retained sample count mismatch.")
        except (OSError, ValueError) as exc:
            issues.append(f"Retained measurement source could not be parsed: {exc}")
            artifact_issues = (*artifact_issues, "Retained source parse failed.")
    return VoltageInputs(
        measured_path=selected,
        measured_sha256=measured_sha,
        measured=measured,
        capture_path=capture_path,
        capture_sha256=capture_sha,
        capture=capture,
        requirement_path=req_path,
        requirement_sha256=req_sha,
        requirement_state=req_state,
        requirement=requirement,
        source_current=source_current,
        artifact_issues=artifact_issues,
        times=times,
        values=values,
        issues=tuple(issues),
    )


def _evaluate(root: Path, directory: Path, inputs: VoltageInputs) -> PhysicalVoltageReviewReport:
    measured, capture, requirement = inputs.measured, inputs.capture, inputs.requirement
    issues = list(inputs.issues)
    measured_unit = next(
        (channel.unit for channel in measured.channels if channel.column == capture.channel),
        None,
    )
    source_matches = (
        measured.source == capture.source_csv and measured.source_sha256 == capture.source_sha256
    )
    if not inputs.source_current or not source_matches or inputs.artifact_issues:
        status = "STALE"
    elif measured.status != "PASS" or not inputs.values or capture.kind != "voltage_envelope":
        status = "UNSUPPORTED"
        if capture.kind != "voltage_envelope":
            issues.append(f"Measurement kind {capture.kind!r} has no voltage-envelope review.")
    elif requirement is None or requirement.limit is None:
        status = "NO_LIMIT"
        if requirement is not None:
            issues.append("Requirement has no authored voltage limit.")
    elif (
        requirement.kind != "voltage_envelope"
        or requirement.test_id != capture.test_id
        or requirement.channel != capture.channel
    ):
        status = "NO_LIMIT"
        issues.append("Selected requirement does not cover this test and channel.")
    elif capture.unit != "V" or requirement.unit != "V" or measured_unit != "V":
        status = "UNIT_MISMATCH"
        issues.append(
            "Capture, measured channel, and requirement must all declare V; no unit conversion is inferred."
        )
    elif dict(capture.conditions) != dict(requirement.conditions):
        status = "CONDITION_MISMATCH"
        issues.append("Capture conditions differ from the authored requirement conditions.")
    else:
        status = "PASS"
    violation_count = 0
    first_violation: VoltageViolation | None = None
    limit = requirement.limit if requirement is not None and status in {"PASS", "FAIL"} else None
    if limit is not None:
        for index, (time, value) in enumerate(zip(inputs.times, inputs.values, strict=True)):
            if (limit.minimum_v is not None and value < limit.minimum_v) or (
                limit.maximum_v is not None and value > limit.maximum_v
            ):
                violation_count += 1
                if first_violation is None:
                    first_violation = VoltageViolation(
                        sample_index=index, time_seconds=time, value_v=value
                    )
        if violation_count:
            status = "FAIL"
            issues.append(
                f"{violation_count} retained sample(s) exceed the authored voltage envelope."
            )
    return PhysicalVoltageReviewReport(
        status=status,
        project_id=capture.project_id,
        measured_receipt=inputs.measured_path.relative_to(root).as_posix(),
        measured_receipt_sha256=inputs.measured_sha256,
        capture_path=inputs.capture_path.relative_to(root).as_posix(),
        capture_sha256=inputs.capture_sha256,
        requirement_path=None
        if inputs.requirement_path is None
        else inputs.requirement_path.relative_to(root).as_posix(),
        requirement_sha256=inputs.requirement_sha256,
        requirement_state=inputs.requirement_state,
        capture=capture,
        requirement=requirement,
        source_current=inputs.source_current,
        source_sha256=capture.source_sha256,
        samples=len(inputs.values),
        measured_unit=measured_unit,
        observed_min=min(inputs.values) if inputs.values else None,
        observed_max=max(inputs.values) if inputs.values else None,
        violation_count=violation_count,
        first_violation=first_violation,
        issues=tuple(issues),
        output_directory=str(directory),
    )


def build_physical_voltage_review(
    root: Path,
    project_id: str,
    measured_receipt: Path,
    capture_file: Path,
    requirement_file: Path | None = None,
    output: Path | None = None,
) -> PhysicalVoltageReviewReport:
    """Display saved voltage data and apply only compatible, authored numeric limits."""
    root = root.resolve()
    target = output or Path("build/physical-voltage") / f"{project_id}-{uuid4().hex[:12]}"
    relative = target.relative_to(root) if target.is_absolute() else target
    directory = repo_path(root, relative.as_posix())
    inputs = _load_inputs(root, project_id, measured_receipt, capture_file, requirement_file)
    report = _evaluate(root, directory, inputs)

    def verify_inputs() -> None:
        if (
            _load_inputs(root, project_id, measured_receipt, capture_file, requirement_file)
            != inputs
        ):
            raise ValueError("Physical-test source or selected evidence changed during export")

    verify_inputs()
    directory = receipt_directory(root, project_id, target)
    files: dict[str, str] = {}
    if not inputs.artifact_issues:
        for name in RETAINED_MEASUREMENT_ARTIFACTS:
            shutil.copy2(inputs.measured_path.parent / name, directory / name)
            files[name] = digest(directory / name)
            if files[name] != inputs.measured.artifacts_sha256[name]:
                raise ValueError(f"Retained measurement artifact changed during copy: {name}")
    shutil.copy2(inputs.capture_path, directory / "capture.json")
    files["capture.json"] = digest(directory / "capture.json")
    if files["capture.json"] != inputs.capture_sha256:
        raise ValueError("Capture context changed during copy")
    if inputs.requirement_path is not None and inputs.requirement_sha256 is not None:
        shutil.copy2(inputs.requirement_path, directory / "requirement.json")
        files["requirement.json"] = digest(directory / "requirement.json")
        if files["requirement.json"] != inputs.requirement_sha256:
            raise ValueError("Selected requirement changed during copy")
    (directory / "index.html").write_text(
        render_physical_voltage(report, inputs.times, inputs.values, bool(files.get("source.csv"))),
        encoding="utf-8",
    )
    files["index.html"] = digest(directory / "index.html")
    verify_inputs()
    report = report.model_copy(update={"artifacts_sha256": files})
    write_model(directory / "physical-voltage.json", report)
    return report

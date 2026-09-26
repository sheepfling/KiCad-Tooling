"""Concise terminal summaries for typed CLI reports; JSON remains the full contract."""

from __future__ import annotations

from typing import TypeAlias, cast

from pydantic import BaseModel

JsonValue: TypeAlias = "str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]"

LABELS: dict[str, str] = {
    "project_id": "Project",
    "contract": "Contract",
    "projects": "Projects",
    "directory": "Directory",
    "destination": "Destination",
    "source_project": "Source project",
    "template_version": "Template version",
    "current_version": "Current version",
    "target_version": "Target version",
    "release_id": "Release",
    "run_directory": "Run log",
}


def mapping(value: object) -> dict[str, JsonValue] | None:
    """Narrow a JSON object at the presentation boundary."""
    if isinstance(value, dict):
        return cast(dict[str, JsonValue], value)
    return None


def sequence(value: object) -> list[JsonValue]:
    """Narrow a JSON array at the presentation boundary."""
    if isinstance(value, list):
        return cast(list[JsonValue], value)
    return []


def issue_text(value: object) -> str:
    """Keep typed issue identity and location visible without dumping JSON."""
    issue = mapping(value)
    if issue is None:
        return str(value)
    code = str(issue.get("code", "issue"))
    location = str(issue.get("location", ""))
    if not location and issue.get("path"):
        location = str(issue["path"])
        if issue.get("line"):
            location += f":{issue['line']}"
    message = str(issue.get("message", issue.get("observed", "")))
    return f"{code} at {location}: {message}" if location else f"{code}: {message}"


def summary(label: str, report: BaseModel, *, limit: int = 5) -> str:
    """Show status, failed stages and next actions while retaining a JSON escape hatch."""
    data = cast(dict[str, JsonValue], report.model_dump(mode="json"))
    status = str(data.get("status", "RESULT"))
    lines = [f"{label}: {status}"]
    for key, title in LABELS.items():
        value = data.get(key)
        if isinstance(value, str) and value:
            lines.append(f"{title}: {value}")
        else:
            values = sequence(value)
            if values:
                project_rows = [mapping(item) for item in values] if key == "projects" else []
                if project_rows and all(item is not None for item in project_rows):
                    lines.append(f"{title}: {len(values)}")
                    for project in project_rows:
                        if project is None:
                            continue
                        location = project.get("summary") or project.get("run_directory")
                        receipt = f" ({location})" if location else ""
                        lines.append(
                            f"  {project.get('id', project.get('project_id', '?'))}: {project.get('status', '?')}{receipt}"
                        )
                        failing = [
                            row
                            for row in (mapping(item) for item in sequence(project.get("checks")))
                            if row is not None
                            and row.get("status") in {"FAIL", "NOT_RUN", "NOT_CONFIGURED"}
                        ]
                        for row in failing[:limit]:
                            lines.append(
                                f"    {row.get('id', 'check')}: {row.get('detail', 'Review the receipt.')}"
                            )
                        if len(failing) > limit:
                            lines.append(
                                "    More findings are available in the receipt or --format json."
                            )
                else:
                    lines.append(f"{title}: {', '.join(str(item) for item in values)}")
    for key in ("preflight", "initialization", "portable"):
        value = data.get(key)
        if isinstance(value, str):
            lines.append(f"{key.replace('_', ' ').title()}: {value}")
    for raw_check in sequence(data.get("checks")):
        check = mapping(raw_check)
        if check is None:
            continue
        observed = f" ({check['observed']})" if check.get("observed") else ""
        lines.append(
            f"  {check.get('id', check.get('name', 'check'))}: {check.get('status', '?')}{observed}"
        )
        if check.get("status") == "FAIL":
            lines.append(f"    Next: {check.get('next_action', 'Review this check.')}")
    failures: list[str] = []
    hidden_findings = False
    for key, raw_stage in data.items():
        if key in {"source", "checks"}:
            continue
        stage = mapping(raw_stage)
        if stage is None:
            continue
        stage_status = stage.get("status")
        if stage_status is None and "returncode" in stage:
            stage_status = "PASS" if stage["returncode"] == 0 else "FAIL"
        if stage_status is None:
            continue
        lines.append(f"  {key.replace('_', ' ')}: {stage_status}")
        if stage_status == "PASS":
            continue
        stage_issues = sequence(stage.get("issues"))
        hidden_findings = hidden_findings or len(stage_issues) > limit
        for issue in stage_issues[:limit]:
            failures.append(f"{key}: {issue_text(issue)}")
        commands = mapping(stage.get("commands")) or {}
        for name, raw_command in commands.items():
            command = mapping(raw_command)
            if command is None or command.get("returncode") == 0:
                continue
            stderr_lines = str(command.get("stderr", "")).strip().splitlines()
            detail = command.get("error") or (stderr_lines[-1] if stderr_lines else "nonzero exit")
            failures.append(f"{key} {name}: {detail}")
        if stage.get("error"):
            failures.append(f"{key}: {stage['error']}")
        stderr_lines = str(stage.get("stderr", "")).strip().splitlines()
        if stderr_lines:
            failures.append(f"{key}: {stderr_lines[-1]}")
    issues = sequence(data.get("issues"))
    hidden_findings = hidden_findings or len(issues) > limit
    failures.extend(issue_text(value) for value in issues[:limit])
    if failures:
        lines.append("Needs attention:")
        lines.extend(f"  - {value}" for value in failures[:limit])
        if len(failures) > limit or hidden_findings:
            lines.append("  More findings are available with --format json.")
    for key in ("changed", "removed"):
        values = sequence(data.get(key))
        if values:
            lines.append(f"{key.title()}: {', '.join(str(value) for value in values)}")
    for key in ("copied_sha256", "excluded"):
        values = mapping(data.get(key))
        if values is not None:
            lines.append(f"{key.replace('_sha256', '').title()}: {len(values)} file(s)")
    for action in sequence(data.get("next_actions")):
        lines.append(f"Next: {action}")
    if data.get("next_step"):
        lines.append(f"Next: {data['next_step']}")
    if status == "FAIL" and data.get("scope") == "project_static":
        projects = sequence(data.get("projects"))
        if len(projects) == 1 and isinstance(projects[0], str):
            lines.append(
                f"Next: python -B -m kicad_tooling.template diagnose --project-id {projects[0]}"
            )
    if status != "PASS":
        lines.append("Full structured result: rerun with --format json.")
    return "\n".join(lines)

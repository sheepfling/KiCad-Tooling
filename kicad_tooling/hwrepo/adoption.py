"""One-command fork adoption using existing transactional initialization and CI."""

from __future__ import annotations

from pathlib import Path

from .doctor import doctor
from .initialization import initialize
from .models import TemplateAdoptReport
from .template import preflight


def adopt(root: Path, project_id: str) -> TemplateAdoptReport:
    """Initialize a fork and run its complete portable acceptance gate."""
    resolved = root.resolve()
    template = preflight(resolved)
    if template.status != "PASS":
        return TemplateAdoptReport(
            project_id=project_id,
            preflight="FAIL",
            initialization="NOT_RUN",
            portable="NOT_RUN",
            status="FAIL",
            issues=tuple(f"{issue.code}: {issue.message}" for issue in template.issues),
            next_actions=("Repair template preflight findings, then rerun adoption.",),
        )

    environment = doctor(resolved)
    if environment.status != "PASS":
        return TemplateAdoptReport(
            project_id=project_id,
            preflight="PASS",
            initialization="NOT_RUN",
            portable="NOT_RUN",
            status="FAIL",
            issues=tuple(
                f"{check.id}: {check.next_action}"
                for check in environment.checks
                if check.status == "FAIL"
            ),
            next_actions=environment.next_actions,
        )

    initialized = initialize(resolved, project_id)
    if initialized.status != "PASS":
        version_actions = tuple(
            item.message
            for item in initialized.issues
            if item.code in {"TEMPLATE_UPGRADE", "TEMPLATE_VERSION_AHEAD"}
        )
        return TemplateAdoptReport(
            project_id=project_id,
            preflight="PASS",
            initialization="FAIL",
            portable="NOT_RUN",
            status="FAIL",
            issues=tuple(f"{issue.code}: {issue.message}" for issue in initialized.issues),
            next_actions=version_actions
            or (
                "Resolve the initialization finding without deleting adopter work, then rerun adoption.",
            ),
        )

    # Import here so template services remain independent of the CLI orchestration layer.
    from kicad_tooling.ci import static_pipeline

    portable = static_pipeline(resolved, None)
    passed = portable.status == "PASS"
    return TemplateAdoptReport(
        project_id=project_id,
        preflight="PASS",
        initialization="PASS",
        portable=portable.status,
        status="PASS" if passed else "FAIL",
        changed=initialized.changed,
        removed=initialized.removed,
        issues=()
        if passed
        else ("Portable acceptance failed; run kicad_tooling.ci for the detailed report.",),
        next_actions=(
            "Choose the repository license/notice and review the adoption changes before the first commit.",
            "Create or import the first project island, then run its selected and native checks.",
        )
        if passed
        else ("Run python -B -m kicad_tooling.ci and resolve its reported findings.",),
    )

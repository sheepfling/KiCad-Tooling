"""Reviewable heuristic findings from source-bound native netlist evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..validate import hashes
from .contract_coach import inspect_summary as inspect_contract_summary
from .contracts import read_model, repo_path
from .discovery import load_config, load_registry
from .evidence import digest
from .models import (
    ContractCoachReport,
    DesignLintFinding,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleId,
    NetlistContract,
    ProjectManifest,
)


@dataclass(frozen=True)
class Candidate:
    rule_id: DesignLintRuleId
    subject: str
    message: str
    evidence: dict[str, tuple[str, ...]]


def candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Named rules share one fingerprint and review-decision lifecycle."""
    from .connector_pins import similar_connector_pin_groups
    from .return_nets import return_net_groups

    found: list[Candidate] = []
    for group in similar_connector_pin_groups(observed):
        found.append(
            Candidate(
                rule_id="connector.repeated_pin_function",
                subject=f"{group.symbol}: {group.function}",
                message=(
                    "Matching connector pin functions use different or missing nets. "
                    "Review the intended pinout and power/return relationship."
                ),
                evidence=dict(group.pins),
            )
        )
    for group in return_net_groups(observed):
        found.append(
            Candidate(
                rule_id="net.numbered_returns",
                subject=group.stem,
                message=(
                    "Separately numbered return nets may be intended as one return domain. "
                    "Review whether they are common, bonded, or intentionally isolated."
                ),
                evidence=dict(group.nets),
            )
        )
    return tuple(sorted(found, key=lambda item: (item.rule_id, item.subject)))


def fingerprint(item: Candidate) -> str:
    """Bind an ignore to exact observed pins/nets, independent of unrelated files."""
    payload = {
        "rule_id": item.rule_id,
        "subject": item.subject,
        "evidence": {key: sorted(value) for key, value in sorted(item.evidence.items())},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluate(
    project_id: str,
    coach: ContractCoachReport,
    policy: DesignLintPolicy,
) -> DesignLintReport:
    """Apply independently authored decisions without treating findings as requirements."""
    if coach.status != "READY_FOR_REVIEW" or coach.observed is None:
        return DesignLintReport(
            status="BLOCKED",
            project_id=project_id,
            native_summary=coach.native_summary,
            native_status=coach.native_status,
            issues=coach.issues or ("Source-bound netlist evidence is unavailable",),
            next_actions=("Repair the native evidence, then rerun design lint.",),
        )
    overrides = {item.rule_id: item for item in policy.rules}
    ignores = {item.fingerprint: item for item in policy.ignores}
    seen: set[str] = set()
    findings: list[DesignLintFinding] = []
    for item in candidates(coach.observed):
        key = fingerprint(item)
        seen.add(key)
        override = overrides.get(item.rule_id)
        mode: Literal["review", "block", "off"] = "review" if override is None else override.mode
        ignored = ignores.get(key)
        if ignored is not None and ignored.rule_id != item.rule_id:
            return DesignLintReport(
                status="BLOCKED",
                project_id=project_id,
                source_hashes=coach.source_hashes,
                netlist_sha256=coach.netlist_sha256,
                native_summary=coach.native_summary,
                native_status=coach.native_status,
                issues=(f"Ignore {key} names the wrong rule",),
            )
        disposition: Literal["OPEN", "IGNORED", "RULE_OFF"] = (
            "RULE_OFF" if mode == "off" else "IGNORED" if ignored is not None else "OPEN"
        )
        findings.append(
            DesignLintFinding(
                rule_id=item.rule_id,
                fingerprint=key,
                subject=item.subject,
                message=item.message,
                evidence=item.evidence,
                mode=mode,
                disposition=disposition,
                reason=(
                    override.reason
                    if disposition == "RULE_OFF" and override is not None
                    else ignored.reason
                    if ignored is not None
                    else None
                ),
            )
        )
    stale = tuple(item for item in policy.ignores if item.fingerprint not in seen)
    open_findings = tuple(item for item in findings if item.disposition == "OPEN")
    status: Literal["PASS", "REVIEW", "FAIL", "BLOCKED"] = (
        "FAIL"
        if any(item.mode == "block" for item in open_findings)
        else "REVIEW"
        if open_findings or stale
        else "PASS"
    )
    actions: tuple[str, ...] = ()
    if open_findings:
        actions += (
            (
                "Review each open finding against an independent pinout or design requirement; "
                "fix the source or record an exact, reasoned project-owned ignore."
            ),
        )
    if stale:
        actions += ("Remove or update stale ignores after reviewing the changed netlist evidence.",)
    return DesignLintReport(
        status=status,
        project_id=project_id,
        source_hashes=coach.source_hashes,
        netlist_sha256=coach.netlist_sha256,
        native_summary=coach.native_summary,
        native_status=coach.native_status,
        findings=tuple(findings),
        stale_ignores=stale,
        rule_overrides=policy.rules,
        next_actions=actions,
    )


def inspect_summary(root: Path, project_id: str, native_summary: Path) -> DesignLintReport:
    """Read the exact native source and the current project-owned lint decisions."""
    root = root.resolve()
    coach = inspect_contract_summary(root, project_id, native_summary)
    if coach.status != "READY_FOR_REVIEW":
        return evaluate(project_id, coach, DesignLintPolicy())
    try:
        project = next(item for item in load_registry(root).projects if item.id == project_id)
        manifest_path = repo_path(root, project.config)
        manifest_hash = digest(manifest_path)
        manifest = read_model(manifest_path, ProjectManifest)
        policy_path = repo_path(manifest_path.parent, manifest.checks)
        policy_hash = digest(policy_path)
        config = load_config(root, project.config)
        if hashes(root, config.source_roots) != coach.source_hashes:
            raise ValueError("Declared source changed while reading design-lint policy")
        report = evaluate(project_id, coach, config.design_lint or DesignLintPolicy())
        if digest(manifest_path) != manifest_hash or digest(policy_path) != policy_hash:
            raise ValueError("Project manifest or lint policy changed during inspection")
        return report.model_copy(
            update={
                "project_manifest_sha256": manifest_hash,
                "policy_path": policy_path.relative_to(root).as_posix(),
                "policy_sha256": policy_hash,
            }
        )
    except (OSError, ValueError, StopIteration) as exc:
        return DesignLintReport(
            status="BLOCKED",
            project_id=project_id,
            native_summary=coach.native_summary,
            native_status=coach.native_status,
            issues=(str(exc),),
            next_actions=("Repair the project-owned policy or source inventory, then rerun lint.",),
        )


def text_report(report: DesignLintReport) -> str:
    lines = [
        f"Design lint: {report.status}",
        f"Project: {report.project_id}",
        f"Native summary: {report.native_summary or 'unavailable'}",
        f"Native status: {report.native_status or 'unavailable'}",
    ]
    for override in report.rule_overrides:
        lines.append(f"Rule {override.rule_id}: {override.mode} ({override.reason})")
    for finding in report.findings:
        lines.append(
            f"{finding.disposition} [{finding.rule_id}] {finding.subject} ({finding.fingerprint})"
        )
        lines.append(f"  {finding.message}")
        for name, related in finding.evidence.items():
            lines.append(f"  {name}: {', '.join(related) or '<unconnected>'}")
        if finding.reason:
            lines.append(f"  Reason: {finding.reason}")
    for stale in report.stale_ignores:
        lines.append(f"STALE_IGNORE [{stale.rule_id}] {stale.fingerprint}: {stale.reason}")
    for issue in report.issues:
        lines.append(f"Issue: {issue}")
    for action in report.next_actions:
        lines.append(f"Next: {action}")
    return "\n".join(lines)

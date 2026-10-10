"""Stable text rendering for typed design-lint reports."""

from __future__ import annotations

from .design_lint_connector_report import connector_peer_report_lines
from .design_lint_contract_coverage_report import contract_coverage_report_lines
from .design_lint_pcb_report import pcb_coverage_report_lines
from .design_lint_peer_report import peer_reference_report_lines
from .models import DesignLintReport


def text_report(report: DesignLintReport) -> str:
    lines = [
        f"Design lint: {report.status}",
        f"Project: {report.project_id}",
        f"Native summary: {report.native_summary or 'unavailable'}",
        f"Validation summary status: {report.native_status or 'unavailable'}",
    ]
    if report.project_manifest_sha256:
        lines.append(f"Project manifest SHA-256: {report.project_manifest_sha256}")
    if report.policy_path is not None:
        lines.append(f"Lint policy: {report.policy_path} ({report.policy_sha256 or 'unavailable'})")
    if report.rule_catalog is not None:
        active_count = sum(item.status == "active" for item in report.rule_catalog.rules)
        lines.append(
            f"Rule catalog: schema {report.rule_catalog.schema_version}, "
            f"{active_count} active rules, SHA-256 {report.rule_catalog.sha256 or 'unavailable'}"
        )
    geometry = report.schematic_geometry
    mode = geometry.mode or "not configured"
    lines.append(f"Schematic geometry coverage: {geometry.status} (mode: {mode})")
    lines.append("Mapped topology check runs:")
    for item in report.mapped_check_runs:
        lines.append(
            f"  {item.rule_id}: {item.status} (mode: {item.mode}; "
            f"{item.requirement_count} authored item(s), {item.finding_count} finding(s))"
        )
        if item.map_sha256 is not None:
            lines.append(f"    Map SHA-256: {item.map_sha256}")
        if item.netlist_sha256 is not None:
            lines.append(f"    Native netlist SHA-256: {item.netlist_sha256}")
        if item.reason is not None:
            lines.append(f"    Reason: {item.reason}")
    lines.extend(peer_reference_report_lines(report))
    if geometry.source_path is not None:
        lines.append(
            f"  Source: {geometry.source_path} (SHA-256 {geometry.source_sha256 or 'unavailable'})"
        )
        lines.append(
            "  Source tree SHA-256: "
            f"{geometry.source_tree_sha256 or 'unavailable'}; "
            f"{len(geometry.source_bindings)} sheet instance(s) bound"
        )
        for binding in geometry.source_bindings:
            sheet_display = " / ".join(binding.sheet_path) or "root"
            lines.append(
                f"    {sheet_display} [{binding.sheet_instance_path}]: "
                f"{binding.source_path} (SHA-256 {binding.source_sha256})"
            )
    stm32 = report.stm32_pin_map_coverage
    lines.append(
        f"STM32 CubeMX pin-map coverage: {stm32.status} "
        f"(mode: {stm32.mode or 'not configured'}; "
        f"{stm32.mapped_pin_count} mapped, {stm32.excluded_pin_count} excluded, "
        f"{len(stm32.mismatches)} mismatch(es))"
    )
    for source_path, source_sha256 in sorted(stm32.ioc_source_hashes.items()):
        lines.append(f"  CubeMX IOC: {source_path} (SHA-256 {source_sha256})")
    for device in stm32.unmapped_devices:
        lines.append(f"  Unmapped STM32 candidate: {device.reference} ({device.observed_part})")
    if stm32.issue is not None:
        lines.append(f"  Issue: {stm32.issue}")
    lines.extend(pcb_coverage_report_lines(report))
    if geometry.netlist_sha256 is not None:
        lines.append(f"  Native netlist SHA-256: {geometry.netlist_sha256}")
    if geometry.kicad_version is not None:
        lines.append(f"  KiCad version: {geometry.kicad_version}")
    if geometry.schematic_version is not None:
        lines.append(f"  Schematic file version: {geometry.schematic_version}")
    if geometry.finding_count:
        lines.append(f"  Localized candidates: {geometry.finding_count}")
    for unsupported in geometry.unsupported:
        lines.append(f"  Unsupported coverage: {unsupported}")
    if geometry.issue is not None:
        lines.append(f"  Coverage issue: {geometry.issue}")
    lines.extend(contract_coverage_report_lines(report))
    for override in report.rule_overrides:
        lines.append(f"Rule {override.rule_id}: {override.mode} ({override.reason})")
    lines.extend(connector_peer_report_lines(report))
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

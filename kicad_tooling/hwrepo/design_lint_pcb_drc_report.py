"""Format source-bound PCB DRC rule coverage evidence."""

from __future__ import annotations

from .design_lint_report_models import DesignLintReport


def pcb_drc_rule_coverage_report_lines(report: DesignLintReport) -> list[str]:
    """Render differential-pair and signal-path native DRC coverage."""
    lines: list[str] = []
    pair_rules = report.pcb_differential_pair_rules

    lines.append(
        "PCB differential-pair DRC rule coverage: "
        f"{pair_rules.status} (mode: {pair_rules.mode or 'not configured'})"
    )

    if pair_rules.project_path is not None:
        lines.append(
            f"  Project settings: {pair_rules.project_path} "
            f"(SHA-256 {pair_rules.project_sha256 or 'unavailable'})"
        )

    if pair_rules.rules_path is not None:
        lines.append(
            f"  Native rules: {pair_rules.rules_path} "
            f"(SHA-256 {pair_rules.rules_sha256 or 'absent'})"
        )

    if pair_rules.board_path is not None:
        lines.append(
            f"  Board: {pair_rules.board_path} (SHA-256 {pair_rules.board_sha256 or 'unavailable'})"
        )

    if pair_rules.native_drc_path is not None:
        lines.append(
            f"  Native DRC: {pair_rules.native_drc_path} "
            f"(SHA-256 {pair_rules.native_drc_sha256 or 'unavailable'})"
        )

    if pair_rules.kicad_version is not None:
        lines.append(f"  KiCad version: {pair_rules.kicad_version}")

    for entry in pair_rules.entries:
        lines.append(
            f"  {entry.id}: {entry.status}; {entry.positive_net} / {entry.negative_net}; "
            f"selector {entry.pair_selector}"
        )
        for item in entry.constraints:
            expected = f"min={item.expected_min_nm}, max={item.expected_max_nm} nm"
            observed = f"min={item.observed_min_nm}, max={item.observed_max_nm} nm"
            rules = ", ".join(item.rule_names) or "none"
            lines.append(
                f"    {item.constraint}: {item.status}; expected {expected}; "
                f"observed {observed}; rules {rules}"
            )
            if item.issue is not None:
                lines.append(f"      Issue: {item.issue}")
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")

    if pair_rules.issue is not None:
        lines.append(f"  Coverage issue: {pair_rules.issue}")

    signal_paths = report.pcb_signal_path_rules

    lines.append(
        "PCB signal-path DRC rule coverage: "
        f"{signal_paths.status} (mode: {signal_paths.mode or 'not configured'})"
    )

    if signal_paths.project_path is not None:
        lines.append(
            f"  Project settings: {signal_paths.project_path} "
            f"(SHA-256 {signal_paths.project_sha256 or 'unavailable'})"
        )

    if signal_paths.rules_path is not None:
        lines.append(
            f"  Native rules: {signal_paths.rules_path} "
            f"(SHA-256 {signal_paths.rules_sha256 or 'absent'})"
        )

    if signal_paths.board_path is not None:
        lines.append(
            f"  Board: {signal_paths.board_path} "
            f"(SHA-256 {signal_paths.board_sha256 or 'unavailable'})"
        )

    if signal_paths.native_drc_path is not None:
        lines.append(
            f"  Native DRC: {signal_paths.native_drc_path} "
            f"(SHA-256 {signal_paths.native_drc_sha256 or 'unavailable'})"
        )

    if signal_paths.pcb_snapshot_path is not None:
        lines.append(
            f"  Native PCB snapshot: {signal_paths.pcb_snapshot_path} "
            f"(SHA-256 {signal_paths.pcb_snapshot_sha256 or 'unavailable'})"
        )

    if signal_paths.kicad_version is not None:
        lines.append(f"  KiCad version: {signal_paths.kicad_version}")

    for entry in signal_paths.entries:
        if entry.kind == "path":
            identity = f"{entry.net}: {entry.from_pad} to {entry.to_pad}"
        else:
            identity = (
                f"{entry.from_pad_pattern} to {entry.to_pad_pattern}; "
                f"members {', '.join(entry.path_ids)}"
            )
        lines.append(f"  {entry.id}: {entry.status}; {identity}")
        for item in entry.constraints:
            expected = f"min={item.expected_min_nm}, max={item.expected_max_nm} nm"
            observed = f"min={item.observed_min_nm}, max={item.observed_max_nm} nm"
            rules = ", ".join(item.rule_names) or "none"
            lines.append(
                f"    {item.constraint}: {item.status}; expected {expected}; "
                f"observed {observed}; rules {rules}"
            )
            if item.issue is not None:
                lines.append(f"      Issue: {item.issue}")
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")

    if signal_paths.issue is not None:
        lines.append(f"  Coverage issue: {signal_paths.issue}")

    return lines

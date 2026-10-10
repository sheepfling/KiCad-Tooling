"""Emit source-bound receipts for each connector return fixture."""

from __future__ import annotations

from .ci_hosted_connector_return_context import ConnectorReturnFixtureContext


def emit_connector_return_receipts(
    ctx: ConnectorReturnFixtureContext, peer_pin_coverage_receipts: dict[str, str]
):
    """Emit source-bound receipts for each connector return fixture."""
    for case in ctx.cases:
        repeatable = (
            ctx.normalized_netlist_hashes[case, "first"]
            == ctx.normalized_netlist_hashes[case, "repeat"]
        )
        if not repeatable:
            raise ValueError(
                f"Native {case} exports differ after normalization to the parsed netlist contract"
            )
        report = ctx.reports[case, "first"]
        ctx.log.event(
            f"connector-return-fixture/{case}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            image=ctx.pinned,
            source_sha256=ctx.source_hashes[case],
            netlist_sha256=ctx.netlist_hashes[case, "first"],
            repeat_netlist_sha256=ctx.netlist_hashes[case, "repeat"],
            normalized_netlist_sha256=ctx.normalized_netlist_hashes[case, "first"],
            repeat_normalized_netlist_sha256=ctx.normalized_netlist_hashes[case, "repeat"],
            lint_status=report.status,
            findings=",".join(finding.rule_id for finding in report.findings) or "none",
            subjects=";".join(finding.subject for finding in report.findings) or "none",
            pin_functions=";".join(
                f"{pin}={name}"
                for (pin, name) in sorted(
                    ctx.observed_contracts[case, "first"].pin_functions.items()
                )
            ),
            pin_electrical_types=";".join(
                f"{pin}={name}"
                for (pin, name) in sorted(
                    ctx.observed_contracts[case, "first"].pin_electrical_types.items()
                )
            ),
            **{"connector_peer_pin_coverage": peer_pin_coverage_receipts[case]}
            if case in peer_pin_coverage_receipts
            else {},
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )

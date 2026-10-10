"""Run one native PCB return-path fault or control case."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .ci_hosted_pcb_return_context import (
    PcbReturnCaseEvidence,
    PcbReturnFixtureCase,
    PcbReturnFixtureContext,
)
from .ci_hosted_pcb_return_evidence import (
    verify_pcb_return_isolation_evidence,
    verify_pcb_return_net_tie_evidence,
    verify_pcb_return_plane_evidence,
    verify_pcb_return_via_evidence,
    verify_pcb_return_zone_island_evidence,
)
from .hwrepo import pcb_return_path_capture
from .hwrepo.evidence import digest
from .hwrepo.models import (
    PcbReturnBondRequirement,
    PcbReturnDomainRequirement,
    PcbReturnEndpointRequirement,
    PcbReturnPathsAnalysis,
)
from .hwrepo.pcb_return_path_checks import (
    pcb_return_path_checks,
)


def verify_pcb_return_fixture_case(
    ctx: PcbReturnFixtureContext, fixture_case: PcbReturnFixtureCase
):
    """Evaluate one source-bound native copper return fixture."""
    (
        fixture_id,
        fixture_name,
        scenario,
        expected_connected,
        expected_islands,
        expected_island_indices,
        expected_tie_dnp,
        expected_isolated,
    ) = fixture_case
    scratch = Path(
        tempfile.mkdtemp(prefix=f"pcb-return-{ctx.project}-", dir=ctx.log.directory.resolve())
    )
    relative_project = scratch.relative_to(ctx.root) / f"{fixture_id}.kicad_pro"
    board = ctx.root / relative_project.with_suffix(".kicad_pcb")
    shutil.copyfile(ctx.fixture_root / fixture_name, board)
    fixture_config = ctx.config.model_copy(update={"project": relative_project.as_posix()})
    receipt = scratch / "receipt"
    try:
        if scenario == "direct":
            topology = PcbReturnDomainRequirement(
                id=fixture_id,
                basis="Synthetic fixture asserts only its stated direct same-net path",
                topology="direct",
                endpoints=(
                    PcbReturnEndpointRequirement(
                        pad="J1.1", net="RETURN", footprint="Synthetic:TestPad"
                    ),
                    PcbReturnEndpointRequirement(
                        pad="J2.1", net="RETURN", footprint="Synthetic:TestPad"
                    ),
                ),
            )
            domains = (topology,)
        elif scenario == "bond":
            topology = PcbReturnDomainRequirement(
                id=fixture_id,
                basis="Synthetic fixture asserts an exact fitted KiCad net-tie bond",
                topology="bonded",
                endpoints=(
                    PcbReturnEndpointRequirement(
                        pad="J1.1", net="RETURN_A", footprint="Synthetic:TestPad"
                    ),
                    PcbReturnEndpointRequirement(
                        pad="J2.1", net="RETURN_B", footprint="Synthetic:TestPad"
                    ),
                ),
                bonds=(
                    PcbReturnBondRequirement(
                        reference="NT1",
                        footprint="Synthetic:NetTie-2",
                        pad_groups=(("NT1.1", "NT1.2"),),
                    ),
                ),
            )
            domains = (topology,)
        else:
            domains = (
                PcbReturnDomainRequirement(
                    id="isolation-a",
                    basis="Synthetic fixture asserts two connected endpoints in return domain A",
                    topology="direct",
                    endpoints=(
                        PcbReturnEndpointRequirement(
                            pad="J1.1", net="RETURN_A", footprint="Synthetic:TestPad"
                        ),
                        PcbReturnEndpointRequirement(
                            pad="J3.1", net="RETURN_A", footprint="Synthetic:TestPad"
                        ),
                    ),
                ),
                PcbReturnDomainRequirement(
                    id="isolation-b",
                    basis="Synthetic fixture asserts two connected endpoints in return domain B",
                    topology="direct",
                    endpoints=(
                        PcbReturnEndpointRequirement(
                            pad="J2.1", net="RETURN_B", footprint="Synthetic:TestPad"
                        ),
                        PcbReturnEndpointRequirement(
                            pad="J4.1", net="RETURN_B", footprint="Synthetic:TestPad"
                        ),
                    ),
                ),
            )
        requirement = PcbReturnPathsAnalysis(
            basis="Synthetic native PCB return-path fixture", domains=domains
        )
        (command, snapshot) = pcb_return_path_capture.capture_native_pcb_connectivity(
            ctx.root, fixture_config, receipt
        )
        if command.returncode != 0 or command.error is not None:
            raise ValueError(
                f"Native PCB fixture command failed: {command.stderr or command.error}"
            )
        if not pcb_return_path_capture.native_pcb_command_matches(command, fixture_config):
            raise ValueError("Native PCB fixture did not use the pinned read-only probe command")
        if snapshot is None:
            raise ValueError("Native PCB fixture returned no connectivity snapshot")
        checks = pcb_return_path_checks(
            requirement,
            snapshot,
            board_sha256=digest(board),
            kicad_version=ctx.config.kicad_version,
            image=ctx.config.image,
            probe_sha256=pcb_return_path_capture.expected_probe_sha256(),
        )
        by_pad = {item.pad.casefold(): item for item in snapshot.pads}
        first = by_pad.get("j1.1")
        second = by_pad.get("j2.1")
        is_via_fixture = fixture_id.startswith("alternate-layer-")
        observed_connected = (
            first is not None
            and second is not None
            and ("j2.1" in {pad.casefold() for pad in first.connected_pads})
            and ("j1.1" in {pad.casefold() for pad in second.connected_pads})
        )
        connectivity_id = f"pcb-return-paths/{fixture_id}/connectivity"
        connectivity_check = next((check for check in checks if check.id == connectivity_id), None)
        failures: list[str] = []
        via_identity_repeatable = False
        case_evidence = PcbReturnCaseEvidence(
            fixture_id=fixture_id,
            scenario=scenario,
            expected_connected=expected_connected,
            expected_islands=expected_islands,
            expected_island_indices=expected_island_indices,
            expected_tie_dnp=expected_tie_dnp,
            expected_isolated=expected_isolated,
            root=ctx.root,
            config=ctx.config,
            fixture_config=fixture_config,
            scratch=scratch,
            snapshot=snapshot,
            first=first,
            second=second,
            checks=checks,
            connectivity_check=connectivity_check,
            observed_connected=observed_connected,
            is_via_fixture=is_via_fixture,
            failures=failures,
            via_identity_repeatable=via_identity_repeatable,
        )
        verify_pcb_return_via_evidence(case_evidence)
        expected_statuses: dict[str, str] = {}
        if scenario == "isolation":
            expected_statuses.update(
                {
                    "pcb-return-paths/isolation-a/connectivity": "PASS",
                    "pcb-return-paths/isolation-b/connectivity": "PASS",
                    "pcb-return-paths/isolation/isolation-a/isolation-b": "PASS"
                    if expected_isolated
                    else "FAIL",
                }
            )
        else:
            connectivity_id = f"pcb-return-paths/{fixture_id}/connectivity"
            expected_connectivity_status = "PASS" if expected_connected else "FAIL"
            expected_statuses[connectivity_id] = expected_connectivity_status
        if scenario == "bond" and expected_tie_dnp is not None:
            expected_statuses[f"pcb-return-paths/{fixture_id}/bond/NT1"] = (
                "FAIL" if expected_tie_dnp else "PASS"
            )
        failures.extend(
            [
                f"{check.id}: {check.detail}"
                for check in checks
                if check.status != expected_statuses.get(check.id, "PASS")
            ]
        )
        if scenario == "direct" and observed_connected != expected_connected:
            failures.append(
                "Native copper pad membership does not match the fixture's declared topology"
            )
        verify_pcb_return_plane_evidence(case_evidence)
        verify_pcb_return_net_tie_evidence(case_evidence)
        verify_pcb_return_isolation_evidence(case_evidence)
        verify_pcb_return_zone_island_evidence(case_evidence)
        if failures:
            raise ValueError("Native PCB return fixture failed: " + "; ".join(failures))
    except Exception as exc:
        ctx.log.event(
            f"pcb-return-fixture/{fixture_id}",
            "FAIL",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            error=str(exc),
        )
        raise
    via_identity_repeatable = case_evidence.via_identity_repeatable
    if expected_islands is None:
        event_fields: dict[str, str | float] = {
            "project": ctx.project,
            "kicad_version": ctx.config.kicad_version,
            "expected_connectivity": "connected" if expected_connected else "open",
            "receipt": receipt.relative_to(ctx.root).as_posix(),
        }
        if expected_isolated is not None:
            event_fields["expected_isolation"] = "separate" if expected_isolated else "bridged"
        if fixture_id == "alternate-layer-via":
            event_fields["via_identity_repeatable"] = "true" if via_identity_repeatable else "false"
        if fixture_id == "stitched-planes":
            event_fields["plane_stitch_repeatable"] = "true" if via_identity_repeatable else "false"
            event_fields["zone_layers"] = "F.Cu,B.Cu"
        ctx.log.event(f"pcb-return-fixture/{fixture_id}", "PASS", **event_fields)
    else:
        ctx.log.event(
            f"pcb-return-fixture/{fixture_id}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            expected_connectivity="connected" if expected_connected else "open",
            filled_island_count=expected_islands,
            receipt=receipt.relative_to(ctx.root).as_posix(),
        )

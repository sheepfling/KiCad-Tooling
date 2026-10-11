"""Exact-version native fixtures for CAN peer reference review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def can_peer_reference_native_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify CAN shared-pair reference fixtures with repeated pinned exports."""
    from .hwrepo.can_peer_reference_scan import scan_can_peer_references
    from .hwrepo.component_peer_pin_findings import (
        component_peer_power_pin_assignment_divergences,
    )
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.contracts import read_kicad_erc_report, write_model
    from .hwrepo.design_lint_can_candidates import can_peer_reference_candidates
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import NetlistContract
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"CAN peer-reference fixtures do not cover KiCad {config.kicad_version}")

    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/can-peer-reference-native"
    )
    cases = ("reference-control", "reference-fault")
    source_hashes = {case: digest(fixture_root / f"{case}.kicad_sch") for case in cases}
    expected_source_hashes = {
        "reference-control": "ece18cddcf6fb122bcbcd46a7b4792426735146a6a923b62b68642ef0903a96a",
        "reference-fault": "4e636cab9d214f97e68640f1d200df6067d49e83d571ce3e8e117527517103a8",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("CAN peer-reference fixture sources differ from reviewed hashes")

    pinned = pinned_image(config.image)
    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"native-can-peer-reference-{project}-", dir=log.directory.resolve()
        )
    )
    inputs = scratch / "input"
    output = scratch / "output"
    inputs.mkdir()
    output.mkdir()
    for case in cases:
        fixture = fixture_root / f"{case}.kicad_sch"
        copied = inputs / fixture.name
        shutil.copyfile(fixture, copied)
        if digest(copied) != source_hashes[case]:
            raise ValueError(f"Synthetic CAN {case} fixture changed while preparing native input")

    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{config.kicad_version}"\n'
        "for case in reference-control reference-fault; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml \\\n"
        '      --output "/output/${case}.${run}.netlist.xml" \\\n'
        '      "/fixtures/${case}.kicad_sch"\n'
        "    kicad-cli sch erc --format json --severity-all \\\n"
        '      --output "/output/${case}.${run}.erc.json" \\\n'
        '      "/fixtures/${case}.kicad_sch"\n'
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
        "HOME=/tmp/kicad-can-peer-reference",
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
        "can-peer-reference-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{source_hashes[case]}" for case in cases),
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    receipt_path = receipt.relative_to(root).as_posix()
    if command.returncode != 0 or command.error is not None:
        log.event(
            "can-peer-reference-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=receipt_path,
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native CAN peer-reference export failed: {command.stderr or command.error}"
        )

    normalized_by_case: dict[str, str] = {}
    pin_nets_by_case: dict[str, dict[str, str]] = {}
    for case in cases:
        if digest(fixture_root / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError("CAN peer-reference fixture changed during native export")
        observations: dict[str, NetlistContract] = {}
        netlist_hashes: dict[str, str] = {}
        erc_hashes: dict[str, str] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native CAN {case} export omitted an expected report")
            observed = read_netlist(netlist_path)
            observations[run] = observed
            normalized_netlist = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            netlist_hashes[run] = hashlib.sha256(normalized_netlist).hexdigest()

            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != config.kicad_version:
                raise ValueError(f"Native CAN {case} ERC version differs from selected KiCad")
            errors = tuple(sorted(item.type for item in erc.violations if item.severity == "error"))
            if errors:
                raise ValueError(f"Native CAN {case} fixture has ERC errors: {errors}")
            erc_rows = [
                (
                    item.type,
                    item.severity,
                    item.description,
                    tuple(
                        sorted(
                            ((detail.description, detail.x, detail.y) for detail in item.items),
                            key=lambda detail: json.dumps(
                                detail,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False,
                            ),
                        )
                    ),
                )
                for item in erc.violations
            ]
            erc_rows.sort(
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
            normalized_erc = json.dumps(
                {"kicad_version": erc.kicad_version, "violations": erc_rows},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            erc_hashes[run] = hashlib.sha256(normalized_erc).hexdigest()
        if netlist_hashes["first"] != netlist_hashes["repeat"]:
            raise ValueError(f"Native CAN {case} netlist exports are not repeatable")
        if erc_hashes["first"] != erc_hashes["repeat"]:
            raise ValueError(f"Native CAN {case} ERC reports are not repeatable")

        observed = observations["first"]
        expected_functions = {
            f"{reference}.{number}": function
            for reference in ("U1", "U2", "U3")
            for number, function in (("1", "CANH"), ("2", "CAN_L"), ("3", "GND"), ("4", "VDD"))
        }
        if any(
            observed.pin_functions.get(pin) != function
            for pin, function in expected_functions.items()
        ):
            raise ValueError(f"Native CAN {case} fixture changed a required pin function")
        if any(
            observed.component_pin_numbers.get(reference) != ("1", "2", "3", "4")
            for reference in ("U1", "U2", "U3")
        ):
            raise ValueError(f"Native CAN {case} fixture has incomplete transceiver pin inventory")
        pin_nets: dict[str, str] = {}
        for net, pins in observed.nets.items():
            for pin in pins:
                if pin in pin_nets:
                    raise ValueError(f"Native CAN {case} pin {pin} has multiple net assignments")
                pin_nets[pin] = net
        expected_assignments = {
            **{
                f"{reference}.{number}": net
                for reference in ("U1", "U2", "U3")
                for number, net in (("1", "NET_B"), ("2", "NET_A"))
            },
            **{
                f"{reference}.3": (
                    "GND_A" if case == "reference-control" or reference != "U3" else "GND_B"
                )
                for reference in ("U1", "U2", "U3")
            },
            **{f"{reference}.4": "+3V3" for reference in ("U1", "U2", "U3")},
        }
        assignment_mismatches = {
            pin: {"expected": net, "observed": pin_nets.get(pin)}
            for pin, net in expected_assignments.items()
            if pin_nets.get(pin) != net
        }
        if assignment_mismatches:
            detail = json.dumps(assignment_mismatches, sort_keys=True)
            raise ValueError(
                f"Native CAN {case} fixture changed the expected pin-to-net assignments: {detail}"
            )

        scan = scan_can_peer_references(observed)
        expected_disposition = (
            "COMMON_REFERENCE" if case == "reference-control" else "SPLIT_REFERENCE_REVIEW"
        )
        if (
            scan.recognized_endpoint_count != 3
            or len(scan.buses) != 1
            or scan.buses[0].disposition != expected_disposition
            or (scan.buses[0].canh_net, scan.buses[0].canl_net) != ("NET_B", "NET_A")
            or tuple(item.reference for item in scan.buses[0].endpoints) != ("U1", "U2", "U3")
        ):
            raise ValueError(f"Native CAN {case} did not preserve the expected peer group")
        if observed.component_symbols.get("U1") != observed.component_symbols.get(
            "U2"
        ) or observed.component_symbols.get("U1") == observed.component_symbols.get("U3"):
            raise ValueError(
                "Native CAN fixture must retain two comparable peers and one distinct peer"
            )
        if component_peer_power_pin_assignment_divergences(observed):
            raise ValueError("CAN reference fixture unexpectedly overlaps component-peer findings")
        candidates = can_peer_reference_candidates(observed, scan)
        expected_count = 0 if case == "reference-control" else 1
        if len(candidates) != expected_count:
            raise ValueError(
                f"Native CAN {case} produced {len(candidates)} reference candidates; "
                f"expected {expected_count}"
            )
        normalized_by_case[case] = netlist_hashes["first"]
        pin_nets_by_case[case] = pin_nets
        log.event(
            f"can-peer-reference-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=netlist_hashes["first"],
            repeat_normalized_netlist_sha256=netlist_hashes["repeat"],
            normalized_erc_sha256=erc_hashes["first"],
            repeat_normalized_erc_sha256=erc_hashes["repeat"],
            canh_net=scan.buses[0].canh_net,
            canl_net=scan.buses[0].canl_net,
            references=",".join(
                sorted({item.reference_net or "" for item in scan.buses[0].endpoints})
            ),
            disposition=expected_disposition,
            lint_candidate_count=str(expected_count),
            erc_errors="0",
            repeatable="true",
            command_receipt=receipt_path,
        )
    changed_pins = {
        pin
        for pin in pin_nets_by_case["reference-control"].keys()
        | pin_nets_by_case["reference-fault"].keys()
        if pin_nets_by_case["reference-control"].get(pin)
        != pin_nets_by_case["reference-fault"].get(pin)
    }
    if changed_pins != {"U3.3"}:
        raise ValueError("CAN reference fixture pair must differ only at the U3 reference pin")
    log.event(
        "can-peer-reference-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{source_hashes[case]}" for case in cases),
        normalized_netlist_hashes=";".join(f"{case}:{normalized_by_case[case]}" for case in cases),
        command_receipt=receipt_path,
    )

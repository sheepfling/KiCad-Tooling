"""Exact-version native fixtures for mapped RS-485 peer-reference review."""

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


def rs485_peer_reference_native_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Check project-mapped RS-485 peer references against repeated native exports."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.contracts import read_kicad_erc_report, write_model
    from .hwrepo.design_lint_rs485_candidates import rs485_peer_reference_candidates
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import NetlistContract
    from .hwrepo.rs485_models import Rs485Analysis
    from .hwrepo.rs485_peer_reference_scan import scan_rs485_peer_references
    from .hwrepo.rs485_peer_reference_types import Rs485PeerReferenceContext
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"RS-485 peer-reference fixtures do not cover KiCad {config.kicad_version}"
        )

    fixture_root = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/design_lint/rs485-peer-reference-native"
    )
    cases = ("reference-control", "reference-fault")
    sources = {
        case: {
            "schematic": fixture_root / f"{case}.kicad_sch",
            "analysis": fixture_root / f"{case}.json",
        }
        for case in cases
    }
    source_hashes = {
        case: {name: digest(path) for name, path in items.items()}
        for case, items in sources.items()
    }
    expected_source_hashes = {
        "reference-control": {
            "schematic": "10be7495b5c4bbdd20fc7f637a0fb77d0dc946c1bb54f8b86e580ab19e8441e3",
            "analysis": "96135ffa15a09b2529b0c383e3171d82ec33c271760413a819ca8c2e9cb956c4",
        },
        "reference-fault": {
            "schematic": "dcceed2427de1a6001cba204dd4f05dee2eb734ae2d77bfb5a58289f7d62622c",
            "analysis": "8694c6ee028fdd3aca09eecb1c91e3c938ce35b62385672100d630ad7c2005bb",
        },
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("RS-485 peer-reference fixture sources differ from reviewed hashes")

    analyses = {
        case: Rs485Analysis.model_validate_json(paths["analysis"].read_text(encoding="utf-8"))
        for case, paths in sources.items()
    }
    pinned = pinned_image(config.image)
    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"native-rs485-peer-reference-{project}-", dir=log.directory.resolve()
        )
    )
    inputs = scratch / "input"
    output = scratch / "output"
    inputs.mkdir()
    output.mkdir()
    for case, items in sources.items():
        schematic_input = inputs / f"{case}.kicad_sch"
        analysis_input = inputs / f"{case}.json"
        shutil.copyfile(items["schematic"], schematic_input)
        shutil.copyfile(items["analysis"], analysis_input)
        if (
            digest(schematic_input) != source_hashes[case]["schematic"]
            or digest(analysis_input) != source_hashes[case]["analysis"]
        ):
            raise ValueError(f"Synthetic RS-485 {case} source changed while preparing input")

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
        "HOME=/tmp/kicad-rs485-peer-reference",
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
        "rs485-peer-reference-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(
            f"{case}:{name}:{source_hashes[case][name]}"
            for case in cases
            for name in ("schematic", "analysis")
        ),
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    receipt_path = receipt.relative_to(root).as_posix()
    if command.returncode != 0 or command.error is not None:
        log.event(
            "rs485-peer-reference-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=receipt_path,
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native RS-485 peer-reference export failed: {command.stderr or command.error}"
        )

    normalized_by_case: dict[str, str] = {}
    assignments_by_case: dict[str, dict[str, str]] = {}
    for case in cases:
        if any(digest(path) != source_hashes[case][name] for name, path in sources[case].items()):
            raise ValueError("RS-485 fixture source changed during native export")
        observations: dict[str, NetlistContract] = {}
        normalized_netlist_hashes: dict[str, str] = {}
        normalized_erc_hashes: dict[str, str] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native RS-485 {case} export omitted an expected report")
            observed = read_netlist(netlist_path)
            observations[run] = observed
            normalized_netlist = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_netlist_hashes[run] = hashlib.sha256(normalized_netlist).hexdigest()

            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != config.kicad_version:
                raise ValueError(f"Native RS-485 {case} ERC version differs from selected KiCad")
            errors = tuple(
                sorted(
                    f"{item.type}: {item.description or 'no description'}; items="
                    f"{tuple((detail.description, detail.x, detail.y) for detail in item.items)!r}"
                    for item in erc.violations
                    if item.severity == "error"
                )
            )
            if errors:
                raise ValueError(f"Native RS-485 {case} fixture has ERC errors: {errors}")
            erc_rows = sorted(
                (
                    item.type,
                    item.severity,
                    item.description,
                    tuple(
                        sorted((detail.description, detail.x, detail.y) for detail in item.items)
                    ),
                )
                for item in erc.violations
            )
            normalized_erc = json.dumps(
                {"kicad_version": erc.kicad_version, "violations": erc_rows},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_erc_hashes[run] = hashlib.sha256(normalized_erc).hexdigest()
        if normalized_netlist_hashes["first"] != normalized_netlist_hashes["repeat"]:
            raise ValueError(f"Native RS-485 {case} netlist exports are not repeatable")
        if normalized_erc_hashes["first"] != normalized_erc_hashes["repeat"]:
            raise ValueError(f"Native RS-485 {case} ERC reports are not repeatable")

        observed = observations["first"]
        expected_symbols = {
            "J1": "Synthetic:Rs485_Endpoint",
            "J2": "Synthetic:Rs485_Endpoint",
            "J3": "Synthetic:Rs485_Endpoint",
            "U1": "Synthetic:Rs485_Transceiver",
        }
        expected_pins = {
            "J1": ("1", "2", "3"),
            "J2": ("1", "2", "3"),
            "J3": ("1", "2", "3"),
            "U1": ("1", "2", "3", "4", "5"),
        }
        expected_footprints = {
            "J1": "Synthetic:3PinHeader",
            "J2": "Synthetic:3PinHeader",
            "J3": "Synthetic:3PinHeader",
            "U1": "Synthetic:SOIC",
        }
        if observed.component_symbols != expected_symbols:
            raise ValueError(f"Native RS-485 {case} fixture changed endpoint symbol identities")
        if observed.component_pin_numbers != expected_pins:
            raise ValueError(f"Native RS-485 {case} fixture changed its exact pin inventory")
        if any(
            observed.components[reference].footprint != footprint
            for reference, footprint in expected_footprints.items()
        ):
            raise ValueError(f"Native RS-485 {case} fixture changed endpoint footprints")
        pin_nets: dict[str, str] = {}
        for net, pins in observed.nets.items():
            for pin in pins:
                if pin in pin_nets:
                    raise ValueError(f"Native RS-485 {case} pin {pin} has multiple net assignments")
                pin_nets[pin] = net
        expected_assignments = {
            requirement.pin: requirement.net
            for endpoint in analyses[case].buses[0].endpoints
            for requirement in endpoint.pins
        }
        mismatches = {
            pin: {"expected": net, "observed": pin_nets.get(pin)}
            for pin, net in expected_assignments.items()
            if pin_nets.get(pin) != net
        }
        if mismatches:
            raise ValueError(
                "Native RS-485 fixture changed exact map assignments: "
                + json.dumps(mismatches, sort_keys=True)
            )

        context = Rs485PeerReferenceContext(
            state="required",
            analysis=analyses[case],
            source_path=f"tests/fixtures/design_lint/rs485-peer-reference-native/{case}.json",
            source_sha256=source_hashes[case]["analysis"],
        )
        scan = scan_rs485_peer_references(context, observed)
        expected_disposition = (
            "COMMON_REFERENCE" if case == "reference-control" else "SPLIT_REFERENCE_REVIEW"
        )
        candidate_count = len(rs485_peer_reference_candidates(scan))
        expected_candidate_count = 0 if case == "reference-control" else 1
        if (
            scan.recognized_endpoint_count != 4
            or len(scan.pairs) != 1
            or scan.pairs[0].disposition != expected_disposition
            or candidate_count != expected_candidate_count
        ):
            raise ValueError(f"Native RS-485 {case} did not preserve the expected peer group")

        normalized_by_case[case] = normalized_netlist_hashes["first"]
        assignments_by_case[case] = pin_nets
        log.event(
            f"rs485-peer-reference-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            source_sha256=source_hashes[case]["schematic"],
            authored_map_sha256=source_hashes[case]["analysis"],
            normalized_netlist_sha256=normalized_netlist_hashes["first"],
            repeat_normalized_netlist_sha256=normalized_netlist_hashes["repeat"],
            normalized_erc_sha256=normalized_erc_hashes["first"],
            repeat_normalized_erc_sha256=normalized_erc_hashes["repeat"],
            line_1_net=scan.pairs[0].line_1_net,
            line_2_net=scan.pairs[0].line_2_net,
            references=",".join(
                sorted(
                    {
                        endpoint.reference_net
                        for endpoint in scan.pairs[0].endpoints
                        if endpoint.reference_net is not None
                    },
                    key=lambda net: (net.casefold(), net),
                )
            ),
            disposition=expected_disposition,
            lint_candidate_count=str(candidate_count),
            erc_errors="0",
            repeatable="true",
            command_receipt=receipt_path,
        )

    changed_pins = {
        pin
        for pin in assignments_by_case["reference-control"].keys()
        | assignments_by_case["reference-fault"].keys()
        if assignments_by_case["reference-control"].get(pin)
        != assignments_by_case["reference-fault"].get(pin)
    }
    if (
        changed_pins != {"J3.3"}
        or normalized_by_case["reference-control"] == normalized_by_case["reference-fault"]
    ):
        raise ValueError("RS-485 fault/control fixtures must differ only at the J3 reference pin")
    log.event(
        "rs485-peer-reference-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(
            f"{case}:{name}:{source_hashes[case][name]}"
            for case in cases
            for name in ("schematic", "analysis")
        ),
        changed_assignments=",".join(sorted(changed_pins)),
        repeatable="true",
        command_receipt=receipt_path,
    )

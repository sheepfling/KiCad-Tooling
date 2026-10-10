"""Hosted native control-input fixture lane."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def native_control_input_demo_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Check unconnected controls in public demos bundled in pinned KiCad 10.0.5."""
    import hashlib

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.control_input_inventory import (
        connected_control_inputs_without_visible_rail_resistor,
        unconnected_control_inputs,
    )
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .validate import read_netlist

    root = root.resolve()
    expected_image = (
        "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
    )
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version != "10.0.5":
        raise ValueError(
            "Native control-input demo fixtures are pinned to the KiCad 10.0.5 demo corpus"
        )
    if config.image != expected_image:
        raise ValueError("Native control-input demos require the recorded KiCad 10.0.5 image")
    pinned = pinned_image(config.image)
    samples = {
        "cm5-minima": (
            "/usr/share/kicad/demos/cm5_minima",
            "CM5_MINIMA_3.kicad_sch",
            (),
        ),
        "jetson-agx-thor": (
            "/usr/share/kicad/demos/jetson-agx-thor-baseboard",
            "jetson-agx-thor-baseboard.kicad_sch",
            (("J14.23", "SDIO_~{RESET}", "reset", "input"),),
        ),
        "coldfire-xilinx": (
            "/usr/share/kicad/demos/kit-dev-coldfire-xilinx_5213",
            "kit-dev-coldfire-xilinx_5213.kicad_sch",
            (("VR201.4", "SHDN", "enable", "input"),),
        ),
        "vme-wren": (
            "/usr/share/kicad/demos/vme-wren",
            "vme-wren.kicad_sch",
            (
                ("IC19.3", "~{RESET}", "reset", "input"),
                ("IC21.3", "~{RESET}", "reset", "input"),
                ("IC30.33", "BOOT_B", "boot/strap", "input"),
                ("IC30.38", "BOOT_A", "boot/strap", "input"),
            ),
        ),
        "por-alias-fixture": (
            "/synthetic",
            "por-b.kicad_sch",
            (("U1.1", "POR_B", "reset", "input"),),
        ),
    }
    synthetic_fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/control-input-alias"
    )
    if not (synthetic_fixture_root / "por-b.kicad_sch").is_file():
        raise ValueError("Synthetic POR_B native control fixture is missing")
    scratch = Path(
        tempfile.mkdtemp(prefix=f"control-input-demo-{project}-", dir=log.directory.resolve())
    )
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")

    source_lines = [
        'actual="$(kicad-cli version)"\n',
        'printf "kicad_version=%s\\n" "$actual"\n',
        f'test "$actual" = "{config.kicad_version}"\n',
    ]
    for sample, (directory, filename, _expected) in samples.items():
        source = f"{directory}/{filename}"
        source_lines.extend(
            (
                f'cd "{directory}"\n',
                f"find . -type f -name '*.kicad_sch' -print0 | sort -z | xargs -0 sha256sum > \"/output/{sample}.source-manifest.sha256\"\n",
                f'sha256sum "{source}" | cut -d \' \' -f 1 > "/output/{sample}.source.sha256"\n',
                f'kicad-cli sch export netlist --format kicadxml --output "/output/{sample}.first.netlist.xml" "{source}"\n',
                f'kicad-cli sch export netlist --format kicadxml --output "/output/{sample}.repeat.netlist.xml" "{source}"\n',
            )
        )
    script = 'mkdir -p "$HOME"\n' + "".join(source_lines)
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
        "HOME=/tmp/kicad-control-input-demos",
        "-v",
        f"{synthetic_fixture_root}:/synthetic:ro",
        "-v",
        f"{output}:/output:rw",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        script,
    )
    log.event(
        "control-input-demo/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        samples=",".join(samples),
    )
    command = run_command(root, argv, timeout=900)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "control-input-demo/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native control demo export failed: {command.stderr or command.error}")
    log.event(
        "control-input-demo/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    for sample, (_directory, _filename, expected) in samples.items():
        candidates_by_run: dict[str, tuple[tuple[str, str, str, str], ...]] = {}
        bias_candidates_by_run: dict[
            str, tuple[tuple[str, tuple[tuple[str, str, str, str], ...], tuple[str, ...]], ...]
        ] = {}
        semantic_hashes: dict[str, str] = {}
        raw_hashes: dict[str, str] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{sample}.{run}.netlist.xml"
            manifest_path = output / f"{sample}.source-manifest.sha256"
            source_path = output / f"{sample}.source.sha256"
            if (
                not netlist_path.is_file()
                or not manifest_path.is_file()
                or not source_path.is_file()
            ):
                raise ValueError(f"Native {sample} demo omitted its source or netlist evidence")
            observed = read_netlist(netlist_path)
            if sample == "por-alias-fixture":
                if observed.pin_functions.get("U1.1") != "POR_B":
                    raise ValueError("Native POR_B fixture did not retain its exact pin function")
                if observed.pin_functions.get("U1.2") != "PORN":
                    raise ValueError("Native PORN negative control did not retain its pin function")
                if observed.pin_electrical_types.get("U1.1") != "input":
                    raise ValueError(
                        "Native POR_B fixture did not retain its input electrical type"
                    )
                if observed.pin_electrical_types.get("U1.2") != "input":
                    raise ValueError("Native PORN control did not retain its input electrical type")
                assigned = {pin.casefold() for pins in observed.nets.values() for pin in pins}
                if {"u1.1", "u1.2"} & assigned:
                    raise ValueError("Native POR alias fixture pins must remain unassigned")
            candidates = unconnected_control_inputs(observed)
            candidates_by_run[run] = tuple(
                (item.pin, item.function, item.family, item.electrical_type) for item in candidates
            )
            bias_candidates_by_run[run] = tuple(
                (
                    gap.net,
                    tuple(
                        (item.pin, item.function, item.family, item.electrical_type)
                        for item in gap.controls
                    ),
                    gap.output_capable_peers,
                )
                for gap in connected_control_inputs_without_visible_rail_resistor(observed)
            )
            raw_hashes[run] = digest(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            semantic_hashes[run] = hashlib.sha256(normalized).hexdigest()

        if candidates_by_run["first"] != expected or candidates_by_run["repeat"] != expected:
            raise ValueError(
                f"Native {sample} control findings changed: "
                f"first={candidates_by_run['first']}, repeat={candidates_by_run['repeat']}"
            )
        if bias_candidates_by_run["first"] != bias_candidates_by_run["repeat"]:
            raise ValueError(
                f"Native {sample} connected-control bias candidates changed between exports"
            )
        if semantic_hashes["first"] != semantic_hashes["repeat"]:
            raise ValueError(f"Native {sample} parsed netlist changed between repeated exports")

        manifest = output / f"{sample}.source-manifest.sha256"
        source_digest = output / f"{sample}.source.sha256"
        candidate_text = ";".join("|".join(item) for item in expected) or "none"
        bias_candidate_records = [
            {
                "net": net,
                "controls": [
                    {
                        "pin": pin,
                        "function": function,
                        "family": family,
                        "electrical_type": electrical_type,
                    }
                    for pin, function, family, electrical_type in controls
                ],
                "output_capable_peers": list(peers),
            }
            for net, controls, peers in bias_candidates_by_run["first"]
        ]
        bias_candidate_json = json.dumps(
            bias_candidate_records,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        bias_candidate_sha256 = hashlib.sha256(bias_candidate_json.encode("utf-8")).hexdigest()
        log.event(
            f"control-input-demo/{sample}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_digest.read_text(encoding="utf-8").strip(),
            source_manifest_sha256=digest(manifest),
            source_manifest_entries=str(len(manifest.read_text(encoding="utf-8").splitlines())),
            raw_netlist_sha256=raw_hashes["first"],
            repeat_raw_netlist_sha256=raw_hashes["repeat"],
            normalized_netlist_sha256=semantic_hashes["first"],
            repeat_normalized_netlist_sha256=semantic_hashes["repeat"],
            review_candidates=candidate_text,
            connected_bias_candidate_count=str(len(bias_candidate_records)),
            connected_bias_candidates_sha256=bias_candidate_sha256,
            connected_bias_candidates=bias_candidate_json,
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

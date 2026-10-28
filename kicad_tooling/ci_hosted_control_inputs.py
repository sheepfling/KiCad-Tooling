"""Hosted native control-input fixture lane."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_model, write_model
from .hwrepo.control_input_bias import control_input_bias_heuristic_coverage
from .hwrepo.control_input_checks import control_input_checks
from .hwrepo.control_input_inventory import (
    connected_control_inputs_without_visible_rail_resistor,
    unconnected_control_inputs,
)
from .hwrepo.control_input_models import ControlInputsAnalysis
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .validate import read_netlist


def native_control_input_demo_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
    sample_names: frozenset[str] | None = None,
) -> None:
    """Check unconnected controls in public demos bundled in pinned KiCad 10.0.5."""

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
            "/synthetic/control-input-alias",
            "por-b.kicad_sch",
            (("U1.1", "POR_B", "reset", "input"),),
        ),
        "series-bias-fixture": (
            "/synthetic/control-input-alias",
            "series-bias-control.kicad_sch",
            (),
        ),
        "bootstrap-capacitor-fixture": (
            "/synthetic/control-input-alias",
            "bare-boot-bootstrap-capacitor.kicad_sch",
            (),
        ),
        "bootstrap-small-capacitor-fixture": (
            "/synthetic/control-input-alias",
            "bare-boot-bootstrap-small-capacitor.kicad_sch",
            (),
        ),
        "array-bias-control-fixture": (
            "/synthetic/control-input-array-native",
            "control.kicad_sch",
            (),
        ),
        "array-bias-fault-fixture": (
            "/synthetic/control-input-array-native",
            "fault.kicad_sch",
            (),
        ),
    }
    if sample_names is not None:
        unknown = sample_names - samples.keys()
        if unknown:
            raise ValueError(f"Unknown native control-input demo samples: {sorted(unknown)}")
        samples = {name: sample for name, sample in samples.items() if name in sample_names}
        if not samples:
            raise ValueError("Native control-input demo selection must include at least one sample")
    synthetic_fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint"
    control_alias_fixture_root = synthetic_fixture_root / "control-input-alias"
    control_array_fixture_root = synthetic_fixture_root / "control-input-array-native"
    if not (control_alias_fixture_root / "por-b.kicad_sch").is_file():
        raise ValueError("Synthetic POR_B native control fixture is missing")
    if not (control_alias_fixture_root / "bare-boot-bootstrap-capacitor.kicad_sch").is_file():
        raise ValueError("Synthetic bootstrap capacitor native control fixture is missing")
    if not (control_alias_fixture_root / "bare-boot-bootstrap-small-capacitor.kicad_sch").is_file():
        raise ValueError("Synthetic small-capacitor native control fixture is missing")
    control_array_contract_path = control_array_fixture_root / "control-inputs.json"
    if not control_array_contract_path.is_file():
        raise ValueError("Synthetic control-bias array contract is missing")
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
        array_bias_check_statuses: dict[str, str] = {}
        array_bias_coverage_statuses: dict[str, str] = {}
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
            if sample in {"array-bias-control-fixture", "array-bias-fault-fixture"}:
                spec = read_model(control_array_contract_path, ControlInputsAnalysis)
                checks = {item.id: item for item in control_input_checks(spec, observed)}
                bias_check = checks["control-inputs/main-reset/bias"]
                expected_check = "PASS" if sample == "array-bias-control-fixture" else "FAIL"
                if bias_check.status != expected_check:
                    raise ValueError(
                        f"Native {sample} array-bias contract is {bias_check.status}: "
                        f"{bias_check.detail}"
                    )
                array_bias_check_statuses[run] = bias_check.status
                coverage = control_input_bias_heuristic_coverage(
                    observed,
                    netlist_sha256=digest(netlist_path),
                    source_path=(
                        "tests/fixtures/design_lint/control-input-array-native/control-inputs.json"
                    ),
                    source_sha256=digest(control_array_contract_path),
                    state="ready",
                    spec=spec,
                )
                if len(coverage.entries) != 1:
                    raise ValueError(f"Native {sample} did not produce one reset-bias prompt")
                entry_status = coverage.entries[0].status
                expected_entry_status = (
                    "COVERED" if sample == "array-bias-control-fixture" else "OPEN"
                )
                if entry_status != expected_entry_status:
                    raise ValueError(
                        f"Native {sample} heuristic coverage is {entry_status}; "
                        f"expected {expected_entry_status}"
                    )
                array_bias_coverage_statuses[run] = entry_status
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
            if sample == "series-bias-fixture":
                if observed.pin_functions.get("U1.1") != "RESET_N":
                    raise ValueError("Native series-bias fixture lost its RESET_N pin function")
                if observed.pin_electrical_types.get("U1.1") != "input":
                    raise ValueError("Native series-bias fixture lost its reset input type")
                dnp = {reference.upper() for reference in observed.dnp_components}
                if "U2" not in dnp:
                    raise ValueError("Native series-bias fixture lost its DNP control")
                nets_by_label = {
                    net.lstrip("/").casefold(): pins for net, pins in observed.nets.items()
                }
                if set(nets_by_label.get("reset_bias_mid", ())) != {"R1.2", "R2.1"}:
                    raise ValueError(
                        "Native series-bias fixture intermediate net is not unbranched"
                    )
                if "U1.1" not in nets_by_label.get("reset_n", ()):
                    raise ValueError("Native series-bias fixture reset pin has no net assignment")
            if sample in {
                "bootstrap-capacitor-fixture",
                "bootstrap-small-capacitor-fixture",
            }:
                if observed.pin_functions.get("U1.1") != "BOOT":
                    raise ValueError("Native bootstrap fixture lost the exact bare BOOT alias")
                if observed.pin_electrical_types.get("U1.1") != "input":
                    raise ValueError("Native bootstrap fixture lost its BOOT input electrical type")
                if observed.pin_functions.get("U1.2") != "SW":
                    raise ValueError("Native bootstrap fixture lost its switch-node pin")
                if observed.pin_electrical_types.get("U1.2") != "output":
                    raise ValueError("Native bootstrap fixture lost its SW output electrical type")
                expected_capacitor_symbol = (
                    "Device:C_Small"
                    if sample == "bootstrap-small-capacitor-fixture"
                    else "Device:C"
                )
                if observed.component_symbols.get("C1") != expected_capacitor_symbol:
                    raise ValueError("Native bootstrap fixture lost its exact capacitor symbol")
                capacitor_pins = observed.component_pin_numbers.get("C1", ())
                if len(capacitor_pins) != 2 or set(capacitor_pins) != {"1", "2"}:
                    raise ValueError("Native bootstrap fixture lost its two-pin inventory")
                dnp = {reference.casefold() for reference in observed.dnp_components}
                if "c1" in dnp:
                    raise ValueError("Native bootstrap fixture capacitor must be fitted")
                pins_by_net = {net: set(pins) for net, pins in observed.nets.items()}
                boot_nets = {net for net, pins in pins_by_net.items() if "U1.1" in pins}
                switch_nets = {net for net, pins in pins_by_net.items() if "U1.2" in pins}
                if len(boot_nets) != 1 or len(switch_nets) != 1 or boot_nets == switch_nets:
                    raise ValueError("Native bootstrap fixture endpoints must use distinct nets")
                boot_net = next(iter(boot_nets))
                switch_net = next(iter(switch_nets))
                if "C1.1" not in pins_by_net[boot_net] or "C1.2" not in pins_by_net[switch_net]:
                    raise ValueError("Native bootstrap capacitor must bridge BOOT and SW nets")
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
        if len(set(array_bias_check_statuses.values())) > 1:
            raise ValueError(f"Native {sample} array-bias check changed between exports")
        if len(set(array_bias_coverage_statuses.values())) > 1:
            raise ValueError(f"Native {sample} array-bias coverage changed between exports")

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
            array_bias_check_status=array_bias_check_statuses.get("first", "NOT_RUN"),
            array_bias_coverage_status=array_bias_coverage_statuses.get("first", "NOT_RUN"),
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

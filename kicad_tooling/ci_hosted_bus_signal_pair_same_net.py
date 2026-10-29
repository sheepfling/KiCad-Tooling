"""Digest-pinned native runner for two-wire bus same-net fixtures."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_bus_signal_pair_models import BusSignalPairFixtureExpectation
from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .validate import read_netlist


def bus_signal_pair_same_net_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
    fixture: BusSignalPairFixtureExpectation,
    event_prefix: str | None = None,
) -> None:
    """Repeat source-bound netlist/ERC exports and compare a typed review result."""
    protocol = fixture.protocol
    pair_name = fixture.pair_name
    root = root.resolve()
    if (version, image) not in KICAD_10_NATIVE_TOOLCHAINS:
        raise ValueError(f"{protocol} same-net fixtures do not cover KiCad {version}")
    cases = ("fault", "control")
    case_expectations = (("fault", fixture.fault), ("control", fixture.control))
    expected_source_hashes = {
        case: expectation.source_sha256 for case, expectation in case_expectations
    }
    pinned = pinned_image(image)
    repository = tooling_checkout_root()
    fixture_root = repository / "tests/fixtures/design_lint" / fixture.fixture_directory
    sources = {case: fixture_root / f"{case}.kicad_sch" for case in cases}
    actual_source_hashes = {case: digest(source) for case, source in sources.items()}
    if actual_source_hashes != expected_source_hashes:
        raise ValueError(f"{protocol} same-net fixture sources differ from reviewed hashes")
    expected_pin_functions = {item.reference: item.function for item in fixture.pin_functions}

    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"{protocol}-{pair_name}-same-net-{version}-",
            dir=log.directory.resolve(),
        )
    )
    inputs = scratch / "input"
    inputs.mkdir()
    output = scratch / "output"
    output.mkdir()
    for case, source in sources.items():
        shutil.copyfile(source, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != actual_source_hashes[case]:
            raise ValueError(f"Synthetic {protocol} {case} source changed while staging")
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{version}"\n'
        "for case in fault control; do\n"
        "  for run in first repeat; do\n"
        '    kicad-cli sch export netlist --format kicadxml --output "/output/$case.$run.netlist.xml" '
        '"/fixtures/$case.kicad_sch"\n'
        '    kicad-cli sch erc --format json --severity-all --output "/output/$case.$run.erc.json" '
        '"/fixtures/$case.kicad_sch"\n'
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
        f"HOME=/tmp/kicad-{protocol}-{pair_name}-same-net",
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
    stage_prefix = event_prefix or f"{protocol}-{pair_name}-same-net-fixture"
    log.event(
        f"{stage_prefix}/native-export",
        "START",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        error = command.stderr or command.error or f"exit {command.returncode}"
        log.event(
            f"{stage_prefix}/native-export",
            "FAIL",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=error,
        )
        raise ValueError(f"Native {protocol} same-net export failed: {error}")

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    findings: dict[tuple[str, str], tuple[str, ...]] = {}
    erc_errors: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted {protocol} same-net {case} evidence")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            if observed.pin_functions != dict(expected_pin_functions):
                raise ValueError(f"Native {protocol} {case} pin-function inventory changed")
            case_expectation = fixture.fault if case == "fault" else fixture.control
            expected_net_assignments = {
                item.name: item.pins for item in case_expectation.net_assignments
            }
            if any(
                observed.nets.get(net) != pins for net, pins in expected_net_assignments.items()
            ):
                raise ValueError(f"Native {protocol} {case} net assignments changed")
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version:
                raise ValueError(f"Native ERC version mismatch for {protocol} {case}")
            erc_errors[(case, run)] = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            project_id = f"synthetic-{protocol}-{pair_name}-same-net-{case}"
            report = evaluate(
                project_id,
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=project_id,
                    observed=observed,
                    netlist_sha256=raw_hashes[(case, run)],
                ),
                DesignLintPolicy(),
            )
            findings[(case, run)] = tuple(
                item.subject for item in report.findings if item.rule_id == fixture.rule_id
            )

    for case in cases:
        case_expectation = fixture.fault if case == "fault" else fixture.control
        first = normalized_hashes[(case, "first")]
        repeat = normalized_hashes[(case, "repeat")]
        expected = case_expectation.subjects
        if (
            first != repeat
            or erc_errors[(case, "first")] != erc_errors[(case, "repeat")]
            or erc_errors[(case, "first")]
            or findings[(case, "first")] != expected
            or findings[(case, "repeat")] != expected
        ):
            raise ValueError(
                f"Native {protocol} same-net {case} differs from reviewed expectations"
            )
        log.event(
            f"{stage_prefix}/{case}",
            "PASS",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            source_sha256=actual_source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=first,
            repeat_normalized_netlist_sha256=repeat,
            erc_errors="none",
            repeatable="true",
            subjects=";".join(expected) if expected else "none",
        )
    log.event(
        f"{stage_prefix}/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        source_hashes=",".join(f"{case}:{actual_source_hashes[case]}" for case in cases),
        command_receipt=receipt.relative_to(root).as_posix(),
        repeatable="true",
    )
    log.finish()


def bus_signal_pair_topology_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
    fixture: BusSignalPairFixtureExpectation,
    event_prefix: str,
) -> None:
    """Run exact-version native exports for a typed two-endpoint topology case."""
    bus_signal_pair_same_net_fixture_lane(
        root,
        version=version,
        image=image,
        log=log,
        fixture=fixture,
        event_prefix=event_prefix,
    )

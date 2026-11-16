"""Digest-pinned native fixtures for Ethernet PHY receive-data-output sharing review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.models import DesignLintPolicy
from .hwrepo.native_report_parsing import read_netlist

ETHERNET_RX_OUTPUT_SHARING_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
RULE_ID = "bus.ethernet_rx_outputs_share_net"
CLOCK_RULE_ID = "bus.ethernet_rx_clock_outputs_share_net"
STATUS_RULE_ID = "bus.ethernet_rx_status_outputs_share_net"


def ethernet_rx_output_sharing_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Repeat native exports for shared-RXD/RXC faults and separate controls."""
    root = root.resolve()
    if (version, image) not in ETHERNET_RX_OUTPUT_SHARING_TOOLCHAINS:
        raise ValueError(
            f"Ethernet RX-sharing fixtures do not cover KiCad {version} with this image"
        )
    pinned = pinned_image(image)
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint/ethernet-rx-output-sharing"
    sources = {
        "fault": fixture_root / "fault.kicad_sch",
        "control": fixture_root / "control.kicad_sch",
    }
    source_hashes = {case: digest(source) for case, source in sources.items()}
    expected_hashes = {
        "fault": "b338af0a3373c57c2f636c44eb3ae8e5e05764fe16590a77cae6043da25af82e",
        "control": "bee79ef0035f002944aeaf2453c398aebd101c2a39493d6cb73f04890f448d79",
    }
    if source_hashes != expected_hashes:
        raise ValueError("Ethernet RX-sharing fixture sources changed from their reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"ethernet-rx-output-sharing-{version}-", dir=log.directory.resolve()
        )
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        target = inputs / f"{case}.kicad_sch"
        shutil.copyfile(source, target)
        if digest(target) != source_hashes[case]:
            raise ValueError(f"Synthetic Ethernet RX-sharing {case} source changed during setup")
    output = scratch / "output"
    output.mkdir()
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
        "HOME=/tmp/kicad-ethernet-rx-output-sharing",
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
        "ethernet-rx-output-sharing-fixture/native-export",
        "START",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "ethernet-rx-output-sharing-fixture/native-export",
            "FAIL",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native Ethernet RX-sharing export failed: {command.stderr or command.error}"
        )

    normalized_hashes: dict[tuple[str, str], str] = {}
    subjects: dict[tuple[str, str, str], tuple[str, ...]] = {}
    erc_errors: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted an Ethernet RX-sharing {case} output")
            observed = read_netlist(netlist_path)
            if case == "fault" and run == "first":
                for reference in ("U1", "U2"):
                    if observed.pin_functions.get(f"{reference}.1") != "RXD0":
                        raise ValueError(
                            "Native Ethernet RX-sharing fault lost its RXD0 pin function"
                        )
                    if observed.components[reference].value != "Ethernet PHY module":
                        raise ValueError(
                            "Native Ethernet RX-sharing fault lost its explicit identity"
                        )
                    if observed.pin_electrical_types.get(f"{reference}.1") != "passive":
                        raise ValueError(
                            "Native Ethernet RX-sharing fixture no longer isolates ERC typing"
                        )
                    if observed.pin_functions.get(f"{reference}.3") != "RXC":
                        raise ValueError(
                            "Native Ethernet RX-sharing fault lost its RXC pin function"
                        )
                    if observed.pin_electrical_types.get(f"{reference}.3") != "passive":
                        raise ValueError(
                            "Native Ethernet RXC fixture no longer isolates ERC typing"
                        )
                    if observed.pin_functions.get(f"{reference}.4") != "RXDV":
                        raise ValueError(
                            "Native Ethernet RX-sharing fault lost its RXDV pin function"
                        )
                    if observed.pin_electrical_types.get(f"{reference}.4") != "passive":
                        raise ValueError(
                            "Native Ethernet RXDV fixture no longer isolates ERC typing"
                        )
                    if reference in observed.dnp_components:
                        raise ValueError(
                            "Native Ethernet RX-sharing endpoint unexpectedly became DNP"
                        )
                if set(observed.nets.get("ETH_RXD_SHARED", ())) != {"U1.1", "U2.1"}:
                    raise ValueError(
                        "Native Ethernet RX-sharing fault did not preserve the shared net"
                    )
                if set(observed.nets.get("MII_RX_CLK_SHARED", ())) != {"U1.3", "U2.3"}:
                    raise ValueError(
                        "Native Ethernet RX-sharing fault did not preserve the shared RXC net"
                    )
                if set(observed.nets.get("MII_RX_DV_SHARED", ())) != {"U1.4", "U2.4"}:
                    raise ValueError(
                        "Native Ethernet RX-sharing fault did not preserve the shared RXDV net"
                    )
            if case == "control" and run == "first":
                if set(observed.nets.get("RXD0_TXD_LINK", ())) != {"U1.1", "U2.2"}:
                    raise ValueError(
                        "Native Ethernet RX-sharing control did not preserve the unlike-role link"
                    )
                if observed.nets.get("PHY2_RXD0") != ("U2.1",):
                    raise ValueError(
                        "Native Ethernet RX-sharing control unexpectedly joins both RXD pins"
                    )
                if observed.nets.get("PHY1_RX_CLK") != ("U1.3",):
                    raise ValueError("Native Ethernet control did not isolate U1.RXC")
                if observed.nets.get("PHY2_RX_CLK") != ("U2.3",):
                    raise ValueError("Native Ethernet control did not isolate U2.RXC")
                if observed.nets.get("PHY1_RX_DV") != ("U1.4",):
                    raise ValueError("Native Ethernet control did not isolate U1.RXDV")
                if observed.nets.get("PHY2_RX_DV") != ("U2.4",):
                    raise ValueError("Native Ethernet control did not isolate U2.RXDV")
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version:
                raise ValueError(f"Native ERC version mismatch for Ethernet RX-sharing {case}")
            erc_errors[(case, run)] = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            project_id = f"synthetic-ethernet-rx-output-sharing-{case}"
            report = evaluate(
                project_id,
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=project_id,
                    observed=observed,
                    netlist_sha256=digest(netlist_path),
                ),
                DesignLintPolicy(),
            )
            for rule_id in (RULE_ID, CLOCK_RULE_ID, STATUS_RULE_ID):
                subjects[(case, run, rule_id)] = tuple(
                    item.subject for item in report.findings if item.rule_id == rule_id
                )

    expected_subjects = {
        RULE_ID: {
            "fault": ("U1, U2: Ethernet PHY receive-data outputs share ETH_RXD_SHARED",),
            "control": (),
        },
        CLOCK_RULE_ID: {
            "fault": ("U1, U2: Ethernet PHY receive-clock outputs share MII_RX_CLK_SHARED",),
            "control": (),
        },
        STATUS_RULE_ID: {
            "fault": ("U1, U2: Ethernet PHY receive-status outputs share MII_RX_DV_SHARED",),
            "control": (),
        },
    }
    for case in sources:
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(
                f"Native Ethernet RX-sharing {case} netlists differ after normalization"
            )
        if erc_errors[(case, "first")] != erc_errors[(case, "repeat")]:
            raise ValueError(f"Native Ethernet RX-sharing {case} ERC results differ on repeat")
        if erc_errors[(case, "first")]:
            raise ValueError(f"Native ERC reported Ethernet RX-sharing {case} errors")
        for rule_id, cases in expected_subjects.items():
            if subjects[(case, "first", rule_id)] != cases[case]:
                raise ValueError(
                    f"Native Ethernet RX-sharing {case} for {rule_id} produced "
                    f"{subjects[(case, 'first', rule_id)]!r}; expected {cases[case]!r}"
                )
            if subjects[(case, "repeat", rule_id)] != subjects[(case, "first", rule_id)]:
                raise ValueError(
                    f"Native Ethernet RX-sharing {case} findings differ on repeat for {rule_id}"
                )
        log.event(
            f"ethernet-rx-output-sharing-fixture/{case}",
            "PASS",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            erc_errors="none",
            repeatable="true",
            subjects=";".join(
                f"{rule_id}={'|'.join(subjects[(case, 'first', rule_id)]) or 'none'}"
                for rule_id in expected_subjects
            ),
        )
    log.event(
        "ethernet-rx-output-sharing-fixture/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()

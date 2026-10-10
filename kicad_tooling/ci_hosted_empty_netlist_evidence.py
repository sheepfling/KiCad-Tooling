"""Hosted synthetic empty-netlist evidence fixture."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def empty_netlist_evidence_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify the native empty-netlist trigger on each supported project image."""
    import hashlib
    import json
    import os
    import shutil
    import sys
    import tempfile

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import NetlistContract
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Empty-netlist evidence fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)

    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    fixtures = {
        "empty": (
            fixture_root / "empty-native-netlist/empty.kicad_sch",
            "ed107ec68043c2eb02fa6566b289b35f119b37c3296bbd1a0f12705ba36b2c9b",
        ),
        "nonempty-control": (
            fixture_root
            / "serial-peer-connector-reference-native/serial-connector-control.kicad_sch",
            "7d086f4f838504fa3cefc906f7f9e415240b10d89e95c9063c19780922915f16",
        ),
    }
    scratch = Path(
        tempfile.mkdtemp(prefix=f"empty-netlist-evidence-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    source_hashes: dict[str, str] = {}
    for case, (fixture, expected_hash) in fixtures.items():
        target = inputs / f"{case}.kicad_sch"
        shutil.copyfile(fixture, target)
        source_hash = digest(target)
        if source_hash != expected_hash:
            raise ValueError(f"Synthetic {case} schematic changed from its reviewed hash")
        source_hashes[case] = source_hash
    output = scratch / "output"
    output.mkdir()

    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{config.kicad_version}"\n'
        "for case in empty nonempty-control; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
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
        "HOME=/tmp/kicad-empty-netlist-evidence",
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
        "empty-netlist-evidence/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "empty-netlist-evidence/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            error=command.error or command.stderr or command.stdout,
        )
        raise ValueError(f"Native empty-netlist fixture export failed for {project}")
    log.event(
        "empty-netlist-evidence/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        returncode=command.returncode,
    )

    for case in fixtures:
        reports: list[NetlistContract] = []
        raw_hashes: list[str] = []
        normalized_bytes: list[bytes] = []
        for run in ("first", "repeat"):
            path = output / f"{case}.{run}.netlist.xml"
            raw_hashes.append(digest(path))
            observed = read_netlist(path)
            reports.append(observed)
            normalized_bytes.append(
                json.dumps(
                    observed.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
        if normalized_bytes[0] != normalized_bytes[1]:
            raise ValueError(f"Native {case} exports differ after netlist normalization")
        observed = reports[0]
        if case == "empty" and (observed.components or observed.nets):
            raise ValueError("Synthetic empty schematic unexpectedly exported components or nets")
        if case != "empty" and not observed.components:
            raise ValueError("Synthetic nonempty control exported no component records")
        normalized_hash = hashlib.sha256(normalized_bytes[0]).hexdigest()
        repeat_normalized_hash = hashlib.sha256(normalized_bytes[1]).hexdigest()
        log.event(
            f"empty-netlist-evidence/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[0],
            repeat_netlist_sha256=raw_hashes[1],
            normalized_netlist_sha256=normalized_hash,
            repeat_normalized_netlist_sha256=repeat_normalized_hash,
            component_count=len(observed.components),
            net_count=len(observed.nets),
            repeatable="true",
            repeatability_basis="canonical_typed_netlist",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

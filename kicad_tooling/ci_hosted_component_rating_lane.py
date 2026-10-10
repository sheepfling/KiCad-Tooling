"""Run the pinned native exports shared by component-rating lint fixtures."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_component_power_rating_fixture import verify_component_power_rating_fixture
from .ci_hosted_component_rating_context import ComponentRatingFixtureContext
from .ci_hosted_component_voltage_rating_fixture import verify_component_voltage_rating_fixture
from .ci_hosted_connector_contact_rating_fixture import verify_connector_contact_rating_fixture
from .ci_hosted_mosfet_stress_fixture import verify_mosfet_stress_fixture
from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def component_rating_fixtures_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Verify authored component voltage, power, and contact limits on native netlists."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Component and connector rating fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/component-voltage-ratings"
    )
    fixture = fixture_root / "rating-control.kicad_sch"
    fixture_sha256 = digest(fixture)
    power_fixture = fixture_root / "power-control.kicad_sch"
    power_fixture_sha256 = digest(power_fixture)
    contact_fixture = fixture_root / "contact-control.kicad_sch"
    contact_fixture_sha256 = digest(contact_fixture)
    mosfet_fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/mosfet-stress"
    )
    mosfet_fixture = mosfet_fixture_root / "mosfet.kicad_sch"
    mosfet_fixture_sha256 = digest(mosfet_fixture)
    scratch = Path(
        tempfile.mkdtemp(prefix=f"component-voltage-rating-{project}-", dir=log.directory.resolve())
    )
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    source = "".join(
        (
            'mkdir -p "$HOME"\n',
            'actual="$(kicad-cli version)"\n',
            'printf "kicad_version=%s\\n" "$actual"\n',
            f'test "$actual" = "{config.kicad_version}"\n',
            (
                "for run in first repeat; do kicad-cli sch export netlist "
                '--format kicadxml --output "/output/rating.${run}.netlist.xml" '
                '"/fixtures/rating-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch erc --format json --severity-all "
                '--output "/output/rating.${run}.erc.json" '
                '"/fixtures/rating-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch export netlist "
                '--format kicadxml --output "/output/power.${run}.netlist.xml" '
                '"/fixtures/power-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch erc --format json --severity-all "
                '--output "/output/power.${run}.erc.json" '
                '"/fixtures/power-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch export netlist "
                '--format kicadxml --output "/output/contact.${run}.netlist.xml" '
                '"/fixtures/contact-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch erc --format json --severity-all "
                '--output "/output/contact.${run}.erc.json" '
                '"/fixtures/contact-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch export netlist "
                '--format kicadxml --output "/output/mosfet.${run}.netlist.xml" '
                '"/mosfet-fixture/mosfet.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch erc --format json --severity-all "
                '--output "/output/mosfet.${run}.erc.json" '
                '"/mosfet-fixture/mosfet.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch export netlist "
                '--format kicadxml --output "/output/power.${run}.netlist.xml" '
                '"/fixtures/power-control.kicad_sch"; done\n'
            ),
            (
                "for run in first repeat; do kicad-cli sch erc --format json --severity-all "
                '--output "/output/power.${run}.erc.json" '
                '"/fixtures/power-control.kicad_sch"; done\n'
            ),
        )
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
        "HOME=/tmp/kicad-component-voltage-rating-fixture",
        "-v",
        f"{fixture_root.resolve()}:/fixtures:ro",
        "-v",
        f"{mosfet_fixture_root.resolve()}:/mosfet-fixture:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        source,
    )
    log.event(
        "component-voltage-rating-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "component-voltage-rating-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native component voltage-rating fixture command failed: "
            f"{command.stderr or command.error}"
        )

    context = ComponentRatingFixtureContext(
        root=root,
        project=project,
        config=config,
        pinned=pinned,
        fixture_root=fixture_root,
        fixture=fixture,
        fixture_sha256=fixture_sha256,
        power_fixture=power_fixture,
        power_fixture_sha256=power_fixture_sha256,
        contact_fixture=contact_fixture,
        contact_fixture_sha256=contact_fixture_sha256,
        mosfet_fixture_root=mosfet_fixture_root,
        mosfet_fixture=mosfet_fixture,
        mosfet_fixture_sha256=mosfet_fixture_sha256,
        scratch=scratch,
        output=output,
    )
    verify_component_voltage_rating_fixture(context, log)
    verify_component_power_rating_fixture(context, log)
    verify_connector_contact_rating_fixture(context, log)
    verify_mosfet_stress_fixture(context, log)

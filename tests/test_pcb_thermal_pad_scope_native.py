"""Digest-pinned KiCad exports for exact exposed-pad pin functions."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contract_coach import pinned_image, run_command
from kicad_tooling.hwrepo.design_lint_pcb_thermal_pad_scope import (
    explicit_thermal_pad_scope_candidates,
)
from kicad_tooling.hwrepo.native_report_parsing import read_netlist
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.pcb_thermal_vias_support import mapping, requirement

RULE_ID = "pcb.explicit_thermal_pad_scope_unreviewed"
FIXTURE = Path(__file__).parent / "fixtures/design_lint/thermal-pad-scope/exposed-pad.kicad_sch"
FIXTURE_SHA256 = "7473c405de142ff363699b1953d3b39cfbfcdcfd68733ff67e65a781d92ac754"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLCHAINS = (
    pytest.param(
        "10.0.0",
        "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        id="kicad-10.0.0",
    ),
    pytest.param(
        "10.0.5",
        "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
        id="kicad-10.0.5",
    ),
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_THERMAL_PAD_SCOPE") != "1",
        reason="native thermal-pad scope exports run in the digest-pinned acceptance lane",
    ),
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


@pytest.mark.parametrize(("version", "image"), TOOLCHAINS)
def test_native_pin_functions_trigger_only_the_fitted_exposed_pad_prompt(
    tmp_path: Path, version: str, image: str
) -> None:
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256
    output = tmp_path / "output"
    output.mkdir()
    user = () if sys.platform == "win32" else ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        f'test "$actual" = "{version}"\n'
        "for run in first repeat; do\n"
        "  kicad-cli sch export netlist --format kicadxml "
        '    --output "/output/$run.netlist.xml" /fixtures/exposed-pad.kicad_sch\n'
        "done\n"
    )
    command = run_command(
        PROJECT_ROOT,
        (
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
            "HOME=/tmp/kicad-thermal-pad-scope",
            "-v",
            f"{FIXTURE.parent}:/fixtures:ro",
            "-v",
            f"{output}:/output:rw",
            "-w",
            "/fixtures",
            "--entrypoint",
            "/bin/sh",
            pinned_image(image),
            "-ec",
            script,
        ),
        timeout=300,
    )
    assert command.returncode == 0, command.error or command.stderr or command.stdout
    first_path = output / "first.netlist.xml"
    repeat_path = output / "repeat.netlist.xml"
    first = read_netlist(first_path)
    repeat = read_netlist(repeat_path)

    def normalized(report: NetlistContract) -> str:
        return json.dumps(report.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    assert normalized(first) == normalized(repeat)
    assert first.pin_functions["U1.9"] == "EP"
    assert first.pin_functions["U1.8"] == "THERMAL_ALERT"
    assert first.dnp_components == ("U2",)
    findings = explicit_thermal_pad_scope_candidates(first, None)
    assert tuple(item.evidence["pin"] for item in findings) == (("U1.9",),)
    assert explicit_thermal_pad_scope_candidates(first, mapping(requirement(pad="U1.9"))) == ()

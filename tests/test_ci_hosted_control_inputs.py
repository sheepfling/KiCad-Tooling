"""Digest-pinned native control-input fixture regressions."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from kicad_tooling.ci_hosted import HostedLog, native_control_input_demo_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.support import reference_root

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_CONTROL_INPUT_FIXTURES") != "1",
        reason="native control-input demos run in the digest-pinned package acceptance lane",
    ),
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

_EXPECTED_CASES = (
    ("cm5-minima", "none", 4, "7c96b511e8fa95eef6dc8fff36c45e92c34e1cfbcc54db7400a2e3149fdd9709"),
    (
        "jetson-agx-thor",
        "J14.23|SDIO_~{RESET}|reset|input",
        24,
        "04bd60403bf87f8a4edf249d582a5b7620974dd333b53e5e80c6db9af8dc9f71",
    ),
    (
        "coldfire-xilinx",
        "VR201.4|SHDN|enable|input",
        2,
        "371dfc8d9313aabf215947750e2ad170d9c5b69f6f03a171ae90e81a73bfb929",
    ),
    (
        "vme-wren",
        (
            "IC19.3|~{RESET}|reset|input;IC21.3|~{RESET}|reset|input;"
            "IC30.33|BOOT_B|boot/strap|input;IC30.38|BOOT_A|boot/strap|input"
        ),
        12,
        "2ee541b32622143b5293f6add4da0d0c6b32137ec15521fd2bafb6fe9e3df050",
    ),
    (
        "por-alias-fixture",
        "U1.1|POR_B|reset|input",
        0,
        "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    ),
    (
        "series-bias-fixture",
        "none",
        0,
        "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    ),
)


@pytest.fixture(scope="module")
def native_control_input_demo_run(
    request: pytest.FixtureRequest,
) -> tuple[str, dict[str, Any]]:
    """Export selected samples once, sharing one exact-version native run."""
    selected: set[str] = set()
    for item in request.session.items:
        if getattr(item, "module", None) is not request.module:
            continue
        callspec = getattr(item, "callspec", None)
        if callspec is None:
            continue
        sample = callspec.params.get("sample")
        if isinstance(sample, str):
            selected.add(sample)
    selected_samples = frozenset(selected)
    assert selected_samples, "The native demo fixture requires a selected sample case"

    repository = Path(__file__).resolve().parents[1]
    acceptance = repository / "build/ci"
    acceptance.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="native-control-input-demo-", dir=acceptance))
    shutil.copytree(
        reference_root(),
        root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    project = "raspberry-pi-status-led"
    config = selected_config(root, project)
    assert config.kicad_version == "10.0.5"
    log = HostedLog(root, "native-control-input-demos")
    native_control_input_demo_lane(
        root,
        project=project,
        image=config.image,
        log=log,
        sample_names=selected_samples,
    )

    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("control-input-demo/")
    }
    assert set(results) == {
        "control-input-demo/native-export",
        *(f"control-input-demo/{sample}" for sample in selected_samples),
    }

    native = results["control-input-demo/native-export"]
    assert native["status"] == "PASS"
    receipt = root / native["command_receipt"]
    assert receipt.is_file()
    command = json.loads(receipt.read_text())
    argv = command["argv"]
    assert "none" in argv
    assert "--read-only" in argv
    mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
    assert len(mounts) == 2
    assert sum(item.endswith(":/synthetic:ro") for item in mounts) == 1
    assert sum(item.endswith(":/output:rw") for item in mounts) == 1

    return config.image, results


@pytest.mark.parametrize(
    ("sample", "expected_candidates", "expected_count", "expected_sha256"),
    _EXPECTED_CASES,
    ids=tuple(case[0] for case in _EXPECTED_CASES),
)
def test_native_public_demos_record_connected_bias_and_unconnected_controls(
    native_control_input_demo_run: tuple[str, dict[str, Any]],
    sample: str,
    expected_candidates: str,
    expected_count: int,
    expected_sha256: str,
) -> None:
    image, results = native_control_input_demo_run
    result = results[f"control-input-demo/{sample}"]
    assert result["status"] == "PASS"
    assert result["kicad_version"] == "10.0.5"
    assert result["image"] == image
    assert result["review_candidates"] == expected_candidates
    bias_candidates = json.loads(result["connected_bias_candidates"])
    assert len(bias_candidates) == expected_count
    assert result["connected_bias_candidate_count"] == str(expected_count)
    canonical_bias_candidates = json.dumps(
        bias_candidates,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    assert hashlib.sha256(canonical_bias_candidates).hexdigest() == expected_sha256
    assert result["connected_bias_candidates_sha256"] == expected_sha256
    assert result["repeatable"] == "true"
    assert re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", result["source_manifest_sha256"])
    assert int(result["source_manifest_entries"]) > 0
    assert re.fullmatch(r"[0-9a-f]{64}", result["raw_netlist_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", result["repeat_raw_netlist_sha256"])
    assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]

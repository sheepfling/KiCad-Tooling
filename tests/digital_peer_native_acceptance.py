"""Run and validate the shared exact-version digital-peer fixture lane."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from types import MappingProxyType

import pytest

from kicad_tooling.ci_hosted import HostedLog, digital_peer_fixture_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.json_types import JsonObject
from tests.support import reference_root

NATIVE_DIGITAL_PEER_PROJECTS = (
    ("controller", "10.0.0"),
    ("raspberry-pi-status-led", "10.0.5"),
)
_EXPECTED_IMAGES = MappingProxyType(
    {
        "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    }
)
_EXPECTED_STAGES = frozenset(
    {
        "spi-participant-fixture/native-export",
        "spi-participant-fixture/unrostered",
        "spi-participant-fixture/rostered",
        "spi-participant-fixture/composite-unrostered",
        "spi-participant-fixture/composite-rostered",
        "spi-participant-fixture/voltage-control",
        "spi-participant-fixture/voltage-fault",
        "spi-participant-fixture/peer-control",
        "spi-participant-fixture/peer-fault",
        "spi-participant-fixture/peer-translator-control",
        "spi-participant-fixture/serial-control",
        "spi-participant-fixture/serial-fault",
        "spi-participant-fixture/serial-reference-fault",
        "spi-participant-fixture/serial-connector-control",
        "spi-participant-fixture/serial-connector-fault",
        "spi-participant-fixture/serial-optical-isolation-control",
        "spi-participant-fixture/serial-label-control",
        "spi-participant-fixture/serial-label-fault",
        "component-peer-power-fixture/control",
        "component-peer-power-fixture/fault",
    }
)
_REPEATABLE_STAGES = frozenset(_EXPECTED_STAGES - {"spi-participant-fixture/native-export"})
_EXPECTED_SOURCE_HASH = "0c5d901b4dc70ccb3c3818bd8fdf002955a6322b814ac2e7f8bab086d47d5e06"
_EXPECTED_COMBO_SPI_SOURCE_HASH = "78fb20b4e2770c1e68b16727ebd4f1014bd76c4d4d512647b38960d41f02f7ff"
_EXPECTED_COMPONENT_SOURCE_HASHES = MappingProxyType(
    {
        "component-peer-power-fixture/control": "0198205216be6cd5be0c03ac14b7c2b9de52258aacd564159e16532fadb10446",
        "component-peer-power-fixture/fault": "92a2cfda8088c7eebe8305e5ecf786870ed44bc846acb031fe4bb1d567418ae3",
    }
)
_EXPECTED_PEER_SOURCE_HASHES = MappingProxyType(
    {
        "spi-participant-fixture/peer-control": "427bfd18783c800ddc0b9e48d4ce95db8d26ac4fb27bf2a36921908016d75cdd",
        "spi-participant-fixture/peer-fault": "98ca9f8d999892b9441019064f36eba776eec18770e23519cde30ff1a532e5a4",
        "spi-participant-fixture/peer-translator-control": "58f2ac474e5c055fc5ff3f5e2f9be0613fc7339298244de035740ca85eaa80a1",
        "spi-participant-fixture/serial-control": "3c420e5cde0e0c6ee52cb5b5f63fb243237dcb846e7ac6057e61f4b30df7ff79",
        "spi-participant-fixture/serial-fault": "14f7c4097f270ed806c471df7d49f4f0dd18607de6402312920e16840f5afdd3",
        "spi-participant-fixture/serial-reference-fault": "d3c9a6e14e9bc4314c2b616e8be3962638161b1e056789ea7b66977e430081be",
        "spi-participant-fixture/serial-connector-control": "7d086f4f838504fa3cefc906f7f9e415240b10d89e95c9063c19780922915f16",
        "spi-participant-fixture/serial-connector-fault": "ee9ce9a51a78c422da96e260720247bb09403abe314921952f29c5d9ba110c20",
        "spi-participant-fixture/serial-optical-isolation-control": "2d3cfb6f98d2d97114a97c8948f6fac290f4401fac58474af8c974dbf2e1da46",
        "spi-participant-fixture/serial-label-control": "a0ac8548431af625c5116c1d456e4f2c6cf1714e58cca84c6fe595165d87c561",
        "spi-participant-fixture/serial-label-fault": "2006adbfa6c6f1c99e88e3320a1ed7230f01a02f5e143c16a946abaa34f9db20",
    }
)


def _assert_result_receipt(root: Path, result: JsonObject, *, version: str, image: str) -> None:
    assert result["kicad_version"] == version
    assert result["image"] == image
    assert result["repeatable"] == "true"
    assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
    if "compatibility_status" in result:
        expected_basis = "normalized_native_netlist_and_electrical_checks"
    elif any(
        key in result
        for key in ("peer_voltage_findings", "peer_reference_findings", "peer_power_findings")
    ):
        expected_basis = "normalized_native_netlist_and_design_lint_report"
    else:
        expected_basis = "normalized_netlist_contract"
    assert result["repeatability_basis"] == expected_basis

    receipt = root / str(result["command_receipt"])
    assert receipt.is_file()
    command = json.loads(receipt.read_text(encoding="utf-8"))
    mounts = tuple(
        command["argv"][index + 1]
        for index, item in enumerate(command["argv"][:-1])
        if item == "-v"
    )
    assert len(mounts) == 2
    assert sum(item.endswith(":/fixtures:ro") for item in mounts) == 1
    assert sum(item.endswith(":/output:rw") for item in mounts) == 1


@pytest.fixture(scope="session")
def native_digital_peer_results() -> dict[str, dict[str, JsonObject]]:
    """Run the shared native lane once for each pinned project toolchain."""
    if os.environ.get("KICAD_RUN_NATIVE_DIGITAL_PEER_FIXTURES") != "1":
        pytest.skip("native digital-peer fixtures run in the digest-pinned package acceptance lane")

    repository = Path(__file__).resolve().parents[1]
    acceptance = repository / "build/ci"
    acceptance.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="native-digital-peer-project-", dir=acceptance))
    shutil.copytree(
        reference_root(),
        root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )

    results_by_project: dict[str, dict[str, JsonObject]] = {}
    for project, expected_version in NATIVE_DIGITAL_PEER_PROJECTS:
        config = selected_config(root, project)
        assert config.kicad_version == expected_version
        assert config.image == _EXPECTED_IMAGES[project]

        log = HostedLog(root, f"native-digital-peer-{project}")
        digital_peer_fixture_lane(root, project=project, image=config.image, log=log)
        events = tuple(
            json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines()
        )
        results = {
            str(item["stage"]): item
            for item in events
            if str(item.get("stage", "")).startswith(
                ("spi-participant-fixture/", "component-peer-power-fixture/")
            )
        }
        assert set(results) == _EXPECTED_STAGES

        for stage in _REPEATABLE_STAGES:
            result = results[stage]
            _assert_result_receipt(root, result, version=expected_version, image=config.image)
            if stage in _EXPECTED_COMPONENT_SOURCE_HASHES:
                assert result["source_sha256"] == _EXPECTED_COMPONENT_SOURCE_HASHES[stage]
            elif stage in _EXPECTED_PEER_SOURCE_HASHES:
                assert result["source_sha256"] == _EXPECTED_PEER_SOURCE_HASHES[stage]
            elif stage in {
                "spi-participant-fixture/composite-unrostered",
                "spi-participant-fixture/composite-rostered",
            }:
                assert result["source_sha256"] == _EXPECTED_COMBO_SPI_SOURCE_HASH
            else:
                assert result["source_sha256"] == _EXPECTED_SOURCE_HASH

            if stage.startswith("component-peer-power-fixture/"):
                assert result["erc_report_version"] == expected_version
                assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]

        results_by_project[project] = results
    return results_by_project

"""Digest-pinned native acceptance for synthetic rating lint themes."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, component_rating_fixtures_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.support import reference_root

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES") != "1",
    reason="native component rating fixtures run in the digest-pinned package acceptance lane",
)
def test_component_and_connector_rating_controls_export_repeatably(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    root = tmp_path / "reference"
    shutil.copytree(
        reference_root(),
        root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    expected_versions = {"controller": "10.0.0", "raspberry-pi-status-led": "10.0.5"}
    expected_images = {
        "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    }
    fixture = (
        repository / "tests/fixtures/design_lint/component-voltage-ratings/rating-control.kicad_sch"
    )
    power_fixture = (
        repository / "tests/fixtures/design_lint/component-voltage-ratings/power-control.kicad_sch"
    )
    contact_fixture = (
        repository
        / "tests/fixtures/design_lint/component-voltage-ratings/contact-control.kicad_sch"
    )
    mosfet_fixture = repository / "tests/fixtures/design_lint/mosfet-stress/mosfet.kicad_sch"
    expected_fixture_sha256 = "c3dd7c1e551613664c776875e217d7580238d04f5f40fe093ff6a86b1fa82af0"
    expected_power_fixture_sha256 = (
        "0c3f36df5ce9601d5424a9928da7c13b07199c95a4c80e9c59675c96618beba1"
    )
    expected_contact_fixture_sha256 = (
        "a210495b6df2c7f43ca4d44361c6be6f022d31116dbd4efa200c76faf03f3182"
    )
    expected_mosfet_fixture_sha256 = (
        "92e70feba1b173c5cbcf8bf2bc9d820be1f7bf1116448e76b072da0b7d1119b6"
    )
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == expected_fixture_sha256
    assert hashlib.sha256(power_fixture.read_bytes()).hexdigest() == expected_power_fixture_sha256
    assert (
        hashlib.sha256(contact_fixture.read_bytes()).hexdigest() == expected_contact_fixture_sha256
    )
    assert hashlib.sha256(mosfet_fixture.read_bytes()).hexdigest() == expected_mosfet_fixture_sha256
    normalized_hashes: dict[str, str] = {}
    power_normalized_hashes: dict[str, str] = {}
    contact_normalized_hashes: dict[str, str] = {}
    mosfet_normalized_hashes: dict[str, str] = {}
    for project, version in expected_versions.items():
        config = selected_config(root, project)
        assert config.kicad_version == version
        assert config.image == expected_images[project]
        log = HostedLog(root, f"native-component-rating-{project}")
        component_rating_fixtures_lane(root, project=project, image=config.image, log=log)
        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("component-voltage-rating-fixture/")
        }
        assert set(results) == {
            "component-voltage-rating-fixture/native-export",
            "component-voltage-rating-fixture/control",
            "component-voltage-rating-fixture/over-limit-fault",
        }
        native = results["component-voltage-rating-fixture/native-export"]
        assert native["status"] == "PASS"
        assert native["fixture_sha256"] == expected_fixture_sha256
        assert native["kicad_version"] == version
        assert native["image"] == expected_images[project]
        assert native["repeatable"] == "true"
        assert native["repeatability_basis"] == "normalized_netlist_and_erc"
        assert native["normalized_netlist_sha256"] == native["repeat_normalized_netlist_sha256"]
        assert native["normalized_erc_sha256"] == native["repeat_normalized_erc_sha256"]
        assert native["native_erc_error_types"] == "none"
        normalized_hashes[project] = native["normalized_netlist_sha256"]
        assert results["component-voltage-rating-fixture/control"]["utilization_status"] == "PASS"
        assert (
            results["component-voltage-rating-fixture/over-limit-fault"]["utilization_status"]
            == "FAIL"
        )
        for case in (
            "component-voltage-rating-fixture/control",
            "component-voltage-rating-fixture/over-limit-fault",
        ):
            assert results[case]["kicad_version"] == version
            assert results[case]["image"] == expected_images[project]
            assert results[case]["fixture_sha256"] == expected_fixture_sha256
            assert results[case]["repeatable"] == "true"
            assert results[case]["normalized_erc_sha256"] == native["normalized_erc_sha256"]
            assert results[case]["native_erc_error_types"] == "none"
        power_results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("component-power-rating-fixture/")
        }
        assert set(power_results) == {
            "component-power-rating-fixture/native-export",
            "component-power-rating-fixture/control",
            "component-power-rating-fixture/over-limit-fault",
        }
        power_native = power_results["component-power-rating-fixture/native-export"]
        assert power_native["status"] == "PASS"
        assert power_native["fixture_sha256"] == expected_power_fixture_sha256
        assert power_native["kicad_version"] == version
        assert power_native["image"] == expected_images[project]
        assert power_native["repeatable"] == "true"
        assert power_native["repeatability_basis"] == "normalized_netlist_and_erc_types"
        assert (
            power_native["normalized_netlist_sha256"]
            == power_native["repeat_normalized_netlist_sha256"]
        )
        assert power_native["normalized_erc_sha256"] == power_native["repeat_normalized_erc_sha256"]
        assert power_native["native_erc_error_types"] == "none"
        power_normalized_hashes[project] = power_native["normalized_netlist_sha256"]
        assert (
            power_results["component-power-rating-fixture/control"]["utilization_status"] == "PASS"
        )
        assert (
            power_results["component-power-rating-fixture/over-limit-fault"]["utilization_status"]
            == "FAIL"
        )
        for case in (
            "component-power-rating-fixture/control",
            "component-power-rating-fixture/over-limit-fault",
        ):
            assert power_results[case]["kicad_version"] == version
            assert power_results[case]["image"] == expected_images[project]
            assert power_results[case]["fixture_sha256"] == expected_power_fixture_sha256
            assert power_results[case]["repeatable"] == "true"
            assert (
                power_results[case]["normalized_erc_sha256"]
                == power_native["normalized_erc_sha256"]
            )
            assert power_results[case]["native_erc_error_types"] == "none"
        contact_results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("connector-contact-rating-fixture/")
        }
        assert set(contact_results) == {
            "connector-contact-rating-fixture/native-export",
            "connector-contact-rating-fixture/control",
            "connector-contact-rating-fixture/over-limit-fault",
        }
        contact_native = contact_results["connector-contact-rating-fixture/native-export"]
        assert contact_native["status"] == "PASS"
        assert contact_native["fixture_sha256"] == expected_contact_fixture_sha256
        assert contact_native["kicad_version"] == version
        assert contact_native["image"] == expected_images[project]
        assert contact_native["repeatable"] == "true"
        assert contact_native["repeatability_basis"] == "normalized_netlist_and_erc_types"
        assert (
            contact_native["normalized_netlist_sha256"]
            == contact_native["repeat_normalized_netlist_sha256"]
        )
        assert (
            contact_native["normalized_erc_sha256"]
            == contact_native["repeat_normalized_erc_sha256"]
        )
        assert contact_native["native_erc_error_types"] == "none"
        contact_normalized_hashes[project] = contact_native["normalized_netlist_sha256"]
        assert (
            contact_results["connector-contact-rating-fixture/control"]["utilization_status"]
            == "PASS"
        )
        assert (
            contact_results["connector-contact-rating-fixture/over-limit-fault"][
                "utilization_status"
            ]
            == "FAIL"
        )
        for case in (
            "connector-contact-rating-fixture/control",
            "connector-contact-rating-fixture/over-limit-fault",
        ):
            assert contact_results[case]["kicad_version"] == version
            assert contact_results[case]["image"] == expected_images[project]
            assert contact_results[case]["fixture_sha256"] == expected_contact_fixture_sha256
            assert contact_results[case]["repeatable"] == "true"
            assert (
                contact_results[case]["normalized_erc_sha256"]
                == contact_native["normalized_erc_sha256"]
            )
            assert contact_results[case]["native_erc_error_types"] == "none"
        mosfet_results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("component-mosfet-stress-fixture/")
        }
        assert set(mosfet_results) == {
            "component-mosfet-stress-fixture/native-export",
            "component-mosfet-stress-fixture/control",
            "component-mosfet-stress-fixture/over-limit-fault",
        }
        mosfet_native = mosfet_results["component-mosfet-stress-fixture/native-export"]
        assert mosfet_native["status"] == "PASS"
        assert mosfet_native["fixture_sha256"] == expected_mosfet_fixture_sha256
        assert mosfet_native["kicad_version"] == version
        assert mosfet_native["image"] == expected_images[project]
        assert mosfet_native["repeatable"] == "true"
        assert mosfet_native["repeatability_basis"] == "normalized_netlist_and_erc_types"
        assert (
            mosfet_native["normalized_netlist_sha256"]
            == mosfet_native["repeat_normalized_netlist_sha256"]
        )
        assert (
            mosfet_native["normalized_erc_sha256"] == mosfet_native["repeat_normalized_erc_sha256"]
        )
        assert mosfet_native["native_erc_error_types"] == "none"
        mosfet_normalized_hashes[project] = mosfet_native["normalized_netlist_sha256"]
        assert (
            mosfet_results["component-mosfet-stress-fixture/control"]["utilization_status"]
            == "PASS"
        )
        assert (
            mosfet_results["component-mosfet-stress-fixture/over-limit-fault"]["utilization_status"]
            == "FAIL"
        )
        for case in (
            "component-mosfet-stress-fixture/control",
            "component-mosfet-stress-fixture/over-limit-fault",
        ):
            assert mosfet_results[case]["kicad_version"] == version
            assert mosfet_results[case]["image"] == expected_images[project]
            assert mosfet_results[case]["fixture_sha256"] == expected_mosfet_fixture_sha256
            assert mosfet_results[case]["repeatable"] == "true"
            assert mosfet_results[case]["native_erc_error_types"] == "none"
        receipt = root / native["command_receipt"]
        assert receipt.is_file()
        command = json.loads(receipt.read_text())
        mounts = tuple(
            command["argv"][index + 1]
            for (index, item) in enumerate(command["argv"][:-1])
            if item == "-v"
        )
        assert len(mounts) == 3
        assert sum(item.endswith(":/fixtures:ro") for item in mounts) == 1
        assert sum(item.endswith(":/mosfet-fixture:ro") for item in mounts) == 1
        assert sum(item.endswith(":/output:rw") for item in mounts) == 1
    assert len(set(normalized_hashes.values())) == 1
    assert len(set(power_normalized_hashes.values())) == 1
    assert len(set(contact_normalized_hashes.values())) == 1
    assert len(set(mosfet_normalized_hashes.values())) == 1

"""Exact-version native fault/control coverage for USB SuperSpeed peer references."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


def _synthetic_toolchain_checkout(base: Path, *, project: str, version: str, image: str) -> Path:
    """Build a minimal project-owned toolchain catalog without project board data."""
    from kicad_tooling.hwrepo.contracts import write_model
    from kicad_tooling.hwrepo.models import (
        CatalogPaths,
        ComponentIdentity,
        IgnoredChecks,
        ProjectDiscovery,
        ProjectKind,
        ProjectManifest,
        ProjectTestContract,
        SchematicValidationContract,
        ToolchainRecord,
        ToolchainsCatalog,
    )

    root = base / "repository"
    catalog = root / "catalog"
    project_dir = root / "projects" / project
    source_dir = project_dir / "kicad"
    tests_dir = project_dir / "tests"
    for directory in (catalog, source_dir, tests_dir):
        directory.mkdir(parents=True, exist_ok=True)
    (source_dir / "synthetic.kicad_pro").write_text("{}\n", encoding="utf-8")
    toolchain_id = f"synthetic-kicad-{version.replace('.', '-')}"
    write_model(
        catalog / "projects.json",
        ProjectDiscovery(
            catalogs=CatalogPaths(
                parts="catalog/parts.json",
                interfaces="catalog/interfaces.json",
                libraries="catalog/libraries.json",
                toolchains="catalog/toolchains.json",
                release_policies="catalog/release-policies.json",
            ),
            project_roots=("projects",),
        ),
    )
    write_model(
        catalog / "toolchains.json",
        ToolchainsCatalog(
            schema_version="1",
            toolchains=(
                ToolchainRecord(
                    id=toolchain_id,
                    kicad_version=version,
                    image=image,
                    desktop_edit_policy="Synthetic native lint regression only",
                    installer_source="Digest-pinned public KiCad container",
                    migration_policy="Synthetic native lint regression only",
                ),
            ),
        ),
    )
    write_model(
        project_dir / "project.json",
        ProjectManifest(
            id=project,
            kind=ProjectKind.SCHEMATIC,
            status="training_fixture",
            assurance_profile="training",
            toolchain_id=toolchain_id,
            project="kicad/synthetic.kicad_pro",
            source_roots=("kicad",),
            required_inputs=("kicad/synthetic.kicad_pro",),
            component_identity=ComponentIdentity(required=False, part_ids=()),
        ),
    )
    write_model(
        tests_dir / "contract.json",
        ProjectTestContract(
            validation=SchematicValidationContract(
                kind=ProjectKind.SCHEMATIC,
                expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
            )
        ),
    )
    return root


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES") != "1",
    reason="native USB SuperSpeed fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_usb_superspeed_peer_reference_native_fixture_lane_is_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_support import HostedLog
    from kicad_tooling.ci_hosted_usb_superspeed_peer_reference import (
        usb_superspeed_peer_reference_fixture_lane,
    )
    from kicad_tooling.hwrepo.electrical import selected_config

    expected_images = {
        "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    }
    root = _synthetic_toolchain_checkout(
        tmp_path,
        project=project,
        version=version,
        image=expected_images[project],
    )
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == expected_images[project]

    log = HostedLog(root, f"native-usb-superspeed-peer-reference-{project}")
    usb_superspeed_peer_reference_fixture_lane(root, project=project, image=config.image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("usb-superspeed-peer-reference-fixture/")
    }
    assert set(results) == {
        "usb-superspeed-peer-reference-fixture/native-export",
        "usb-superspeed-peer-reference-fixture/fault",
        "usb-superspeed-peer-reference-fixture/control",
        "usb-superspeed-peer-reference-fixture/mapped-fault",
        "usb-superspeed-peer-reference-fixture/mapped-control",
        "usb-superspeed-peer-reference-fixture/stale-map-control",
    }
    fault = results["usb-superspeed-peer-reference-fixture/fault"]
    assert fault["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert fault["rule_status"] == "REVIEW"
    assert fault["common_reference_paths"] == 0
    assert fault["separate_reference_paths"] == 2
    assert fault["reference_nets"] == "USB_GND->PHY_GND"
    assert set(fault["pair_families"].split(";")) == {
        "USB SuperSpeed TX->USB SuperSpeed RX",
        "USB SuperSpeed RX->USB SuperSpeed TX",
    }
    control = results["usb-superspeed-peer-reference-fixture/control"]
    assert control["status"] == "PASS"
    assert control["lint_status"] == "REVIEW"
    assert control["rule_status"] == "PASS"
    assert set(control["other_findings"].split(";")) == {
        "signal.named_pair_without_reviewed_requirement:SS_RX_P / SS_RX_N",
        "signal.named_pair_without_reviewed_requirement:SS_TX_P / SS_TX_N",
    }
    assert control["reference_findings"] == "none"
    assert control["common_reference_paths"] == 2
    assert control["separate_reference_paths"] == 0
    assert control["reference_nets"] == "BOARD_GND->BOARD_GND"

    mapped_fault = results["usb-superspeed-peer-reference-fixture/mapped-fault"]
    assert mapped_fault["status"] == "PASS"
    assert mapped_fault["reference_policy"] == "separate_nets"
    assert mapped_fault["reference_findings"] == 0
    assert mapped_fault["path_mismatches"] == 0
    assert mapped_fault["mapped_separate_paths"] == 2
    assert mapped_fault["requirement_count"] == 2
    assert mapped_fault["repeatable"] == "true"

    mapped_control = results["usb-superspeed-peer-reference-fixture/mapped-control"]
    assert mapped_control["status"] == "PASS"
    assert mapped_control["reference_policy"] == "common_net"
    assert mapped_control["reference_findings"] == 0
    assert mapped_control["path_mismatches"] == 0
    assert mapped_control["mapped_separate_paths"] == 0
    assert mapped_control["requirement_count"] == 2
    assert mapped_control["repeatable"] == "true"

    stale_map = results["usb-superspeed-peer-reference-fixture/stale-map-control"]
    assert stale_map["status"] == "PASS"
    assert stale_map["reference_findings"] == 0
    assert stale_map["path_mismatches"] == 2
    assert stale_map["repeatable"] == "true"

    for case, result in (("fault", fault), ("control", control)):
        assert result["kicad_version"] == version
        assert result["image"] == expected_images[project]
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert (
            result["source_sha256"]
            == {
                "fault": "4eab8226ec5b526a16c880453f54202bb3df9b42b444bd82684d92fd7720c095",
                "control": "5b8bd68163f9493c91c643b55d283f9514522ccc67b2cc7e37955e83e0b7b400",
            }[case]
        )
        receipt = root / result["command_receipt"]
        assert receipt.is_file()
        command = json.loads(receipt.read_text())
        argv = command["argv"]
        assert "--network" in argv and argv[argv.index("--network") + 1] == "none"
        mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
        assert len(mounts) == 2
        assert sum(item.endswith(":/fixtures:ro") for item in mounts) == 1
        assert sum(item.endswith(":/output:rw") for item in mounts) == 1

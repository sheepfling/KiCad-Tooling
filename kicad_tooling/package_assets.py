"""Required runtime and CI assets plus package-payload checks for wheels."""

from __future__ import annotations

import zipfile
from email.parser import Parser
from pathlib import Path

REQUIRED_WHEEL_ASSETS = frozenset(
    {
        "kicad_tooling/tool-surfaces.json",
        "kicad_tooling/py.typed",
        "kicad_tooling/package_assets.py",
        "kicad_tooling/package_build.py",
        "kicad_tooling/hwrepo/external_protection_models.py",
        "kicad_tooling/hwrepo/component_role_models.py",
        "kicad_tooling/hwrepo/power_path_models.py",
        "kicad_tooling/hwrepo/power_sequence_models.py",
        "kicad_tooling/hwrepo/power_connectivity_models.py",
        "kicad_tooling/hwrepo/analysis_state_models.py",
        "kicad_tooling/hwrepo/crystal_network_models.py",
        "kicad_tooling/hwrepo/pcb_keepout_models.py",
        "kicad_tooling/hwrepo/usb_c_models.py",
        "kicad_tooling/hwrepo/usb_data_path_models.py",
        "kicad_tooling/hwrepo/connector_return_distribution_models.py",
        "kicad_tooling/markdown_check/__main__.py",
        "kicad_tooling/fixtures/foreign-eagle-board.xml",
        "kicad_tooling/fixtures/scaffold-license.txt",
        "kicad_tooling/hwrepo/design-lint-rules.json",
        "kicad_tooling/hwrepo/pcb_variant_probe.py.in",
        "kicad_tooling/hwrepo/native_pcb_probe_touch_clearance.py.in",
        "kicad_tooling/hwrepo/schematic-text-metrics.json",
        "kicad_tooling/hwrepo/fixtures/pcb-return-alternate-layer-via.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-return-alternate-layer-open.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-return-zone-connected.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-return-zone-split.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-return-zone-through-hole-split.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-return-unstitched-planes.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-return-stitched-planes.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-return-net-tie-connected.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-return-net-tie-dnp.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-return-isolation-open.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-return-isolation-bridged.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-access-probe-envelope.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-decoupling-placement.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-protection-entry-path.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-switching-loop.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-switching-loop-inner-plane.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-switching-loop-split-plane.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-reference-narrow-void-control.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-reference-narrow-void-fault.kicad_pcb",
        "kicad_tooling/hwrepo/kicad_library_license.txt",
    }
)


def wheel_contents(wheel: Path) -> tuple[str, dict[str, bytes]]:
    """Read authoritative metadata and required package payload from a wheel."""
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ValueError(f"Expected one distribution metadata file in {wheel}")
        metadata_name = metadata_names[0]
        metadata = Parser().parsestr(archive.read(metadata_name).decode("utf-8"))
        version = metadata["Version"]
        if metadata["Name"] != "kicad-team-tooling" or not version:
            raise ValueError(f"Unexpected distribution metadata in {wheel}")
        payload = {
            name: archive.read(name)
            for name in archive.namelist()
            if name.startswith("kicad_tooling/") or name == metadata_name
        }
        missing = REQUIRED_WHEEL_ASSETS - payload.keys()
        if missing:
            raise ValueError(f"Missing package assets in {wheel}: {missing}")
        return version, payload

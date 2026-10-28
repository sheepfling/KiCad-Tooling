"""Source registry for digest-bound hosted USB data-path fixtures."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_support import tooling_checkout_root


def usb_data_path_fixture_sources() -> dict[str, Path]:
    """Return the tooling-owned synthetic schematic sources for the USB lane."""
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint"
    return {
        "integrated-direct": fixture_root / "usb-data-path-native/integrated-phy-direct.kicad_sch",
        "external-series": fixture_root
        / "usb-data-path-native/external-phy-series-control.kicad_sch",
        "external-series-reference-bond-control": fixture_root
        / "usb-data-path-native/external-phy-series-reference-bond-control.kicad_sch",
        "external-series-reference-fault": fixture_root
        / "usb-data-path-native/external-phy-series-reference-fault.kicad_sch",
        "external-bypass": fixture_root
        / "usb-data-path-native/external-phy-direct-bypass-fault.kicad_sch",
        "peer-reference-fault": fixture_root / "usb-peer-reference-native/fault.kicad_sch",
        "peer-reference-control": fixture_root / "usb-peer-reference-native/control.kicad_sch",
        "usb-c-peer-reference-fault": fixture_root / "usb-c-peer-reference-native/fault.kicad_sch",
        "usb-c-peer-reference-control": fixture_root
        / "usb-c-peer-reference-native/control.kicad_sch",
        "usb-multiport-peer-reference-fault": fixture_root
        / "usb-multiport-peer-reference-native/fault.kicad_sch",
        "usb-multiport-peer-reference-control": fixture_root
        / "usb-multiport-peer-reference-native/control.kicad_sch",
        "usb-threeport-peer-reference-fault": fixture_root
        / "usb-threeport-peer-reference-native/fault.kicad_sch",
        "usb-threeport-peer-reference-control": fixture_root
        / "usb-threeport-peer-reference-native/control.kicad_sch",
        "intentional-isolation-boundary": fixture_root
        / "usb-isolator-peer-reference-native/intentional-isolation.kicad_sch",
        "inline-component-control": fixture_root
        / "usb-data-path-native/inline-protection-control.kicad_sch",
        "inline-component-ground-fault": fixture_root
        / "usb-data-path-native/inline-protection-ground-fault.kicad_sch",
        "inline-component-peer-reference-fault": fixture_root
        / "usb-data-path-native/inline-protection-split-reference.kicad_sch",
        "inline-component-peer-reference-map-control": fixture_root
        / "usb-data-path-native/inline-protection-split-reference.kicad_sch",
        "inline-component-peer-reference-bond-fault": fixture_root
        / "usb-data-path-native/inline-protection-reference-bond-fault.kicad_sch",
        "inline-component-peer-reference-bond-control": fixture_root
        / "usb-data-path-native/inline-protection-reference-bond-control.kicad_sch",
        "protection-shunt-split-reference": fixture_root
        / "usb-data-path-native/protection-shunt-split-reference.kicad_sch",
        "protection-shunt-common-reference": fixture_root
        / "usb-data-path-native/protection-shunt-common-reference.kicad_sch",
        "protection-shunt-pin-fault": fixture_root
        / "usb-data-path-native/protection-shunt-pin-fault.kicad_sch",
    }

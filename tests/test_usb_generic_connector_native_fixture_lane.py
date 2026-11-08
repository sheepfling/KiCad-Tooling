"""Digest-pinned native exports for generic USB connector coverage review."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.electrical import selected_config

RULE_ID = "bus.usb_generic_connector_phy_pair_review"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES") != "1",
    reason="native generic-connector USB fixtures run in the digest-pinned USB lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.design_lint_rule(rule_id="bus.usb_superspeed_generic_connector_pair_review")
def test_native_generic_connector_fault_and_named_control(
    hosted_reference_root: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted import HostedLog, generic_usb_connector_fixture_lane

    root = hosted_reference_root
    config = selected_config(root, project)
    assert config.kicad_version == version
    log = HostedLog(root, f"native-usb-generic-connector-{project}")
    generic_usb_connector_fixture_lane(root, project=project, image=config.image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    fault = next(
        item for item in events if item.get("stage") == "usb-generic-connector-fixture/fault"
    )
    assert json.loads(fault["other_connector_contacts"]) == [
        "J1.3 function=VBUS nets=unassigned",
        "J1.4 function=GND nets=USB_GND",
    ]
    superspeed_fault = next(
        item
        for item in events
        if item.get("stage") == "usb-generic-connector-fixture/superspeed_fault"
    )
    assert json.loads(superspeed_fault["other_connector_contacts"]) == [
        "J1.3 function=GND nets=USB_GND",
        "J1.4 function=VBUS nets=unassigned",
    ]

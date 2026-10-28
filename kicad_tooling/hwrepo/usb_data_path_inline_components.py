"""Check exact project-authored USB paths through multi-pin components."""

from __future__ import annotations

from dataclasses import dataclass

from .models import NetlistContract
from .usb_data_path_component_checks import check_usb_component_pin_map
from .usb_data_path_models import UsbDataPathInlineComponentRequirement


@dataclass(frozen=True, slots=True)
class UsbInlineComponentCheck:
    component_issues: tuple[str, ...]
    positive_issues: tuple[str, ...]
    negative_issues: tuple[str, ...]


def check_usb_inline_component(
    requirement: UsbDataPathInlineComponentRequirement,
    observed: NetlistContract,
) -> UsbInlineComponentCheck:
    """Compare complete native component identity, pin inventory, and pin disposition."""
    exact_map = check_usb_component_pin_map(requirement, observed)
    component_issues = list(exact_map.component_issues)
    positive_pin_ids = {
        requirement.positive_connector_pin.casefold(),
        requirement.positive_phy_pin.casefold(),
    }
    negative_pin_ids = {
        requirement.negative_connector_pin.casefold(),
        requirement.negative_phy_pin.casefold(),
    }
    positive_issues: list[str] = []
    negative_issues: list[str] = []
    for pin, issue in exact_map.pin_issues:
        pin_id = pin.casefold()
        if pin_id in positive_pin_ids:
            positive_issues.append(issue)
        elif pin_id in negative_pin_ids:
            negative_issues.append(issue)
        else:
            component_issues.append(issue)
    return UsbInlineComponentCheck(
        component_issues=tuple(component_issues),
        positive_issues=tuple(positive_issues),
        negative_issues=tuple(negative_issues),
    )

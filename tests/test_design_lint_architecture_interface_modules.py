"""Keep I2C peer-reference and mapped connector checks in focused owners."""

from __future__ import annotations

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

I2C_PEER_REFERENCE_MODULES = (
    "i2c_peer_reference_models.py",
    "i2c_peer_reference_scan.py",
)

CONNECTOR_MAPPED_SIGNAL_MODULES = (
    "connector_mapped_interface_pins.py",
    "connector_mapped_signal_sharing.py",
    "connector_mapped_shield_signal_sharing.py",
    "connector_mapped_signal_split_nets.py",
)


def _assert_modules_are_reviewable(modules: tuple[str, ...], *, label: str) -> None:
    paths = [HWREPO / name for name in modules]
    assert all(path.is_file() for path in paths)
    module_sizes = {path.name: line_count(path) for path in paths}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }
    assert not oversized, f"Keep {label} modules below 500 lines: {oversized}"


def test_i2c_peer_reference_review_stays_in_focused_protocol_modules() -> None:
    _assert_modules_are_reviewable(I2C_PEER_REFERENCE_MODULES, label="I2C peer-reference")


@pytest.mark.connector_lint
def test_mapped_connector_signal_checks_stay_in_a_focused_owner_module() -> None:
    _assert_modules_are_reviewable(CONNECTOR_MAPPED_SIGNAL_MODULES, label="mapped connector")

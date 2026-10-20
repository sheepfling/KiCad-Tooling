"""Validate the source registry for synthetic hosted USB data-path cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_usb_data_path_cases import usb_data_path_fixture_sources

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def test_fixture_source_registry_stays_within_synthetic_design_lint_fixtures() -> None:
    sources = usb_data_path_fixture_sources()
    fixture_root = Path(__file__).parent / "fixtures/design_lint"

    assert len(sources) == 23
    assert all(path.is_file() for path in sources.values())
    assert all(path.resolve().is_relative_to(fixture_root.resolve()) for path in sources.values())

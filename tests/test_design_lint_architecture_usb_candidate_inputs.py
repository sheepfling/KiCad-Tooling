"""Guard capability grouping for authored USB data-path evidence."""

from __future__ import annotations

from dataclasses import fields
from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo.design_lint_candidate_inputs import (
    DesignLintCandidateInputs,
    UsbDataPathCandidateInputs,
)
from kicad_tooling.hwrepo.usb_data_path_models import UsbDataPathMap

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint, pytest.mark.interface_lint]


def test_usb_data_path_map_is_owned_by_a_named_candidate_group() -> None:
    names = {item.name for item in fields(DesignLintCandidateInputs)}

    assert get_type_hints(DesignLintCandidateInputs)["usb_data_path"] is (
        UsbDataPathCandidateInputs
    )
    assert "usb_data_path_map" not in names
    assert get_type_hints(UsbDataPathCandidateInputs)["authored_map"] == UsbDataPathMap | None

"""Regressions for named BJT and MOSFET symbol-role records."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo.component_bjt_symbols import (
    BjtPinRoleNumbers,
    basic_bjt_role_numbers,
)
from kicad_tooling.hwrepo.component_mosfet_symbols import (
    MosfetPinRoleNumbers,
    mosfet_terminal_role_numbers,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


def test_bjt_role_lookup_returns_named_frozen_pin_numbers() -> None:
    roles = basic_bjt_role_numbers(
        "Q1",
        "Transistor_BJT:Q_NPN_BCE",
        ("1", "2", "3"),
        {"Q1.1": "collector", "Q1.2": "base", "Q1.3": "emitter"},
    )

    assert roles == BjtPinRoleNumbers(base="2", collector="1", emitter="3")
    assert get_type_hints(basic_bjt_role_numbers)["return"] == BjtPinRoleNumbers | None
    with pytest.raises(FrozenInstanceError):
        roles.base = "1"  # type: ignore[union-attr]


def test_bjt_role_lookup_rejects_incomplete_native_roles() -> None:
    assert (
        basic_bjt_role_numbers(
            "Q1",
            "Transistor_BJT:Q_NPN_BCE",
            ("1", "2", "3"),
            {"Q1.1": "collector", "Q1.2": "base"},
        )
        is None
    )


def test_mosfet_role_lookup_returns_named_frozen_pin_numbers() -> None:
    roles = mosfet_terminal_role_numbers(
        "Q2",
        "Transistor_FET:Q_NMOS_DGS",
        ("1", "2", "3"),
        {"Q2.1": "drain", "Q2.2": "gate", "Q2.3": "source"},
    )

    assert roles == MosfetPinRoleNumbers(drain="1", gate="2", source="3")
    assert get_type_hints(mosfet_terminal_role_numbers)["return"] == (MosfetPinRoleNumbers | None)
    with pytest.raises(FrozenInstanceError):
        roles.gate = "1"  # type: ignore[union-attr]


def test_mosfet_role_lookup_rejects_duplicate_native_roles() -> None:
    assert (
        mosfet_terminal_role_numbers(
            "Q2",
            "Transistor_FET:Q_NMOS_DGS",
            ("1", "2", "3"),
            {"Q2.1": "drain", "Q2.2": "gate", "Q2.3": "gate"},
        )
        is None
    )

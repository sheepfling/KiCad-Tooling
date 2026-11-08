"""Deterministic capture of connector contacts outside an interface pin group."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_contact_evidence import (
    collect_other_connector_contacts,
    format_other_connector_contacts,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]


def test_other_contacts_keep_sorted_assignments_and_explicit_open_state() -> None:
    contacts = collect_other_connector_contacts(
        "J1",
        ("5", "2", "1"),
        ("VCC", "CANH", "VBUS"),
        {
            "j1.1": {"VCC", "3V3"},
            "j1.2": {"CAN_H"},
        },
        ("j1.2",),
    )

    assert format_other_connector_contacts(contacts) == (
        "J1.1 function=VBUS nets=3V3,VCC",
        "J1.5 function=VCC nets=unassigned",
    )


def test_other_contact_capture_rejects_incomplete_native_functions() -> None:
    with pytest.raises(ValueError, match="matching lengths"):
        collect_other_connector_contacts("J1", ("1",), (), {}, ())
    with pytest.raises(ValueError, match="native pin functions"):
        collect_other_connector_contacts("J1", ("1",), (None,), {}, ())

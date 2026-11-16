"""Keep native netlist population parsing correct around custom ``dnp`` fields."""

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.native_report_parsing import read_netlist

RULE_ID = "schematic.reserved_dnp_property_collision"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _netlist(properties: str, fields: str = "") -> str:
    return (
        "<export><design><tool>Eeschema 10.0.8</tool></design><components>"
        "<comp ref='J1'><value>USB_A</value>"
        f"<fields>{fields}</fields>{properties}</comp></components><nets/></export>"
    )


def _dnp_components(tmp_path: Path, xml: str) -> tuple[str, ...]:
    path = tmp_path / "netlist.xml"
    path.write_text(xml, encoding="utf-8")
    return read_netlist(path).dnp_components


def test_custom_dnp_value_does_not_mark_a_fitted_part_as_dnp(tmp_path: Path) -> None:
    xml = _netlist(
        '<property name="dnp" value="yes"/>',
        '<field name="dnp">yes</field>',
    )

    assert _dnp_components(tmp_path, xml) == ()


def test_native_empty_marker_wins_over_colliding_custom_value(tmp_path: Path) -> None:
    xml = _netlist(
        '<property name="dnp" value="no"/><property name="dnp"/>',
        '<field name="dnp">no</field>',
    )

    assert _dnp_components(tmp_path, xml) == ("J1",)


def test_native_empty_marker_remains_dnp_without_custom_field(tmp_path: Path) -> None:
    xml = _netlist('<property name="dnp"/>')

    assert _dnp_components(tmp_path, xml) == ("J1",)


def test_invalid_native_dnp_value_remains_an_error_without_custom_field(tmp_path: Path) -> None:
    xml = _netlist('<property name="dnp" value="no"/>')
    path = tmp_path / "netlist.xml"
    path.write_text(xml, encoding="utf-8")

    with pytest.raises(ValueError, match="Ambiguous native dnp property at J1"):
        read_netlist(path)


def test_unmeasured_kicad_version_keeps_legacy_dnp_interpretation(tmp_path: Path) -> None:
    xml = _netlist(
        '<property name="dnp" value="yes"/>',
        '<field name="dnp">yes</field>',
    ).replace("Eeschema 10.0.8", "Eeschema 10.0.9")

    assert _dnp_components(tmp_path, xml) == ("J1",)

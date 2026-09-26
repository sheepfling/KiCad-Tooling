"""Provider identity is projected through a strict, closed JSON boundary."""

from __future__ import annotations

import json
import unittest

from kicad_tooling.hwrepo.contracts import parse_easyeda_identity, parse_model
from kicad_tooling.hwrepo.models import CadProviderIdentity, CadSourceFile


def provider_document() -> dict:
    return {
        "success": True,
        "ignored_vendor_field": "allowed outside our projection",
        "result": {
            "lcsc": {"number": "C2040"},
            "dataStr": {
                "head": {
                    "c_para": {
                        "Manufacturer": "Raspberry Pi",
                        "Manufacturer Part": "RP2040",
                        "Supplier Part": "C2040",
                        "name": "RP2040",
                        "package": "QFN-56",
                    }
                }
            },
            "packageDetail": {
                "dataStr": {
                    "shape": [
                        "PAD~example",
                        "SVGNODE~" + json.dumps({"attrs": {"uuid": "a" * 32, "title": "QFN-56"}}),
                    ]
                }
            },
        },
    }


class CadContractsTests(unittest.TestCase):
    def test_known_fields_round_trip_and_vendor_extras_do_not_gain_authority(self) -> None:
        result = parse_easyeda_identity(json.dumps(provider_document()))
        self.assertEqual(result.supplier_id, "C2040")
        self.assertEqual(result.mpn, "RP2040")
        self.assertEqual(result.manufacturer, "Raspberry Pi")
        self.assertEqual(result.model_uuid, "a" * 32)
        self.assertEqual(parse_model(result.model_dump_json(), CadProviderIdentity), result)
        self.assertNotIn("ignored_vendor_field", result.model_dump_json())
        with self.assertRaises(ValueError):
            result.mpn = "changed"

    def test_missing_or_ambiguous_3d_pair_is_blocked(self) -> None:
        for shapes in (
            [],
            ["PAD~only"],
            "not a list",
            [False],
            ["SVGNODE~{}", "SVGNODE~{}"],
            ["SVGNODE~{bad json}"],
            ['SVGNODE~{"attrs":false}'],
        ):
            raw = provider_document()
            raw["result"]["packageDetail"]["dataStr"]["shape"] = shapes
            with self.subTest(shapes=shapes), self.assertRaises(ValueError):
                parse_easyeda_identity(json.dumps(raw))

    def test_identity_never_coerces_bad_provider_fields(self) -> None:
        for field, value in (
            ("Manufacturer", ""),
            ("Manufacturer Part", 123),
            ("Supplier Part", "../../C2040"),
            ("name", None),
            ("package", False),
        ):
            raw = provider_document()
            raw["result"]["dataStr"]["head"]["c_para"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                parse_easyeda_identity(json.dumps(raw))
        for raw in ({"success": False}, [], None, {"success": 1}, {"success": True, "result": {}}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_easyeda_identity(json.dumps(raw))

    def test_duplicate_keys_and_non_finite_json_are_rejected(self) -> None:
        document = json.dumps(provider_document())
        for invalid in (
            document.replace('"success": true', '"success":true,"success":true'),
            document.replace(
                '"ignored_vendor_field": "allowed outside our projection"',
                '"ignored_vendor_field":NaN',
            ),
        ):
            with self.subTest(document=invalid), self.assertRaises(ValueError):
                parse_easyeda_identity(invalid)
        raw = provider_document()
        raw["result"]["packageDetail"]["dataStr"]["shape"] = [
            'SVGNODE~{"attrs":{"uuid":"' + "a" * 32 + '","uuid":"' + "b" * 32 + '"}}'
        ]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            parse_easyeda_identity(json.dumps(raw))

    def test_source_file_contract_rejects_unknown_fields_and_invalid_hashes(self) -> None:
        valid = '{"path":"part.kicad_sym","sha256":"' + "0" * 64 + '"}'
        item = parse_model(valid, CadSourceFile)
        self.assertEqual(parse_model(item.model_dump_json(), CadSourceFile), item)
        for invalid in (
            valid.replace('"path":', '"extra":1,"path":'),
            valid.replace("0" * 64, "changed"),
            valid.replace('"part.kicad_sym"', "false"),
        ):
            with self.subTest(document=invalid), self.assertRaises(ValueError):
                parse_model(invalid, CadSourceFile)


if __name__ == "__main__":
    unittest.main()

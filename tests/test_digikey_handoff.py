"""No-key list handoff preserves orders and handles ambiguous network outcomes."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from kicad_tooling.hwrepo.contracts import parse_model
from kicad_tooling.hwrepo.digikey_handoff import DigiKeyHandoffError, build_payload, send
from kicad_tooling.hwrepo.models import (
    DigiKeyHandoffPayload,
    PurchasingFinding,
    PurchasingLine,
    PurchasingPlan,
    PurchasingPreferences,
)


def line(
    *,
    part_id: str = "RES-1",
    order_number: str = "311-1.00KHRCT-ND",
    manufacturer: str = "Yageo",
    mpn: str = "RC0603FR-071KL",
    kind: str = "DigiKey",
) -> PurchasingLine:
    return PurchasingLine(
        part_id=part_id,
        revision="A",
        manufacturer=manufacturer,
        mpn=mpn,
        footprint="Resistor_SMD:R_0603_1608Metric",
        references=("R1", "R2"),
        per_board=2,
        required=6,
        spares=2,
        quantity=8,
        order_number=order_number,
        order_number_kind=kind,
        search_url="https://www.digikey.com/en/products",
    )


def ready(*lines: PurchasingLine) -> PurchasingPlan:
    return PurchasingPlan(
        status="READY_FOR_ORDER_REVIEW",
        preferences=PurchasingPreferences(boards=3),
        components=(),
        lines=lines or (line(),),
        findings=(),
        excluded_references=("R9",),
    )


class DigiKeyHandoffTests(unittest.TestCase):
    def test_payload_preserves_exact_order_number_quantities_and_identity(self) -> None:
        result = build_payload(ready())
        row = result.root[0]
        self.assertEqual(row.requested_part_number, "311-1.00KHRCT-ND")
        self.assertEqual(row.quantities[0].quantity, 8)
        self.assertEqual(row.customer_reference, "RES-1")
        self.assertIn("Yageo", row.notes)
        self.assertIn("RC0603FR-071KL", row.notes)
        self.assertIn("R1, R2", row.notes)
        self.assertNotIn("R9", row.notes)
        self.assertEqual(
            result.model_dump(mode="json", by_alias=True),
            [
                {
                    "requestedPartNumber": "311-1.00KHRCT-ND",
                    "quantities": [{"quantity": 8}],
                    "customerReference": "RES-1",
                    "notes": "Manufacturer: Yageo; MPN: RC0603FR-071KL; References: R1, R2",
                }
            ],
        )
        self.assertFalse(ready().purchase_authorized)

    def test_provider_contract_round_trip_and_strict_rejection(self) -> None:
        payload = build_payload(ready())
        serialized = payload.model_dump_json(by_alias=True)
        self.assertEqual(parse_model(serialized, DigiKeyHandoffPayload), payload)
        for document in (
            "{}",
            "null",
            serialized.replace('"quantity":8', '"quantity":"8"'),
            serialized.replace('"quantity":8', '"quantity":true'),
            serialized.replace('"quantity":8', '"quantity":0'),
            serialized.replace('"quantity":8', '"quantity":8,"unexpected":1'),
            serialized.replace('"quantity":8', '"quantity":8,"quantity":9'),
            serialized.replace('"quantities":[{"quantity":8}]', '"quantities":[]'),
            serialized.replace(
                '"requestedPartNumber":"311-1.00KHRCT-ND"', '"requestedPartNumber":12'
            ),
        ):
            with self.subTest(document=document), self.assertRaises(ValueError):
                parse_model(document, DigiKeyHandoffPayload)

    def test_mpn_is_supported_without_an_invented_supplier_sku(self) -> None:
        result = build_payload(ready(line(order_number="RC0603FR-071KL", kind="MPN")))
        self.assertEqual(result.root[0].requested_part_number, "RC0603FR-071KL")

    def test_incomplete_or_empty_plan_cannot_send(self) -> None:
        finding = PurchasingFinding(
            code="missing", message="Missing identity", action="Choose part"
        )
        for plan in (
            ready().model_copy(update={"status": "NEEDS_PARTS"}),
            ready().model_copy(update={"lines": ()}),
            ready().model_copy(update={"findings": (finding,)}),
        ):
            with self.subTest(plan=plan), self.assertRaises(DigiKeyHandoffError):
                build_payload(plan)

    def test_ambiguous_identical_mpn_needs_exact_supplier_numbers(self) -> None:
        first = line(order_number="123", mpn="123", kind="MPN")
        second = line(
            part_id="RES-2", order_number="123", mpn="123", manufacturer="Other", kind="MPN"
        )
        with self.assertRaisesRegex(DigiKeyHandoffError, "different manufacturers"):
            build_payload(ready(first, second))

    def connection(
        self, body: bytes = b'"https://www.digikey.com/short/abc1234"', status: int = 200
    ) -> MagicMock:
        connection = MagicMock()
        response = connection.getresponse.return_value
        response.status = status
        response.getheader.return_value = str(len(body))
        response.read1.side_effect = (body, b"")
        return connection

    def test_single_https_post_uses_documented_noauth_schema(self) -> None:
        connection = self.connection()
        with patch(
            "kicad_tooling.hwrepo.digikey_handoff.http.client.HTTPSConnection",
            return_value=connection,
        ) as factory:
            result = send(build_payload(ready()), list_name="Board & prototype / 2")
        self.assertEqual(result.single_use_url, "https://www.digikey.com/short/abc1234")
        self.assertEqual(factory.call_args.args, ("www.digikey.com",))
        connection.request.assert_called_once()
        method, path = connection.request.call_args.args
        self.assertEqual(method, "POST")
        url = urlsplit(path)
        self.assertEqual(url.path, "/mylists/api/thirdparty")
        self.assertEqual(
            parse_qs(url.query),
            {
                "listName": ["Board & prototype / 2"],
                "tags": ["KiCad-Parts-Assistant"],
            },
        )
        submitted = DigiKeyHandoffPayload.model_validate_json(
            connection.request.call_args.kwargs["body"],
            strict=True,
        )
        self.assertEqual(submitted, build_payload(ready()))
        self.assertNotIn("Authorization", connection.request.call_args.kwargs["headers"])
        connection.close.assert_called_once()

    def test_current_eight_character_supplier_link_is_supported(self) -> None:
        connection = self.connection(body=b'"https://www.digikey.com/short/abc12345"')
        with patch(
            "kicad_tooling.hwrepo.digikey_handoff.http.client.HTTPSConnection",
            return_value=connection,
        ):
            result = send(build_payload(ready()), list_name="Board")
        self.assertEqual(result.single_use_url, "https://www.digikey.com/short/abc12345")
        connection.request.assert_called_once()

    def test_timeout_does_not_retry_an_ambiguous_post(self) -> None:
        connection = self.connection()
        connection.getresponse.side_effect = TimeoutError("socket timed out")
        with (
            patch(
                "kicad_tooling.hwrepo.digikey_handoff.http.client.HTTPSConnection",
                return_value=connection,
            ),
            self.assertRaisesRegex(DigiKeyHandoffError, "No automatic retry"),
        ):
            send(build_payload(ready()), list_name="Board")
        connection.request.assert_called_once()
        connection.close.assert_called_once()

    def test_response_trickle_cannot_reset_total_deadline(self) -> None:
        connection = self.connection()
        connection.getresponse.return_value.read1.side_effect = (b'"https://', b"www.")
        ticks = iter((0.0, 0.0, 1.0, 2.0, 10.0, 16.0))
        with (
            patch(
                "kicad_tooling.hwrepo.digikey_handoff.http.client.HTTPSConnection",
                return_value=connection,
            ),
            patch(
                "kicad_tooling.hwrepo.digikey_handoff.time.monotonic",
                side_effect=ticks,
            ),
            self.assertRaisesRegex(DigiKeyHandoffError, "No automatic retry"),
        ):
            send(build_payload(ready()), list_name="Board")
        self.assertEqual(connection.getresponse.return_value.read1.call_count, 2)
        connection.request.assert_called_once()
        connection.close.assert_called_once()

    def test_redirects_and_server_failures_are_not_followed_or_retried(self) -> None:
        for status in (301, 302, 307, 308, 400, 429, 500):
            connection = self.connection(status=status)
            with (
                self.subTest(status=status),
                patch(
                    "kicad_tooling.hwrepo.digikey_handoff.http.client.HTTPSConnection",
                    return_value=connection,
                ),
                self.assertRaisesRegex(DigiKeyHandoffError, f"HTTP {status}"),
            ):
                send(build_payload(ready()), list_name="Board")
            connection.request.assert_called_once()
            connection.getresponse.return_value.read1.assert_not_called()
            connection.close.assert_called_once()

    def test_untrusted_or_unsupported_response_never_becomes_a_link(self) -> None:
        for body in (
            b"<html>Just a moment</html>",
            b"null",
            b"{}",
            b'{"singleUseUrl":"https://www.digikey.com/short/abc1234"}',
            b'"http://www.digikey.com/short/abc1234"',
            b'"https://www.digikey.com.evil.test/short/abc1234"',
            b'"https://evil.test/short/abc1234"',
            b'"https://user@www.digikey.com/short/abc1234"',
            b'"https://www.digikey.com/short/abc1234?next=evil"',
            b'"https://www.digikey.com/short/abc1234#x"',
            b'"https://www.digikey.com:444/short/abc1234"',
            b'"https://www.digikey.com/short/abc123"',
            b'"https://www.digikey.com/short/abc123456"',
            b'"https://www.digikey.com/short/abc1234/extra"',
            b"\xff",
        ):
            connection = self.connection(body=body)
            with (
                self.subTest(body=body),
                patch(
                    "kicad_tooling.hwrepo.digikey_handoff.http.client.HTTPSConnection",
                    return_value=connection,
                ),
                self.assertRaises(DigiKeyHandoffError),
            ):
                send(build_payload(ready()), list_name="Board")
            connection.request.assert_called_once()

    def test_response_size_is_limited_with_or_without_content_length(self) -> None:
        for header in ("8193", "garbage", "-1", None):
            connection = self.connection(body=b"x" * 8193)
            connection.getresponse.return_value.getheader.return_value = header
            with (
                self.subTest(header=header),
                patch(
                    "kicad_tooling.hwrepo.digikey_handoff.http.client.HTTPSConnection",
                    return_value=connection,
                ),
                self.assertRaises(DigiKeyHandoffError),
            ):
                send(build_payload(ready()), list_name="Board")
            connection.close.assert_called_once()

    def test_invalid_local_requests_never_contact_supplier(self) -> None:
        payload = build_payload(ready())
        with patch("kicad_tooling.hwrepo.digikey_handoff.http.client.HTTPSConnection") as factory:
            for name in ("", " ", "x" * 201, "bad\nname"):
                with self.subTest(name=name), self.assertRaises(DigiKeyHandoffError):
                    send(payload, list_name=name)
            with self.assertRaises(DigiKeyHandoffError):
                send(DigiKeyHandoffPayload(root=()), list_name="Board")
            factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()

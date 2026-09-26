"""Supplier-offer snapshots remain typed, local and non-authorizing."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import UTC, datetime
from io import StringIO
from unittest.mock import patch

from kicad_tooling.hwrepo.models import SourcingSnapshot, SupplierOffer
from kicad_tooling.hwrepo.sourcing import check
from kicad_tooling.sourcing import main as sourcing_main
from tests.support import reference_root

ROOT = reference_root()


class SourcingSnapshotTests(unittest.TestCase):
    def snapshot(self, **updates: object) -> SourcingSnapshot:
        base = SourcingSnapshot(
            snapshot_id="training-offer-observation",
            source_commit="a" * 40,
            observed_at=datetime(2026, 9, 7, tzinfo=UTC),
            offers=(
                SupplierOffer(
                    id="offer-1",
                    part_id="training-generic-led-red-5mm",
                    supplier="Example supplier observation",
                    supplier_sku="EXAMPLE-LED-5MM",
                    source_url="https://example.invalid/offer",
                    region="test-only",
                    currency="USD",
                    quantity_break=1,
                    unit_price_minor=0,
                    availability="not a purchasing instruction",
                    lead_time_days=None,
                ),
            ),
        )
        return base.model_copy(update=updates)

    def test_known_part_offer_is_a_non_authorizing_snapshot(self) -> None:
        report = check(ROOT, self.snapshot())
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertFalse(report.build_authorized)

    def test_unknown_part_offer_fails_closed(self) -> None:
        offer = self.snapshot().offers[0].model_copy(update={"part_id": "unknown-part"})
        report = check(ROOT, self.snapshot(offers=(offer,)))
        self.assertEqual(report.status, "FAIL")
        self.assertIn("SOURCING_PART", {issue.code for issue in report.issues})

    def test_cli_defaults_to_json_and_text_explains_a_failing_offer(self) -> None:
        snapshot = self.snapshot()
        with (
            patch.object(sys, "argv", ["sourcing.py", "--root", str(ROOT), "--snapshot", "offer.json"]),
            patch("kicad_tooling.sourcing.read_model", return_value=snapshot),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(sourcing_main(), 0)
        self.assertEqual(json.loads(output.getvalue())["lane"], "SOURCING_SNAPSHOT")

        unknown = snapshot.offers[0].model_copy(update={"part_id": "unknown-part"})
        with (
            patch.object(sys, "argv", [
                "sourcing.py", "--root", str(ROOT), "--snapshot", "offer.json", "--format", "text",
            ]),
            patch("kicad_tooling.sourcing.read_model", return_value=self.snapshot(offers=(unknown,))),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(sourcing_main(), 1)
        self.assertIn("Sourcing snapshot training-offer-observation: FAIL", output.getvalue())
        self.assertIn("SOURCING_PART at offer-1", output.getvalue())
        self.assertIn("Build authorized: no", output.getvalue())

    def test_cli_text_reports_an_unreadable_snapshot(self) -> None:
        with (
            patch.object(sys, "argv", [
                "sourcing.py", "--root", str(ROOT), "--snapshot", "missing.json", "--format", "text",
            ]),
            patch("kicad_tooling.sourcing.read_model", side_effect=OSError("missing snapshot")),
            patch("sys.stdout", new_callable=StringIO) as output,
            patch("sys.stderr", new_callable=StringIO),
        ):
            self.assertEqual(sourcing_main(), 1)
        self.assertIn("SOURCING_LOAD at missing.json: missing snapshot", output.getvalue())


if __name__ == "__main__":
    unittest.main()

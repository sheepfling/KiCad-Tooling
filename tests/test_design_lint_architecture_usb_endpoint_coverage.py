"""Architecture contract for USB endpoint coverage review ownership."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

RULE_ID = "bus.usb_endpoint_path_coverage_incomplete"
OWNER = (
    "kicad_tooling/hwrepo/usb_peer_endpoint_coverage_review.py#"
    "usb_endpoint_path_coverage_candidates"
)


def test_catalog_points_to_the_usb_coverage_predicate_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.default_mode == "review"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs


def test_usb_endpoint_coverage_owner_stays_within_review_size() -> None:
    path = Path(__file__).parents[1] / OWNER.split("#", maxsplit=1)[0]

    assert len(path.read_text(encoding="utf-8").splitlines()) < 500

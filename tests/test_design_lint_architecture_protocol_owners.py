"""Keep protocol-specific lint predicates inside their owning modules."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

SWD_SIGNAL_SAME_NET_MODULES = (
    "swd_same_net.py",
    "design_lint_swd_same_net_candidate_evidence.py",
    "swd_endpoint_inventory.py",
)


def test_swd_signal_same_net_rule_uses_its_focused_protocol_owner() -> None:
    modules = [HWREPO / name for name in SWD_SIGNAL_SAME_NET_MODULES]
    rule = next(item for item in rule_catalog().rules if item.rule_id == "bus.swdio_swclk_same_net")
    module_sizes = {path.name: line_count(path) for path in modules if path.is_file()}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }
    owner = "kicad_tooling/hwrepo/swd_same_net.py#swdio_swclk_same_net_candidates"

    assert len(module_sizes) == len(SWD_SIGNAL_SAME_NET_MODULES)
    assert not oversized, f"SWD signal same-net modules reached the review limit: {oversized}"
    assert rule.theme == "interfaces"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs

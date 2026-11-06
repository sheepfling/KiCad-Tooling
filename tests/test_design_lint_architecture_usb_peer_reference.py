"""Keep USB peer analysis split by endpoint, path, map, and scan concern."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import (
    FACADE_MAX_LINES,
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

USB_PEER_ANALYSIS_MODULES = (
    "usb_peer_reference_types.py",
    "usb_peer_endpoint_analysis.py",
    "usb_peer_data_crossing.py",
    "usb_peer_path_analysis.py",
    "usb_peer_inline_path_analysis.py",
    "usb_peer_mapped_protection_evidence.py",
    "usb_peer_protection_shunt_analysis.py",
    "usb_peer_reference_contract.py",
    "usb_peer_reference_decision.py",
    "usb_peer_reference_evidence.py",
    "usb_peer_reference_scan.py",
    "usb_peer_unsupported_topology.py",
    "usb_peer_map_identity.py",
    "usb_peer_generic_connector_models.py",
    "usb_peer_generic_connector_candidates.py",
    "design_lint_usb_generic_connector_candidate_evidence.py",
    "design_lint_usb_generic_connector_candidates.py",
)


def test_usb_peer_reference_review_stays_split_by_responsibility() -> None:
    facade = HWREPO / "usb_peer_reference_review.py"
    modules = [HWREPO / name for name in USB_PEER_ANALYSIS_MODULES]

    assert line_count(facade) < FACADE_MAX_LINES
    assert all(path.is_file() for path in modules)
    module_sizes = {path.name: line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized, (
        "Keep USB endpoint, path, map, and scan logic in reviewable modules below 500 lines; "
        f"oversized modules: {oversized}"
    )


def test_usb_peer_reference_rule_refs_point_to_the_owning_modules() -> None:
    rule = next(
        item for item in rule_catalog().rules if item.rule_id == "bus.usb_peer_reference_review"
    )
    references = {
        item.split("#", maxsplit=1)[0].rsplit("/", maxsplit=1)[-1]
        for item in rule.implementation_refs
    }

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/usb_peer_reference_decision.py#usb_peer_reference_disposition"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/usb_peer_inline_path_analysis.py#mapped_inline_usb_data_link"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/usb_peer_protection_shunt_analysis.py#mapped_protection_shunt_usb_data_link"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/bus_signal_pairs.py#usb_superspeed_function_identity"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/usb_peer_endpoint_analysis.py#usb_superspeed_endpoints"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/usb_peer_reference_evidence.py"
        "#usb_reference_net_component_observations"
    ) in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/usb_peer_path_analysis.py#usb_superspeed_direct_data_link"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/usb_peer_unsupported_topology.py#unsupported_usb_multi_pin_path_candidates"
        in rule.implementation_refs
    )
    assert references <= {
        *USB_PEER_ANALYSIS_MODULES,
        "bus_signal_pairs.py",
        "peer_reference_assignments.py",
        "design_lint_candidate_aggregation.py",
        "design_lint_peer_candidates.py",
        "design_lint_usb_generic_connector_candidate_evidence.py",
        "design_lint_usb_generic_connector_candidates.py",
    }

"""Keep USB unmapped-topology evidence attached to its typed source."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from kicad_tooling.hwrepo.design_lint_usb_unmapped_topology_candidate_evidence import (
    UsbUnmappedMultiPinTopologyCandidate,
    UsbUnmappedMultiPinTopologyFindingEvidence,
)
from kicad_tooling.hwrepo.usb_peer_reference_types import UsbPeerUnsupportedMultiPinPath

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]

RULE_ID = "bus.usb_unmapped_multi_pin_topology"


def test_typed_candidate_retains_unsupported_path_and_derived_report_fields() -> None:
    path = UsbPeerUnsupportedMultiPinPath(
        connector_reference="J1",
        phy_reference="U1",
        component_reference="U2",
        component_symbol="Synthetic:Protection",
        component_footprint="Synthetic:QFN",
        component_pin_count=6,
        port_group="1",
        positive_connector_net="USB_DP_PORT",
        positive_phy_net="USB_DP_PHY",
        positive_connector_component_pins=("U2.1",),
        positive_phy_component_pins=("U2.2",),
        negative_connector_net="USB_DM_PORT",
        negative_phy_net="USB_DM_PHY",
        negative_connector_component_pins=("U2.3",),
        negative_phy_component_pins=("U2.4",),
    )
    source = UsbUnmappedMultiPinTopologyFindingEvidence(
        path=path,
        data_path=UsbDataPathCandidateInputs(authored_map=None),
    )

    candidate = UsbUnmappedMultiPinTopologyCandidate.from_source_evidence(
        source,
        subject="J1 / U1: unmapped USB multi-pin topology port 1 (U2)",
        message="Review the exact path map; topology alone does not establish conduction.",
    )

    assert candidate.source_evidence is source
    assert candidate.source_evidence.path is path
    assert candidate.rule_id == RULE_ID
    assert candidate.evidence["USB_D+_connector_side"] == ("USB_DP_PORT: U2.1",)
    assert candidate.evidence["USB_D+_PHY_side"] == ("USB_DP_PHY: U2.2",)
    assert candidate.evidence["USB_data_map_state"] == (
        "no map matches this connector/PHY port group",
    )
    with pytest.raises(TypeError):
        candidate.evidence["USB_topology_kind"] = ("other",)  # type: ignore[index]

    with pytest.raises(ValueError, match="typed source projection"):
        UsbUnmappedMultiPinTopologyCandidate(
            rule_id=RULE_ID,
            subject=candidate.subject,
            message=candidate.message,
            evidence={"USB_topology_kind": ("forged",)},
            source_evidence=source,
        )

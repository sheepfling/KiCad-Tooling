"""USB-C connector and controller CC findings retain current source evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_usb_c_cc_same_net_candidate_evidence import (
    UsbCcConnectorSameNetEvidence,
    UsbCcControllerSameNetEvidence,
    UsbCcSameNetCandidate,
)
from kicad_tooling.hwrepo.usb_c_cc_controller_same_net import (
    usb_c_cc_controller_same_net_candidates,
)
from kicad_tooling.hwrepo.usb_c_cc_same_net import usb_c_cc_same_net_candidates
from tests.design_lint_fixtures.usb_c_cc_same_net import usb_c_cc_same_net_netlist
from tests.design_lint_fixtures.usb_c_sbu_same_net import usb_c_cc_controller_same_net_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


def test_connector_candidate_retains_reviewed_scope_and_exact_netlist() -> None:
    observed = usb_c_cc_same_net_netlist(
        reference="PORT_A",
        symbol="Synthetic:USB_C_Port",
        cc1_function="CC-1",
        cc2_function="cc_2",
    )
    (candidate,) = usb_c_cc_same_net_candidates(observed, ("PORT_A",))

    assert isinstance(candidate, UsbCcSameNetCandidate)
    assert isinstance(candidate.source_evidence, UsbCcConnectorSameNetEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.source_evidence.reviewed_connector_references == ("PORT_A",)
    assert candidate.evidence["connector"] == ("PORT_A",)

    with pytest.raises(ValueError, match="recognized connector scope"):
        replace(candidate.source_evidence, reviewed_connector_references=())


def test_controller_candidate_revalidates_current_pins_and_shared_assignment() -> None:
    observed = usb_c_cc_controller_same_net_netlist()
    (candidate,) = usb_c_cc_controller_same_net_candidates(observed)

    assert isinstance(candidate, UsbCcSameNetCandidate)
    assert isinstance(candidate.source_evidence, UsbCcControllerSameNetEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence["component"] == ("U1",)

    with pytest.raises(ValueError, match="exact native name"):
        replace(candidate.source_evidence, net="STALE_NET")


def test_candidate_wire_fields_must_match_the_typed_cc_pair() -> None:
    candidate = usb_c_cc_controller_same_net_candidates(usb_c_cc_controller_same_net_netlist())[0]

    with pytest.raises(ValueError, match="typed source projection"):
        replace(candidate, evidence={"net": ("STALE_NET",)})

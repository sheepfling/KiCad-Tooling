"""Source-bound connector contact rating evidence replay regression."""

from __future__ import annotations

import pytest

from tests.electrical_evidence_support import (
    ElectricalEvidenceWorkspace,
    reject_omitted_electrical_checks,
)
from tests.electrical_evidence_support import (
    electrical_evidence_workspace as _electrical_evidence_workspace_fixture,  # noqa: F401
)
from tests.test_connector_contact_ratings import (
    native_netlist_xml as connector_contact_netlist_xml,
)
from tests.test_connector_contact_ratings import (
    requirement as connector_contact_requirement,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.evidence_lint,
    pytest.mark.template_checkout,
]


def test_connector_contact_rating_replays_and_rejects_omitted_checks(
    electrical_evidence_workspace: ElectricalEvidenceWorkspace,
) -> None:
    check_id = "connector-contact-rating/host-connector/contact-vbus-contact/utilization"
    result = electrical_evidence_workspace.run_native_requirement(
        contract_field="connector_contact_ratings",
        requirement=connector_contact_requirement(),
        netlist_xml=connector_contact_netlist_xml(),
        output_name="connector-contact-rating-replay",
    )

    assert {check.id: check for check in result.checks}[check_id].status == "PASS"
    electrical_evidence_workspace.verify()
    reject_omitted_electrical_checks(
        electrical_evidence_workspace,
        (
            "connector-contact-rating/host-connector/identity",
            "connector-contact-rating/host-connector/contact-vbus-contact/assignment",
            check_id,
        ),
    )

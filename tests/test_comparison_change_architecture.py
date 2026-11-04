"""Guard the owner and typed inputs shared by saved comparison operations."""

from __future__ import annotations

from typing import get_type_hints

import pytest

from kicad_tooling.hwrepo import (
    board_variant_compare_models,
    bom_change,
    bom_compare_models,
    product_revision_bom_models,
    product_variant_bom_models,
    verification_history_models,
)
from kicad_tooling.hwrepo.comparison_change import change_state
from kicad_tooling.hwrepo.comparison_change_models import Change
from kicad_tooling.hwrepo.findings_view_models import FindingsViewReport
from kicad_tooling.hwrepo.native_project_validation_models import ValidationSummary
from kicad_tooling.hwrepo.project_verification_report_models import ProjectVerificationReport
from kicad_tooling.hwrepo.verification_history_evidence import (
    HistoryReceiptModel,
    _item,  # pyright: ignore[reportPrivateUsage]
)
from kicad_tooling.hwrepo.verification_history_models import HistoryEvidence

pytestmark = pytest.mark.architecture


def test_before_after_state_has_one_typed_owner_and_compatibility_export() -> None:
    assert bom_change.change_state is change_state
    assert bom_compare_models.Change is Change
    assert board_variant_compare_models.Change is Change
    assert product_revision_bom_models.Change is Change
    assert product_variant_bom_models.Change is Change
    assert verification_history_models.Change is Change
    hints = get_type_hints(change_state, include_extras=True)
    assert hints["before"] != object | None
    assert hints["before"] == hints["after"]
    assert hints["return"] is Change


def test_history_receipt_admission_uses_only_supported_report_models() -> None:
    assert HistoryReceiptModel == ValidationSummary | FindingsViewReport | ProjectVerificationReport
    assert (
        get_type_hints(_item, include_extras=True)["return"]
        == tuple[HistoryEvidence, HistoryReceiptModel | None]
    )

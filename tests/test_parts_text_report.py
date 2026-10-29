"""Parts text reports expose the same purchasing groups as the typed plan."""

from kicad_tooling.hwrepo.models import (
    PartRecord,
    PartsCatalog,
    PartStatus,
    PurchasingComponent,
    PurchasingPreferences,
    PurchasingReport,
)
from kicad_tooling.hwrepo.parts_workflow import text_report
from kicad_tooling.hwrepo.purchasing import plan


def _part(identifier: str, mpn: str) -> PartRecord:
    return PartRecord(
        id=identifier,
        revision="A",
        description="Reviewed component",
        part_class="resistor",
        unit="each",
        manufacturer="Yageo",
        mpn=mpn,
        datasheet_url="https://example.test/datasheet",
        lifecycle="active",
        status=PartStatus.APPROVED,
    )


def _component(
    reference: str, part_id: str | None, *, dnp: bool = False, exclude: bool = False
) -> PurchasingComponent:
    return PurchasingComponent(
        reference=reference,
        value="1k",
        footprint="R:0603",
        part_id=part_id,
        dnp=dnp,
        exclude_from_bom=exclude,
    )


def test_text_report_lists_all_groups_quantities_and_unresolved_components() -> None:
    purchase_plan = plan(
        (
            _component("R1", "RES-1"),
            _component("R2", "RES-1"),
            _component("R3", "RES-2"),
            _component("R4", None),
            _component("R5", "RES-1", dnp=True),
            _component("R6", "RES-1", exclude=True),
            _component("R7", "RES-1", dnp=True, exclude=True),
        ),
        PartsCatalog(schema_version="1", parts=(_part("RES-1", "ABC1"), _part("RES-2", "ABC2"))),
        PurchasingPreferences(boards=3, spare_percent=20, spare_minimum=1),
        ("RES-1", "RES-2"),
    )
    report = PurchasingReport(
        project_id="example",
        status=purchase_plan.status,
        plan=purchase_plan,
        receipt_dir="build/parts",
    )

    text = text_report(report)
    assert (
        "RES-1 rev A: Yageo ABC1; references: R1, R2; per board: 2; required: 6; spares: 2; order quantity: 8"
        in text
    )
    assert (
        "RES-2 rev A: Yageo ABC2; references: R3; per board: 1; required: 3; spares: 1; order quantity: 4"
        in text
    )
    assert "Fitted references without a BOM group: R4" in text
    assert (
        "Excluded references: R5 (DNP), R6 (excluded from BOM), R7 (DNP, excluded from BOM)" in text
    )
    assert "MISSING_PART_ID (R4)" in text


def test_text_report_handles_empty_groups_and_blocked_plan() -> None:
    purchase_plan = plan(
        (_component("R1", None),),
        PartsCatalog(schema_version="1", parts=(_part("RES-1", "ABC1"),)),
        PurchasingPreferences(),
        ("RES-1",),
    )
    text = text_report(
        PurchasingReport(
            project_id="example",
            status=purchase_plan.status,
            plan=purchase_plan,
            receipt_dir="build/parts",
        )
    )
    assert "BOM groups: none available for ordering review." in text
    assert "Fitted references without a BOM group: R1" in text

    blocked = text_report(
        PurchasingReport(
            project_id="example",
            status="BLOCKED",
            issues=("Native evidence missing",),
            receipt_dir="build/parts",
        )
    )
    assert "Blocked: Native evidence missing" in blocked
    assert "BOM groups" not in blocked


def test_order_review_readiness_does_not_hide_native_validation_failure() -> None:
    purchase_plan = plan(
        (_component("R1", "RES-1"),),
        PartsCatalog(schema_version="1", parts=(_part("RES-1", "ABC1"),)),
        PurchasingPreferences(),
        ("RES-1",),
    )
    assert purchase_plan.status == "READY_FOR_ORDER_REVIEW"
    report = PurchasingReport(
        project_id="example",
        status=purchase_plan.status,
        plan=purchase_plan,
        receipt_dir="build/parts",
        native_status="FAIL",
    )
    text = text_report(report)
    assert "Parts to order: READY_FOR_ORDER_REVIEW" in text
    assert "Native validation: FAIL" in text
    assert "Inspect the retained validation receipt" in text


def test_text_report_identifies_duplicate_fitted_references_as_ambiguous() -> None:
    purchase_plan = plan(
        (
            _component("R1", "RES-1"),
            _component("R1", "RES-1", dnp=True),
            _component("R2", "RES-1"),
            _component("R2", None),
            _component("R3", None),
        ),
        PartsCatalog(schema_version="1", parts=(_part("RES-1", "ABC1"),)),
        PurchasingPreferences(),
        ("RES-1",),
    )
    text = text_report(
        PurchasingReport(
            project_id="example",
            status=purchase_plan.status,
            plan=purchase_plan,
            receipt_dir="build/parts",
        )
    )
    assert (
        "Purchasing group membership is ambiguous for duplicate fitted references: R1, R2" in text
    )
    assert "Fitted references without a BOM group: R3" in text
    assert "Excluded references: R1 (DNP)" in text

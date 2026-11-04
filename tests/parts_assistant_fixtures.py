"""Prepared-order fixtures shared by the parts-assistant HTTP tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from kicad_tooling.hwrepo.contract_coach import NetlistRunner
from kicad_tooling.hwrepo.purchasing import write_csvs
from kicad_tooling.hwrepo.purchasing_models import (
    PurchasingComponent,
    PurchasingPlan,
    PurchasingPreferences,
    PurchasingReport,
)


def projected_order_preparation(
    template: PurchasingReport, plan: PurchasingPlan
) -> Callable[..., PurchasingReport]:
    """Return a prepared-order callback with fresh files for each request."""

    def projected(
        root: Path,
        project_id: str,
        output: Path,
        runner: NetlistRunner,
        *,
        boards: int,
        spare_percent: int,
        spare_minimum: int,
    ) -> PurchasingReport:
        updated = plan.model_copy(
            update={
                "preferences": PurchasingPreferences(
                    boards=boards, spare_percent=spare_percent, spare_minimum=spare_minimum
                ),
                "components": (
                    PurchasingComponent(
                        reference="R1",
                        value="1k",
                        footprint="Device:R",
                        part_id="RES-1",
                    ),
                ),
                "lines": (
                    plan.lines[0].model_copy(
                        update={"required": boards * 2, "spares": 0, "quantity": boards * 2}
                    ),
                ),
            }
        )
        write_csvs(output, updated)
        return template.model_copy(update={"receipt_dir": str(output), "plan": updated})

    return projected

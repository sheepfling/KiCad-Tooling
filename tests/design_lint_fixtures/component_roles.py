"""Small reviewed component-role maps shared by synthetic lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.component_role_models import (
    ComponentRoleBinding,
    ComponentRoleMap,
    ComponentRolePin,
)


def custom_led_role_map(
    basis: str = "Synthetic reviewed library symbol declaration",
) -> ComponentRoleMap:
    """Map one synthetic two-pin LED using its complete native identity."""
    return ComponentRoleMap(
        entries=(
            ComponentRoleBinding(
                part_id="training-led",
                symbol="Training:LED_5mm",
                footprint="Training:LED_0603",
                role="led",
                pins=(
                    ComponentRolePin(number="1", function="A", electrical_type="passive"),
                    ComponentRolePin(number="2", function="K", electrical_type="passive"),
                ),
                basis=basis,
            ),
        )
    )


def custom_battery_role_map(
    basis: str = "Synthetic reviewed battery symbol declaration",
) -> ComponentRoleMap:
    """Map one synthetic two-pin battery using its complete native identity."""
    return ComponentRoleMap(
        entries=(
            ComponentRoleBinding(
                part_id="training-battery",
                symbol="Training:Battery_2pin",
                footprint="Training:Battery_Cell_2pin",
                role="battery",
                pins=(
                    ComponentRolePin(number="1", function="+", electrical_type="passive"),
                    ComponentRolePin(number="2", function="-", electrical_type="passive"),
                ),
                basis=basis,
            ),
        )
    )

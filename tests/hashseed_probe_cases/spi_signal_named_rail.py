"""Hash-seed report cases for SPI signal pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.spi_signal_named_rail import spi_signal_on_named_rail_netlist


def report_cases() -> dict[str, object]:
    fault = evaluate(
        "synthetic-spi-signal-named-rail-fault",
        coach(spi_signal_on_named_rail_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-spi-signal-named-rail-control",
        coach(spi_signal_on_named_rail_netlist(rail_name="CLOCK_A")),
        DesignLintPolicy(),
    )
    return {
        "spi_signal_named_rail_fault": fault.model_dump(mode="json"),
        "spi_signal_named_rail_control": control.model_dump(mode="json"),
    }

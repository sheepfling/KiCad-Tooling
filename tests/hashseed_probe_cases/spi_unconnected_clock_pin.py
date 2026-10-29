"""Cross-process cases for an open clock on a partially assigned SPI channel."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.spi_unconnected_clock_pin import spi_unconnected_clock_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    source = spi_unconnected_clock_netlist(open_pins=("U1.1",))
    fault = source.model_copy(update={"nets": dict(reversed(tuple(source.nets.items())))})
    control = spi_unconnected_clock_netlist(open_pins=())
    return {
        "spi_unconnected_clock_pin_fault": evaluate(
            "synthetic-spi-clock-open-fault", coach(fault), DesignLintPolicy()
        ).model_dump(mode="json"),
        "spi_unconnected_clock_pin_control": evaluate(
            "synthetic-spi-clock-open-control", coach(control), DesignLintPolicy()
        ).model_dump(mode="json"),
    }

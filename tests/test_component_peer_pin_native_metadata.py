"""Native fixture metadata diagnostics use precise synthetic evidence."""

from __future__ import annotations

import pytest

from kicad_tooling.ci_hosted_component_peer_metadata import native_peer_metadata_mismatches
from kicad_tooling.hwrepo.models import NetlistContract
from tests.component_peer_pin_support import peer_signal_input_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


def _mismatches(observed: NetlistContract) -> tuple[str, ...]:
    return native_peer_metadata_mismatches(
        observed,
        expected_symbols={
            "U1": "Synthetic:SignalInputModule",
            "U2": "Synthetic:SignalInputModule",
        },
        references=("U1", "U2"),
        pin_type="input",
        pin_function="IN",
    )


def _native_metadata_control() -> NetlistContract:
    observed = peer_signal_input_netlist()
    return observed.model_copy(
        update={
            "pin_functions": {
                **observed.pin_functions,
                "U1.1": "Pin_1",
                "U2.1": "Pin_1",
            },
            "pin_electrical_types": {
                **observed.pin_electrical_types,
                "U1.1": "passive",
                "U2.1": "passive",
            },
        }
    )


def test_complete_native_peer_metadata_matches_synthetic_control() -> None:
    assert _mismatches(_native_metadata_control()) == ()


@pytest.mark.parametrize(
    ("field", "key", "value"),
    (
        ("component_symbols", "U2", "Synthetic:DifferentModule"),
        ("component_pin_numbers", "U2", ("1",)),
        ("pin_electrical_types", "U2.2", "passive"),
        ("pin_functions", "U2.2", "OUT"),
    ),
)
def test_native_peer_metadata_mismatch_names_expected_and_observed_fields(
    field: str, key: str, value: object
) -> None:
    observed = _native_metadata_control()
    changed = dict(getattr(observed, field))
    changed[key] = value
    report = _mismatches(observed.model_copy(update={field: changed}))

    assert len(report) == 1
    assert field in report[0]
    assert "expected" in report[0]
    assert "observed" in report[0]

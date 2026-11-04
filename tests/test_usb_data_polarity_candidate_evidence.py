"""USB polarity candidates retain their exact pin and netlist source."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_interfaces_usb_data_polarity import (
    usb_data_polarity_label_candidates,
)
from kicad_tooling.hwrepo.design_lint_usb_data_polarity_candidate_evidence import (
    UsbDataPolarityCandidate,
    UsbDataPolarityFindingEvidence,
    project_usb_data_polarity_evidence,
)
from tests.design_lint_fixtures import complementary_usb_netlist


def _candidate() -> UsbDataPolarityCandidate:
    observed = complementary_usb_netlist(positive_net="USB_DM", negative_net="USB_DP")
    candidates = usb_data_polarity_label_candidates(observed)
    candidate = candidates[0]
    assert isinstance(candidate, UsbDataPolarityCandidate)
    return candidate


def test_usb_polarity_candidate_retains_exact_source_and_projection() -> None:
    candidate = _candidate()
    source = candidate.source_evidence

    assert source.observed.pin_functions[source.pin] == source.function
    assert source.pin in source.observed.nets[source.net]
    assert project_usb_data_polarity_evidence(source).evidence == candidate.evidence
    assert candidate.evidence == {
        "pin": ("J1.1",),
        "pin_function": ("USB_D+",),
        "pin_side": ("positive",),
        "net": ("USB_DM",),
        "net_side": ("negative",),
        "port_group": ("unindexed",),
    }


def test_usb_polarity_source_rejects_values_outside_the_observed_netlist() -> None:
    source = _candidate().source_evidence

    with pytest.raises(ValueError, match="source netlist"):
        replace(source, function="USB_DM")

    with pytest.raises(ValueError, match="must contain its source pin"):
        replace(source, net="USB_DP")


def test_usb_polarity_candidate_rejects_projection_mismatch() -> None:
    candidate = _candidate()

    with pytest.raises(ValueError, match="typed source projection"):
        replace(candidate, evidence={"pin": ("wrong",)})


def test_usb_polarity_source_rejects_non_conflicting_sides() -> None:
    source = _candidate().source_evidence
    observed = source.observed.model_copy(
        update={"nets": {**source.observed.nets, "USB_DP": (source.pin,)}}
    )

    with pytest.raises(ValueError, match="opposite pin and net sides"):
        UsbDataPolarityFindingEvidence(
            observed=observed,
            pin=source.pin,
            function=source.function,
            pin_side="positive",
            net="USB_DP",
            net_side="positive",
            port_group=source.port_group,
        )

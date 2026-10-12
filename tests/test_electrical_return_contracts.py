"""Pytest coverage for authored grounding and return-pin requirements."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.analysis_state_models import AnalysisPending
from kicad_tooling.hwrepo.electrical import grounding_checks
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    GroundDomain,
    GroundingAnalysis,
    NetlistContract,
)
from kicad_tooling.hwrepo.return_nets import return_net_groups

pytestmark = [pytest.mark.design_lint, pytest.mark.return_path_lint]


def isolated_ground_inputs() -> tuple[GroundingAnalysis, NetlistContract]:
    requirement = GroundingAnalysis(
        basis="Independent synthetic pin requirements",
        domains=(
            GroundDomain(net="GND", pins=("U1.2", "J1.2")),
            GroundDomain(net="AGND", pins=("U2.2",)),
        ),
    )
    observed = NetlistContract(
        components={
            reference: ComponentContract(value="fixture", footprint="")
            for reference in ("U1", "U2", "J1")
        },
        nets={"GND": ("U1.2", "J1.2"), "AGND": ("U2.2",)},
    )
    return requirement, observed


def test_grounding_accepts_distinct_declared_domains() -> None:
    requirement, observed = isolated_ground_inputs()

    assert all(item.status == "PASS" for item in grounding_checks(requirement, observed))


@pytest.mark.parametrize(
    "nets",
    (
        {"GND": ("U1.2",), "AGND": ("U2.2",)},
        {"GND": ("U1.2", "J1.2", "U2.2")},
        {"GND": ("U1.2", "J1.2", "U1.3"), "AGND": ("U2.2",)},
        {"GND": ("U1.2", "J1.2"), "AGND": ("U2.2",), "SHORT": ("U1.2",)},
    ),
)
def test_grounding_rejects_missing_wrong_or_extra_pins(nets: dict[str, tuple[str, ...]]) -> None:
    requirement, observed = isolated_ground_inputs()
    changed = observed.model_copy(update={"nets": nets})

    assert any(item.status == "FAIL" for item in grounding_checks(requirement, changed))


def test_new_component_requires_ground_review_or_explicit_exemption() -> None:
    requirement, observed = isolated_ground_inputs()
    observed = observed.model_copy(
        update={
            "components": {
                **observed.components,
                "R1": ComponentContract(value="1k", footprint=""),
            }
        }
    )

    assert grounding_checks(requirement, observed)[-1].status == "FAIL"
    exempt = requirement.model_copy(
        update={"exempt_components": {"R1": "Series resistor, no ground pin"}}
    )
    assert grounding_checks(exempt, observed)[-1].status == "PASS"
    contradictory = exempt.model_copy(
        update={"exempt_components": {"U1": "Contradictory exemption"}}
    )
    assert grounding_checks(contradictory, observed)[-1].status == "FAIL"


def test_numbered_connector_returns_need_pinout_review_even_if_connector_is_covered() -> None:
    observed = NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic connector", footprint="")
            for reference in ("J1", "J2")
        },
        nets={
            "GND": ("J1.9", "J2.9"),
            "0V CTRL 1": ("J1.7",),
            "0V CTRL 2": ("J2.7",),
            "CTRL 1": ("J1.1",),
            "CTRL 2": ("J2.1",),
        },
    )
    groups = return_net_groups(observed)
    assert len(groups) == 1
    assert set(groups[0].nets) == {"0V CTRL 1", "0V CTRL 2"}

    requirement = GroundingAnalysis(
        basis="Independent synthetic connector pinout",
        domains=(GroundDomain(net="GND", pins=("J1.9", "J2.9")),),
    )
    checks = {row.id: row for row in grounding_checks(requirement, observed)}
    assert checks["grounding/GND"].status == "PASS"
    assert checks["grounding/component-coverage"].status == "PASS"
    assert checks["grounding/return-net-review"].status == "FAIL"
    assert "J1.7" in checks["grounding/return-net-review"].detail

    pending = grounding_checks(
        AnalysisPending(mode="pending", reason="Connector pinout review pending"), observed
    )
    assert pending[0].status == "NOT_CONFIGURED"
    assert "0V CTRL 1" in pending[0].detail

    reviewed = requirement.model_copy(
        update={
            "domains": (
                *requirement.domains,
                GroundDomain(net="0V CTRL 1", pins=("J1.7",)),
                GroundDomain(net="0V CTRL 2", pins=("J2.7",)),
            )
        }
    )
    assert all(row.status == "PASS" for row in grounding_checks(reviewed, observed))


def test_three_usb_signal_grounds_must_match_a_declared_common_net() -> None:
    observed = NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic part", footprint="")
            for reference in ("U1", "J1", "J2", "J3")
        },
        nets={
            "GND": ("U1.2",),
            "USB1_GND": ("J1.4",),
            "USB2_GND": ("J2.4",),
            "USB3_GND": ("J3.4",),
            "USB1_SHIELD": ("J1.5",),
            "USB2_SHIELD": ("J2.5",),
            "USB3_SHIELD": ("J3.5",),
            "USB1_DP": ("J1.3",),
        },
    )
    groups = return_net_groups(observed)
    assert len(groups) == 1
    assert set(groups[0].nets) == {"USB1_GND", "USB2_GND", "USB3_GND"}

    requirement = GroundingAnalysis(
        basis="Synthetic approved pinout requires one signal-ground domain",
        domains=(GroundDomain(net="GND", pins=("U1.2", "J1.4", "J2.4", "J3.4")),),
    )
    checks = {row.id: row for row in grounding_checks(requirement, observed)}
    assert checks["grounding/GND"].status == "FAIL"
    assert checks["grounding/component-coverage"].status == "PASS"
    assert checks["grounding/return-net-review"].status == "FAIL"

    fixed_nets = {
        name: pins
        for name, pins in observed.nets.items()
        if name not in {"GND", "USB1_GND", "USB2_GND", "USB3_GND"}
    }
    fixed = observed.model_copy(
        update={"nets": {**fixed_nets, "GND": ("U1.2", "J1.4", "J2.4", "J3.4")}}
    )
    assert not return_net_groups(fixed)
    assert all(row.status == "PASS" for row in grounding_checks(requirement, fixed))


def test_separate_serial_returns_pass_when_isolation_is_declared() -> None:
    observed = NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic part", footprint="")
            for reference in ("U1", "U2", "J1", "J2")
        },
        nets={
            "SERIAL_1_GND": ("U1.3", "J1.5"),
            "SERIAL_2_GND": ("U2.3", "J2.5"),
        },
    )
    assert set(return_net_groups(observed)[0].nets) == {"SERIAL_1_GND", "SERIAL_2_GND"}

    isolated = GroundingAnalysis(
        basis="Synthetic approved pinout requires separate isolated returns",
        domains=(
            GroundDomain(net="SERIAL_1_GND", pins=("U1.3", "J1.5")),
            GroundDomain(net="SERIAL_2_GND", pins=("U2.3", "J2.5")),
        ),
    )
    assert all(row.status == "PASS" for row in grounding_checks(isolated, observed))

    common = GroundingAnalysis(
        basis="Synthetic approved pinout requires common returns",
        domains=(GroundDomain(net="SERIAL_1_GND", pins=("U1.3", "J1.5", "U2.3", "J2.5")),),
    )
    checks = {row.id: row for row in grounding_checks(common, observed)}
    assert checks["grounding/SERIAL_1_GND"].status == "FAIL"
    assert checks["grounding/return-net-review"].status == "FAIL"


def test_one_stray_usb_return_is_caught_by_the_declared_pinout() -> None:
    observed = NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic part", footprint="")
            for reference in ("U1", "J1", "J2", "J3")
        },
        nets={"GND": ("U1.2", "J1.4", "J2.4"), "USB3_GND": ("J3.4",)},
    )
    assert not return_net_groups(observed)

    requirement = GroundingAnalysis(
        basis="Synthetic approved pinout requires one signal-ground domain",
        domains=(GroundDomain(net="GND", pins=("U1.2", "J1.4", "J2.4", "J3.4")),),
    )
    checks = {row.id: row for row in grounding_checks(requirement, observed)}
    assert checks["grounding/GND"].status == "FAIL"
    assert checks["grounding/component-coverage"].status == "PASS"
    assert "grounding/return-net-review" not in checks


def test_protocol_numbers_and_shields_are_not_return_group_indices() -> None:
    observed = NetlistContract(
        components={},
        nets={
            "RS232_GND": ("J1.5",),
            "RS485_GND": ("J2.5",),
            "USB1_SHIELD": ("J3.5",),
            "USB2_SHIELD": ("J4.5",),
        },
    )

    assert not return_net_groups(observed)


def test_misleading_return_names_need_reasoned_exceptions_and_no_stale_waiver() -> None:
    observed = NetlistContract(
        components={"J1": ComponentContract(value="Synthetic connector", footprint="")},
        nets={
            "GND": ("J1.9",),
            "RETURN STATUS 1": ("J1.1",),
            "RETURN STATUS 2": ("J1.2",),
        },
    )
    requirement = GroundingAnalysis(
        basis="Synthetic pinout distinguishes logic status from ground",
        domains=(GroundDomain(net="GND", pins=("J1.9",)),),
        reviewed_return_exceptions={
            "RETURN STATUS 1": "Logic status, not a return",
            "RETURN STATUS 2": "Logic status, not a return",
        },
    )
    assert all(row.status == "PASS" for row in grounding_checks(requirement, observed))

    stale = requirement.model_copy(
        update={
            "reviewed_return_exceptions": {
                **requirement.reviewed_return_exceptions,
                "RETURN STATUS 3": "Old pinout",
            }
        }
    )
    review = next(
        row for row in grounding_checks(stale, observed) if row.id.endswith("return-net-review")
    )
    assert review.status == "FAIL"

    with pytest.raises(ValueError):
        GroundingAnalysis(
            basis="Conflicting synthetic declaration",
            domains=(GroundDomain(net="GND", pins=("J1.9",)),),
            reviewed_return_exceptions={"GND": "Contradiction"},
        )

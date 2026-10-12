"""Focused synthetic regressions for the decoupling lint theme."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import (
    evaluate,
)
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ComponentRoleBinding,
    ComponentRoleMap,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import (
    coach,
    custom_decoupling_capacitor_role_map,
    custom_ic_decoupling_capacitor_fixture,
    ic_power_decoupling_fixture,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
]


def test_ic_power_rail_without_fitted_capacitor_needs_review() -> None:
    report = evaluate(
        "synthetic-decoupling-presence",
        coach(ic_power_decoupling_fixture()),
        DesignLintPolicy(),
    )
    findings = [
        item for item in report.findings if item.rule_id == "power.ic_rail_without_fitted_capacitor"
    ]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].subject == "+3V3: IC supply decoupling review"
    assert findings[0].evidence == {
        "net": ("+3V3",),
        "power_input_pins": ("U1.1",),
        "component_references": ("U1",),
    }
    assert "does not establish local" in findings[0].message


def test_fitted_capacitor_to_return_controls_review() -> None:
    report = evaluate(
        "synthetic-decoupling-presence-control",
        coach(ic_power_decoupling_fixture(capacitor_net="+3V3")),
        DesignLintPolicy(),
    )
    assert "power.ic_rail_without_fitted_capacitor" not in {
        item.rule_id for item in report.findings
    }


def test_custom_decoupling_capacitor_requires_exact_project_role() -> None:
    rule_id = "power.ic_rail_without_fitted_capacitor"
    source = custom_ic_decoupling_capacitor_fixture()
    unclassified = evaluate(
        "synthetic-custom-decoupling-capacitor",
        coach(source),
        DesignLintPolicy(),
    )
    assert unclassified.status == "REVIEW"
    assert {item.rule_id for item in unclassified.findings if item.rule_id == rule_id} == {rule_id}

    role_map = custom_decoupling_capacitor_role_map()
    mapped = evaluate(
        "synthetic-custom-decoupling-capacitor",
        coach(source),
        DesignLintPolicy(component_role_map=role_map),
    )
    assert mapped.status == "PASS"
    assert rule_id not in {item.rule_id for item in mapped.findings}
    assert "component.led_directly_driven_from_output" not in {
        item.rule_id for item in mapped.findings
    }

    wrong_return = evaluate(
        "synthetic-custom-decoupling-capacitor",
        coach(custom_ic_decoupling_capacitor_fixture(capacitor_reference_net="CAP_REF")),
        DesignLintPolicy(component_role_map=role_map),
    )
    assert wrong_return.status == "REVIEW"
    assert rule_id in {item.rule_id for item in wrong_return.findings}

    dnp = evaluate(
        "synthetic-custom-decoupling-capacitor",
        coach(custom_ic_decoupling_capacitor_fixture(dnp_capacitor=True)),
        DesignLintPolicy(component_role_map=role_map),
    )
    assert dnp.status == "REVIEW"
    assert rule_id in {item.rule_id for item in dnp.findings}

    stale_map = role_map.model_copy(
        update={
            "entries": (role_map.entries[0].model_copy(update={"footprint": "Synthetic:Other"}),)
        }
    )
    stale = evaluate(
        "synthetic-custom-decoupling-capacitor",
        coach(source),
        DesignLintPolicy(component_role_map=stale_map),
    )
    assert stale.status == "BLOCKED"
    assert any("stale at C1" in issue for issue in stale.issues)

    with pytest.raises(ValidationError):
        ComponentRoleBinding.model_validate(
            {
                **role_map.entries[0].model_dump(),
                "pins": (role_map.entries[0].pins[0].model_dump(),),
            }
        )
    with pytest.raises(ValidationError):
        ComponentRoleBinding.model_validate(
            {
                **role_map.entries[0].model_dump(),
                "pins": (
                    role_map.entries[0].pins[0].model_dump(),
                    {
                        **role_map.entries[0].pins[1].model_dump(),
                        "electrical_type": "input",
                    },
                ),
            }
        )


def test_custom_decoupling_capacitor_suppression_is_input_order_stable() -> None:
    source = custom_ic_decoupling_capacitor_fixture()
    policy = DesignLintPolicy(component_role_map=custom_decoupling_capacitor_role_map())
    original = evaluate("synthetic-custom-decoupling-capacitor", coach(source), policy)
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    role_binding = custom_decoupling_capacitor_role_map().entries[0]
    reordered_policy = DesignLintPolicy(
        component_role_map=ComponentRoleMap(
            entries=(role_binding.model_copy(update={"pins": tuple(reversed(role_binding.pins))}),)
        )
    )
    repeated = evaluate(
        "synthetic-custom-decoupling-capacitor",
        coach(reordered_source),
        reordered_policy,
    )
    assert original.status == "PASS"
    assert repeated.status == "PASS"
    assert original.findings == repeated.findings
    assert original.issues == repeated.issues


def test_ic_decoupling_prompt_is_order_stable_and_fitted_capacitor_clears_it() -> None:
    rule_id = "power.ic_rail_without_fitted_capacitor"
    source = ic_power_decoupling_fixture()

    def lint(netlist: NetlistContract) -> tuple[str, DesignLintReport]:
        source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
        return source_hash, evaluate(
            "synthetic-decoupling-presence",
            coach(netlist, source_hash),
            DesignLintPolicy(),
        )

    source_hash, original = lint(source)
    assert original.netlist_sha256 == source_hash
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == rule_id
    }
    assert len(original_findings) == 1

    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    reordered_hash, reordered = lint(reordered_source)
    assert source_hash != reordered_hash
    assert reordered.netlist_sha256 == reordered_hash
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == rule_id
    }
    assert reordered_findings == original_findings

    repaired_hash, repaired = lint(ic_power_decoupling_fixture(capacitor_net="+3V3"))
    assert source_hash != repaired_hash
    assert rule_id not in {item.rule_id for item in repaired.findings}


def _ic_power_decoupling_scope_cases() -> tuple[tuple[str, NetlistContract, bool], ...]:
    custom_return = ic_power_decoupling_fixture(
        capacitor_net="+3V3", capacitor_reference_net="CAP_REF"
    )
    custom_return = custom_return.model_copy(
        update={
            "components": {
                **custom_return.components,
                "U2": ComponentContract(value="Synthetic return pin", footprint=""),
            },
            "component_symbols": {
                **custom_return.component_symbols,
                "U2": "Synthetic:ReturnPin",
            },
            "nets": {**custom_return.nets, "CAP_REF": ("C1.2", "U2.2")},
            "pin_functions": {**custom_return.pin_functions, "U2.2": "GND"},
        }
    )
    return (
        # A DNP capacitor does not count as fitted.
        (
            "dnp-capacitor",
            ic_power_decoupling_fixture(capacitor_net="+3V3", dnp_capacitor=True),
            True,
        ),
        # A capacitor on another rail does not cover this rail.
        ("other-rail", ic_power_decoupling_fixture(capacitor_net="+5V"), True),
        # A capacitor without a recognized return connection does not count.
        (
            "return-on-positive-rail",
            ic_power_decoupling_fixture(capacitor_net="+3V3", capacitor_reference_net="+5V"),
            True,
        ),
        (
            "unmapped-return-net",
            ic_power_decoupling_fixture(capacitor_net="+3V3", capacitor_reference_net="CAP_REF"),
            True,
        ),
        ("mapped-return-pin", custom_return, False),
        # An open or same-net terminal assignment does not count.
        (
            "open-capacitor-terminal",
            ic_power_decoupling_fixture(capacitor_net="+3V3", capacitor_reference_net=None),
            True,
        ),
        (
            "same-net-capacitor-terminals",
            ic_power_decoupling_fixture(capacitor_net="+3V3", capacitor_reference_net="+3V3"),
            True,
        ),
        # A CP-prefixed IC library name is not a capacitor symbol.
        (
            "cp-prefixed-device",
            ic_power_decoupling_fixture().model_copy(
                update={"component_symbols": {"U1": "Synthetic:CP2102"}}
            ),
            True,
        ),
        # DNP ICs and connector power pins are outside the rule.
        ("dnp-ic", ic_power_decoupling_fixture(dnp_ic=True), False),
        ("connector-power-pin", ic_power_decoupling_fixture(reference="J1"), False),
        # Only native power-input pins on narrowly recognized positive rails qualify.
        ("passive-pin", ic_power_decoupling_fixture(electrical_type="passive"), False),
        (
            "unrecognized-rail",
            ic_power_decoupling_fixture(rail="LOCAL_A", power_function="LOCAL_SUPPLY"),
            False,
        ),
    )


_IC_POWER_DECOUPLING_SCOPE_CASES = _ic_power_decoupling_scope_cases()


@pytest.mark.parametrize(
    ("case_name", "source", "expected"),
    _IC_POWER_DECOUPLING_SCOPE_CASES,
    ids=[case[0] for case in _IC_POWER_DECOUPLING_SCOPE_CASES],
)
def test_ic_power_decoupling_enforces_capacitor_and_scope_boundaries(
    case_name: str,
    source: NetlistContract,
    expected: bool,
) -> None:
    report = evaluate(
        "synthetic-decoupling-presence-boundary",
        coach(source),
        DesignLintPolicy(),
    )
    present = "power.ic_rail_without_fitted_capacitor" in {item.rule_id for item in report.findings}
    assert present == expected, case_name


def test_ic_power_decoupling_review_supports_rule_policy_and_exact_ignore() -> None:
    source = ic_power_decoupling_fixture()
    initial = evaluate("synthetic-decoupling-presence-policy", coach(source), DesignLintPolicy())
    finding = next(
        item
        for item in initial.findings
        if item.rule_id == "power.ic_rail_without_fitted_capacitor"
    )
    blocked = evaluate(
        "synthetic-decoupling-presence-policy",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="power.ic_rail_without_fitted_capacitor",
                    mode="block",
                    reason="Synthetic project requires owner review of uncapped IC rails",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = evaluate(
        "synthetic-decoupling-presence-policy",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="power.ic_rail_without_fitted_capacitor",
                    mode="off",
                    reason="Synthetic project documents internal or off-board decoupling",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"
    assert (
        next(
            item
            for item in disabled.findings
            if item.rule_id == "power.ic_rail_without_fitted_capacitor"
        ).disposition
        == "RULE_OFF"
    )

    ignored = evaluate(
        "synthetic-decoupling-presence-policy",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id="power.ic_rail_without_fitted_capacitor",
                    fingerprint=finding.fingerprint,
                    reason="Synthetic control records an intentional remote decoupling plan",
                ),
            )
        ),
    )
    assert ignored.status == "PASS"
    assert (
        next(
            item
            for item in ignored.findings
            if item.rule_id == "power.ic_rail_without_fitted_capacitor"
        ).disposition
        == "IGNORED"
    )

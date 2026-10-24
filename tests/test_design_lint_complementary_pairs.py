"""Focused synthetic regressions for the complementary pairs lint theme."""

from __future__ import annotations

import hashlib
import re

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import (
    candidates,
    evaluate,
    fingerprint,
)
from kicad_tooling.hwrepo.models import (
    ComplementaryPinFunctionAlias,
    ComplementaryPinFunctionAliasMap,
    ComponentContract,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
)
from tests.design_lint_fixtures import (
    can_netlist,
    coach,
    complementary_usb_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


def test_complementary_pair_assignments_are_reviewed_without_inferred_requirements() -> None:
    missing_side = evaluate(
        "synthetic-usb", coach(complementary_usb_netlist(negative_net=None)), DesignLintPolicy()
    )
    pair_findings = [
        item
        for item in missing_side.findings
        if item.rule_id == "bus.complementary_pair_assignment"
    ]
    assert len(pair_findings) == 1
    assert pair_findings[0].evidence["positive_pins"] == ("J1.1",)
    assert pair_findings[0].evidence["negative_pins"] == ("J1.2",)
    assert pair_findings[0].evidence["negative_nets"] == ()
    assert "lack a unique" in pair_findings[0].message

    shorted = complementary_usb_netlist(positive_net="USB_DATA", negative_net="USB_DATA")
    shorted_report = evaluate("synthetic-usb", coach(shorted), DesignLintPolicy())
    shorted_findings = [
        item
        for item in shorted_report.findings
        if item.rule_id == "bus.complementary_pair_assignment"
    ]
    assert len(shorted_findings) == 1
    assert "share one schematic net" in shorted_findings[0].message

    can_shorted = can_netlist().model_copy(update={"nets": {"CAN_BUS": ("U1.1", "U1.2")}})
    can_pair_findings = [
        item
        for item in evaluate("synthetic-can", coach(can_shorted), DesignLintPolicy()).findings
        if item.rule_id == "bus.complementary_pair_assignment"
    ]
    assert len(can_pair_findings) == 1

    missing_counterpart = NetlistContract(
        components={},
        nets={"TX_POS": ("U3.1",)},
        component_symbols={"U3": "Synthetic:DifferentialDevice"},
        pin_functions={"U3.1": "TXP"},
    )
    missing_function = next(
        item
        for item in candidates(missing_counterpart)
        if item.rule_id == "bus.complementary_pair_assignment"
    )
    assert missing_function.evidence["negative_pins"] == ()
    assert "absent from the pin-function inventory" in missing_function.message

    valid_pair = evaluate("synthetic-usb", coach(complementary_usb_netlist()), DesignLintPolicy())
    assert not (
        any(item.rule_id == "bus.complementary_pair_assignment" for item in valid_pair.findings)
    )

    intentionally_unused = complementary_usb_netlist(positive_net=None, negative_net=None)
    candidate = next(
        item
        for item in candidates(intentionally_unused)
        if item.rule_id == "bus.complementary_pair_assignment"
    )
    reviewed_unused = evaluate(
        "synthetic-usb",
        coach(intentionally_unused),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=candidate.rule_id,
                    fingerprint=fingerprint(candidate),
                    reason="This approved variant leaves its USB data pair unused",
                ),
            )
        ),
    )
    assert reviewed_unused.status == "PASS"
    assert reviewed_unused.findings[0].disposition == "IGNORED"


@pytest.mark.parametrize(
    "prefix",
    ("", "StdA_", "StdB_"),
    ids=("unsuffixed", "std-a", "std-b"),
)
def test_usb_superspeed_connector_aliases_have_fault_and_control_coverage(prefix: str) -> None:
    rule_id = "bus.complementary_pair_assignment"
    functions = {
        "J1.1": f"{prefix}SSTX+",
        "J1.2": f"{prefix}SSTX−",
        "J1.3": f"{prefix}SSRX+",
        "J1.4": f"{prefix}SSRX−",
    }
    nets = {
        "HOST_TO_PORT_POS": ("J1.1",),
        "HOST_TO_PORT_NEG": ("J1.2",),
        "PORT_TO_HOST_POS": ("J1.3",),
        "PORT_TO_HOST_NEG": ("J1.4",),
    }
    control = NetlistContract(
        components={},
        nets=nets,
        component_symbols={"J1": "Synthetic:UsbSuperSpeedPort"},
        pin_functions=functions,
    )
    assert not any(item.rule_id == rule_id for item in candidates(control))

    fault = control.model_copy(
        update={"nets": {name: pins for name, pins in nets.items() if "J1.4" not in pins}}
    )
    findings = [item for item in candidates(fault) if item.rule_id == rule_id]
    assert len(findings) == 1
    assert findings[0].subject == "J1: USB SuperSpeed RX pair"
    assert findings[0].evidence["positive_pins"] == ("J1.3",)
    assert findings[0].evidence["negative_pins"] == ("J1.4",)
    assert findings[0].evidence["negative_nets"] == ()


@pytest.mark.design_lint_rule(rule_id="bus.complementary_pair_assignment")
@pytest.mark.parametrize(
    ("positive_function", "negative_function", "family"),
    (
        ("CANH", "CANL", "CAN"),
        ("D+", "D-", "USB data"),
        ("TX+", "TX-", "TX"),
        ("RX+", "RX-", "RX"),
        ("TD+", "TD-", "Ethernet TX"),
        ("RD+", "RD-", "Ethernet RX"),
        ("SSTX+", "SSTX-", "USB SuperSpeed TX"),
        ("SSRX+", "SSRX-", "USB SuperSpeed RX"),
    ),
    ids=("can", "usb2", "tx", "rx", "ethernet-tx", "ethernet-rx", "usb-ss-tx", "usb-ss-rx"),
)
def test_builtin_pairs_do_not_require_native_symbol_library_ids(
    positive_function: str,
    negative_function: str,
    family: str,
) -> None:
    rule_id = "bus.complementary_pair_assignment"
    observations = (
        NetlistContract(
            components={},
            nets={"POS": ("U1.1",), "NEG": ("U1.2",)},
            pin_functions={"U1.1": positive_function, "U1.2": negative_function},
        ),
        NetlistContract(
            components={},
            nets={"POS": ("U1.1",), "NEG": ("U1.2",)},
            component_symbols={"U1": "Synthetic:GenericPair"},
            pin_functions={"U1.1": positive_function, "U1.2": negative_function},
        ),
    )

    signatures = []
    for control in observations:
        assert not any(item.rule_id == rule_id for item in candidates(control))

        fault_nets = {"POS": ("U1.1", "U1.2")} if family == "CAN" else {"POS": ("U1.1",)}
        fault = control.model_copy(update={"nets": fault_nets})
        findings = [item for item in candidates(fault) if item.rule_id == rule_id]
        assert len(findings) == 1
        assert findings[0].subject == f"U1: {family} pair"
        assert findings[0].evidence["positive_pins"] == ("U1.1",)
        assert findings[0].evidence["negative_pins"] == ("U1.2",)
        expected_negative_nets = ("POS",) if family == "CAN" else ()
        assert findings[0].evidence["negative_nets"] == expected_negative_nets
        signatures.append((fingerprint(findings[0]), findings[0].message, findings[0].evidence))

    assert signatures[0] == signatures[1]


@pytest.mark.parametrize(
    ("positive_function", "negative_function", "family"),
    (
        ("TD+", "TD-", "Ethernet TX"),
        ("TDP", "TDN", "Ethernet TX"),
        ("RD+", "RD-", "Ethernet RX"),
        ("RDP", "RDN", "Ethernet RX"),
    ),
    ids=("td-symbols", "td-pin-aliases", "rd-symbols", "rd-pin-aliases"),
)
def test_ethernet_media_pair_aliases_have_fault_and_control_coverage(
    positive_function: str,
    negative_function: str,
    family: str,
) -> None:
    rule_id = "bus.complementary_pair_assignment"
    control = NetlistContract(
        components={},
        nets={"NET_A": ("U1.1",), "NET_B": ("U1.2",)},
        component_symbols={"U1": "Synthetic:EthernetPhy"},
        pin_functions={"U1.1": positive_function, "U1.2": negative_function},
    )
    assert not any(item.rule_id == rule_id for item in candidates(control))

    fault = control.model_copy(update={"nets": {"NET_A": ("U1.1",)}})
    findings = [item for item in candidates(fault) if item.rule_id == rule_id]

    assert len(findings) == 1
    assert findings[0].subject == f"U1: {family} pair"
    assert findings[0].evidence["positive_pins"] == ("U1.1",)
    assert findings[0].evidence["negative_pins"] == ("U1.2",)
    assert findings[0].evidence["negative_nets"] == ()


def test_usb_c_lane_indexed_pairs_remain_outside_single_pair_rule() -> None:
    rule_id = "bus.complementary_pair_assignment"
    lane_indexed = NetlistContract(
        components={},
        nets={
            "TX1P": ("J2.1",),
            "TX1N": ("J2.2",),
            "TX2P": ("J2.3",),
            "TX2N": ("J2.4",),
            "RX1P": ("J2.5",),
            "RX1N": ("J2.6",),
            "RX2P": ("J2.7",),
            "RX2N": ("J2.8",),
        },
        component_symbols={"J2": "Synthetic:UsbTypeCPort"},
        pin_functions={
            "J2.1": "TX1+",
            "J2.2": "TX1−",
            "J2.3": "TX2+",
            "J2.4": "TX2−",
            "J2.5": "RX1+",
            "J2.6": "RX1−",
            "J2.7": "RX2+",
            "J2.8": "RX2−",
        },
    )
    assert not any(item.rule_id == rule_id for item in candidates(lane_indexed))


@pytest.mark.parametrize(
    ("positive_function", "negative_function"),
    (("TXP", "TXN"), ("RX+", "RX−")),
    ids=("tx-alias", "rx-alias"),
)
def test_function_names_without_unique_pair_classification_remain_outside_rule(
    positive_function: str,
    negative_function: str,
) -> None:
    paired = NetlistContract(
        components={},
        nets={"POS": ("U2.1",), "NEG": ("U2.2",)},
        component_symbols={"U2": "Synthetic:DifferentialDevice"},
        pin_functions={"U2.1": positive_function, "U2.2": negative_function},
    )
    assert not any(
        item.rule_id == "bus.complementary_pair_assignment" for item in candidates(paired)
    )


def test_project_complementary_aliases_are_symbol_scoped_and_stale_maps_block() -> None:
    rule_id = "bus.complementary_pair_assignment"
    alias = ComplementaryPinFunctionAlias(
        symbol="Vendor:DualOutput",
        family="lane 0",
        positive_functions=("OUTP", "OUT_PLUS"),
        negative_functions=("OUTN", "OUT_MINUS"),
        basis="Synthetic project review maps these exact symbol functions as one pair",
    )
    policy = DesignLintPolicy(
        complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(entries=(alias,))
    )

    def source(*, negative_net: str | None = None, dnp: bool = False) -> NetlistContract:
        nets = {"LANE0_P": ("U1.1",)}
        if negative_net is not None:
            nets[negative_net] = ("U1.2",)
        return NetlistContract(
            components={"U1": ComponentContract(value="Synthetic PHY", footprint="")},
            nets=nets,
            dnp_components=("U1",) if dnp else (),
            component_symbols={"U1": "Vendor:DualOutput"},
            pin_functions={"U1.1": "OUTP", "U1.2": "OUTN"},
            component_pin_numbers={"U1": ("1", "2")},
        )

    fault_source = source()
    fault = evaluate("synthetic-vendor-pair", coach(fault_source), policy)
    finding = next(item for item in fault.findings if item.rule_id == rule_id)
    assert fault.status == "REVIEW"
    assert finding.subject == "U1: lane 0 pair"
    assert finding.evidence["positive_pins"] == ("U1.1",)
    assert finding.evidence["negative_pins"] == ("U1.2",)
    assert finding.evidence["negative_nets"] == ()
    assert finding.evidence["alias_symbol"] == ("Vendor:DualOutput",)
    assert finding.evidence["alias_basis"] == (alias.basis,)
    assert re.search("^[a-f0-9]{64}$", finding.evidence["alias_sha256"][0]) is not None

    baseline = evaluate("synthetic-vendor-pair", coach(fault_source), DesignLintPolicy())
    assert rule_id not in {item.rule_id for item in baseline.findings}

    valid = evaluate("synthetic-vendor-pair", coach(source(negative_net="LANE0_N")), policy)
    assert rule_id not in {item.rule_id for item in valid.findings}
    dnp = evaluate("synthetic-vendor-pair", coach(source(dnp=True)), policy)
    assert rule_id not in {item.rule_id for item in dnp.findings}

    reordered_alias = alias.model_copy(
        update={
            "positive_functions": tuple(reversed(alias.positive_functions)),
            "negative_functions": tuple(reversed(alias.negative_functions)),
        }
    )
    reordered_policy = DesignLintPolicy(
        complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
            entries=(reordered_alias,)
        )
    )
    reordered = evaluate("synthetic-vendor-pair", coach(fault_source), reordered_policy)
    reordered_finding = next(item for item in reordered.findings if item.rule_id == rule_id)
    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        finding.fingerprint,
        finding.evidence,
    )

    changed_basis = alias.model_copy(update={"basis": "Synthetic alternate review record"})
    changed_policy = DesignLintPolicy(
        complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
            entries=(changed_basis,)
        )
    )
    changed = evaluate("synthetic-vendor-pair", coach(fault_source), changed_policy)
    changed_finding = next(item for item in changed.findings if item.rule_id == rule_id)
    assert changed_finding.fingerprint != finding.fingerprint

    stale_alias = alias.model_copy(
        update={
            "positive_functions": ("OLD_POSITIVE",),
            "negative_functions": ("OLD_NEGATIVE",),
        }
    )
    stale = evaluate(
        "synthetic-vendor-pair",
        coach(fault_source),
        DesignLintPolicy(
            complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                entries=(stale_alias,)
            )
        ),
    )
    assert stale.status == "BLOCKED"
    assert any("is stale" in item for item in stale.issues)
    assert any(
        "Refresh the project complementary pin-function alias map" in item
        for item in stale.next_actions
    )

    wrong_symbol = alias.model_copy(update={"symbol": "Vendor:RenamedDevice"})
    exact_identity = evaluate(
        "synthetic-vendor-pair",
        coach(fault_source),
        DesignLintPolicy(
            complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                entries=(wrong_symbol,)
            )
        ),
    )
    assert exact_identity.status == "BLOCKED"
    assert any("no exact native symbol instance" in item for item in exact_identity.issues)

    missing_symbol_identity = fault_source.model_copy(update={"component_symbols": {}})
    unresolved_alias = evaluate(
        "synthetic-vendor-pair",
        coach(missing_symbol_identity),
        policy,
    )
    assert unresolved_alias.status == "BLOCKED"
    assert any("no exact native symbol instance" in item for item in unresolved_alias.issues)

    repeated_builtin = alias.model_copy(
        update={"positive_functions": ("TX+",), "negative_functions": ("TX-",)}
    )
    built_in_collision = evaluate(
        "synthetic-vendor-pair",
        coach(fault_source),
        DesignLintPolicy(
            complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                entries=(repeated_builtin,)
            )
        ),
    )
    assert built_in_collision.status == "BLOCKED"
    assert any("repeats built-in" in item for item in built_in_collision.issues)

    with pytest.raises(ValidationError):
        ComplementaryPinFunctionAlias(
            symbol="Vendor:DualOutput",
            family="ambiguous",
            positive_functions=("OUTP",),
            negative_functions=(" out_p ",),
            basis="Invalid overlapping aliases",
        )


def test_complementary_pair_finding_is_order_stable_and_assignment_clears_it() -> None:
    rule_id = "bus.complementary_pair_assignment"
    source = complementary_usb_netlist(negative_net=None)

    def lint(netlist: NetlistContract) -> tuple[str, DesignLintReport]:
        source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
        return source_hash, evaluate(
            "synthetic-usb", coach(netlist, source_hash), DesignLintPolicy()
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
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
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

    repaired_hash, repaired = lint(complementary_usb_netlist())
    assert source_hash != repaired_hash
    assert rule_id not in {item.rule_id for item in repaired.findings}

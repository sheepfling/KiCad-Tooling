"""Serial peer-reference authored-map and fitted-bond regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import ReferenceBondRequirement
from kicad_tooling.hwrepo.reference_bonds import reference_bond_issues
from kicad_tooling.hwrepo.serial_peer_reference_review import (
    unmapped_serial_peer_reference_reviews,
)
from tests.serial_peer_reference_support import (
    RULE_ID,
    bonded_label_serial_reference_netlist,
    bonded_serial_reference_netlist,
    ferrite_bonded_serial_reference_netlist,
    labelled_serial_peer_map,
    labelled_serial_reference_netlist,
    report,
    serial_connector_peer_map,
    serial_connector_reference_netlist,
    serial_peer_map,
    serial_reference_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


class SerialPeerReferenceMapTests:
    def test_source_matched_separate_header_reference_map_suppresses_prompt(self) -> None:
        source = serial_connector_reference_netlist()
        reviewed = serial_connector_peer_map(
            reference_policy="separate_nets",
            output_reference_net="GND_A",
            input_reference_net="GND_B",
        )
        assert (unmapped_serial_peer_reference_reviews(source, reviewed)) == (())
        assert not (
            any(item.rule_id == RULE_ID for item in report(source, serial_peers=reviewed).findings)
        )

        stale = serial_connector_peer_map(
            reference_policy="common_net",
            output_reference_net="GND",
            input_reference_net="GND",
        )
        assert (len(unmapped_serial_peer_reference_reviews(source, stale))) == (1)

    def test_exact_direct_map_suppresses_reviewed_common_or_separate_references(self) -> None:
        split = serial_reference_netlist()
        split_map = serial_peer_map(
            reference_policy="separate_nets",
            output_reference_net="GND_A",
            input_reference_net="GND_B",
        )
        assert (unmapped_serial_peer_reference_reviews(split, split_map)) == (())
        assert not (
            any(item.rule_id == RULE_ID for item in report(split, serial_peers=split_map).findings)
        )

        common = serial_reference_netlist(output_reference_net="GND", input_reference_net="GND")
        common_map = serial_peer_map(
            reference_policy="common_net", output_reference_net="GND", input_reference_net="GND"
        )
        assert (unmapped_serial_peer_reference_reviews(common, common_map)) == (())

    def test_bonded_reference_map_suppresses_only_when_exact_bond_matches(self) -> None:
        bond = ReferenceBondRequirement(
            reference="R3",
            expected_symbol="Device:R",
            expected_footprint="Synthetic:0603",
            expected_value="0R",
            side_a_pin="R3.1",
            side_b_pin="R3.2",
            side_a_net="GND_A",
            side_b_net="GND_B",
        )
        reviewed = serial_peer_map(
            reference_policy="bonded",
            output_reference_net="GND_A",
            input_reference_net="GND_B",
            reference_bond=bond,
        )
        control = bonded_serial_reference_netlist()
        assert (unmapped_serial_peer_reference_reviews(control, reviewed)) == (())
        assert not (
            any(item.rule_id == RULE_ID for item in report(control, serial_peers=reviewed).findings)
        )

        fault = bonded_serial_reference_netlist(fault=True)
        findings = unmapped_serial_peer_reference_reviews(fault, reviewed)
        assert (len(findings)) == (1)
        assert (findings[0].first_reference_domain.net) == ("GND_A")
        assert (
            next(
                item
                for item in report(fault, serial_peers=reviewed).findings
                if item.rule_id == RULE_ID
            ).subject
        ) == ("U1 / U2: serial reference-domain review")

        label_map = labelled_serial_peer_map(
            reference_policy="bonded",
            first_reference_net="GND_A",
            second_reference_net="GND_B",
            reference_bond=bond,
        )
        assert (
            unmapped_serial_peer_reference_reviews(
                bonded_label_serial_reference_netlist(), label_map
            )
        ) == (())
        labelled_fault = unmapped_serial_peer_reference_reviews(
            bonded_label_serial_reference_netlist(fault=True), label_map
        )
        assert (len(labelled_fault)) == (1)
        assert (len(labelled_fault[0].label_links)) == (1)

    def test_bonded_reference_map_accepts_an_exact_fitted_ferrite(self) -> None:
        bond = ReferenceBondRequirement(
            reference="FB1",
            expected_symbol="Device:FerriteBead",
            expected_footprint="Synthetic:0603Ferrite",
            expected_value="600R @100MHz",
            side_a_pin="FB1.1",
            side_b_pin="FB1.2",
            side_a_net="GND_A",
            side_b_net="GND_B",
        )
        reviewed = serial_peer_map(
            reference_policy="bonded",
            output_reference_net="GND_A",
            input_reference_net="GND_B",
            reference_bond=bond,
        )

        control = ferrite_bonded_serial_reference_netlist()
        assert (reference_bond_issues(control, bond)) == (())
        assert (unmapped_serial_peer_reference_reviews(control, reviewed)) == (())

        fault = ferrite_bonded_serial_reference_netlist(fault=True)
        issues = reference_bond_issues(fault, bond)
        assert (issues) == (("FB1.2 is on FLOATING_GND; expected GND_B",))
        assert (len(unmapped_serial_peer_reference_reviews(fault, reviewed))) == (1)

    def test_stale_reference_map_does_not_suppress_prompt(self) -> None:
        source = serial_reference_netlist()
        stale = serial_peer_map(
            reference_policy="common_net", output_reference_net="GND", input_reference_net="GND"
        )
        assert (len(unmapped_serial_peer_reference_reviews(source, stale))) == (1)

    def test_map_of_supply_pins_does_not_suppress_return_domain_prompt(self) -> None:
        source = serial_reference_netlist()
        wrong_roles = serial_peer_map(
            reference_policy="common_net",
            output_reference_net="+3V3",
            input_reference_net="+3V3",
            output_reference_pin="U1.8",
            input_reference_pin="U2.8",
        )
        assert (len(unmapped_serial_peer_reference_reviews(source, wrong_roles))) == (1)

    def test_reference_domain_finding_is_order_stable_and_exact_map_clears_it(self) -> None:
        source = serial_reference_netlist()
        reordered = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        assert (unmapped_serial_peer_reference_reviews(source)) == (
            unmapped_serial_peer_reference_reviews(reordered)
        )
        assert (report(source).findings) == (report(reordered).findings)
        reviewed = serial_peer_map(
            reference_policy="separate_nets",
            output_reference_net="GND_A",
            input_reference_net="GND_B",
        )
        assert (unmapped_serial_peer_reference_reviews(source, reviewed)) == (())

    def test_exact_channel_label_map_suppresses_but_stale_map_does_not(self) -> None:
        source = labelled_serial_reference_netlist()
        reviewed = labelled_serial_peer_map(
            reference_policy="separate_nets",
            first_reference_net="GND_A",
            second_reference_net="GND_B",
        )
        assert (unmapped_serial_peer_reference_reviews(source, reviewed)) == (())
        assert not (
            any(item.rule_id == RULE_ID for item in report(source, serial_peers=reviewed).findings)
        )

        stale = labelled_serial_peer_map(
            reference_policy="separate_nets",
            first_reference_net="GND_C",
            second_reference_net="GND_D",
        )
        assert (len(unmapped_serial_peer_reference_reviews(source, stale))) == (1)

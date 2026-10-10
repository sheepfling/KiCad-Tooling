"""Component Peers report cases for deterministic synthetic verification."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    NetlistContract,
)
from tests.component_peer_pin_support import (
    peer_bidirectional_netlist,
    peer_component_pin_netlist,
    peer_power_output_netlist,
    peer_signal_input_netlist,
)
from tests.component_peer_power_assignment_support import (
    lint_report as peer_power_pin_assignment_lint_report,
)
from tests.component_peer_power_assignment_support import peer_power_netlist
from tests.design_lint_fixtures import (
    coach,
    generic_component_power_input_netlist,
)


def part_id_peer_component_pin_netlist(
    *, pin_type: str, pin_function: str, pin_nets: tuple[str | None, str | None]
) -> NetlistContract:
    return peer_component_pin_netlist(
        pin_nets=pin_nets,
        symbols={"U1": "Synthetic:ModuleA", "U2": "Synthetic:ModuleB"},
        pin_electrical_types=(pin_type, pin_type),
        pin_function=pin_function,
        part_ids={"U1": "SYNTHETIC-PEER-MODULE", "U2": "synthetic-peer-module"},
    )


def report_cases() -> dict[str, object]:
    return {
        "generic_component_power_input_fault": evaluate(
            "synthetic-generic-component-power-input-hash-seed-fault",
            coach(generic_component_power_input_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "generic_component_power_input_control": evaluate(
            "synthetic-generic-component-power-input-hash-seed-control",
            coach(generic_component_power_input_netlist(connected=True)),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_signal_input_fault": evaluate(
            "synthetic-peer-signal-input-hash-seed-fault",
            coach(peer_signal_input_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_signal_input_control": evaluate(
            "synthetic-peer-signal-input-hash-seed-control",
            coach(peer_signal_input_netlist(input_nets=("SIGNAL_A", "SIGNAL_B"))),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_signal_output_fault": evaluate(
            "synthetic-peer-signal-output-hash-seed-fault",
            coach(
                peer_component_pin_netlist(
                    pin_nets=("SIGNAL_A", None), pin_electrical_types=("output", "output")
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_signal_output_control": evaluate(
            "synthetic-peer-signal-output-hash-seed-control",
            coach(
                peer_component_pin_netlist(
                    pin_nets=("SIGNAL_A", "SIGNAL_B"), pin_electrical_types=("output", "output")
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_signal_output_part_id_fault": evaluate(
            "synthetic-peer-signal-output-part-id-hash-seed-fault",
            coach(
                part_id_peer_component_pin_netlist(
                    pin_type="output", pin_function="OUT", pin_nets=("SIGNAL_A", None)
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_signal_output_part_id_control": evaluate(
            "synthetic-peer-signal-output-part-id-hash-seed-control",
            coach(
                part_id_peer_component_pin_netlist(
                    pin_type="output", pin_function="OUT", pin_nets=("SIGNAL_A", "SIGNAL_B")
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_signal_input_part_id_fault": evaluate(
            "synthetic-peer-signal-input-part-id-hash-seed-fault",
            coach(
                part_id_peer_component_pin_netlist(
                    pin_type="input", pin_function="IN", pin_nets=("SIGNAL_A", None)
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_signal_input_part_id_control": evaluate(
            "synthetic-peer-signal-input-part-id-hash-seed-control",
            coach(
                part_id_peer_component_pin_netlist(
                    pin_type="input", pin_function="IN", pin_nets=("SIGNAL_A", "SIGNAL_B")
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_bidirectional_part_id_fault": evaluate(
            "synthetic-peer-bidirectional-part-id-hash-seed-fault",
            coach(
                part_id_peer_component_pin_netlist(
                    pin_type="bidirectional", pin_function="DATA_IO", pin_nets=("DATA_A", None)
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_bidirectional_part_id_control": evaluate(
            "synthetic-peer-bidirectional-part-id-hash-seed-control",
            coach(
                part_id_peer_component_pin_netlist(
                    pin_type="bidirectional", pin_function="DATA_IO", pin_nets=("DATA_A", "DATA_B")
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_bidirectional_fault": evaluate(
            "synthetic-peer-bidirectional-hash-seed-fault",
            coach(peer_bidirectional_netlist()),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_bidirectional_control": evaluate(
            "synthetic-peer-bidirectional-hash-seed-control",
            coach(peer_bidirectional_netlist(pin_nets=("DATA_IO_A", "DATA_IO_B"))),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_power_output_part_id_fault": evaluate(
            "synthetic-peer-power-output-part-id-hash-seed-fault",
            coach(
                peer_power_output_netlist(
                    symbols={"U1": "Synthetic:PowerModule", "U2": "Synthetic:PowerModuleAlias"},
                    part_ids={
                        "U1": "SYNTHETIC-POWER-MODULE-001",
                        "U2": "synthetic-power-module-001",
                    },
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_power_output_part_id_control": evaluate(
            "synthetic-peer-power-output-part-id-hash-seed-control",
            coach(
                peer_power_output_netlist(
                    output_nets=("VOUT", "VOUT"),
                    symbols={"U1": "Synthetic:PowerModule", "U2": "Synthetic:PowerModuleAlias"},
                    part_ids={
                        "U1": "SYNTHETIC-POWER-MODULE-001",
                        "U2": "synthetic-power-module-001",
                    },
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_power_output_part_id_incomplete_identity": evaluate(
            "synthetic-peer-power-output-part-id-incomplete-identity-hash-seed",
            coach(
                peer_power_output_netlist(
                    symbols={"U1": "Synthetic:PowerModule", "U2": "Synthetic:PowerModuleAlias"},
                    part_ids={
                        "U1": "SYNTHETIC-POWER-MODULE-001",
                        "U2": "synthetic-power-module-001",
                    },
                    values={"U1": "Synthetic module", "U2": "Other module"},
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_power_output_part_id_dedup_fault": evaluate(
            "synthetic-peer-power-output-part-id-dedup-hash-seed-fault",
            coach(
                peer_power_output_netlist(
                    references=("U1", "U2", "U3"),
                    output_nets=("VOUT", None, "VOUT"),
                    symbols={
                        "U1": "Synthetic:PowerModule",
                        "U2": "Synthetic:PowerModule",
                        "U3": "Synthetic:PowerModuleAlias",
                    },
                    part_ids={
                        "U1": "SYNTHETIC-POWER-MODULE-001",
                        "U2": "synthetic-power-module-001",
                        "U3": "Synthetic-Power-Module-001",
                    },
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_power_output_part_id_dedup_control": evaluate(
            "synthetic-peer-power-output-part-id-dedup-hash-seed-control",
            coach(
                peer_power_output_netlist(
                    references=("U1", "U2", "U3"),
                    output_nets=("VOUT", "VOUT_PEER", "VOUT_ALIAS"),
                    symbols={
                        "U1": "Synthetic:PowerModule",
                        "U2": "Synthetic:PowerModule",
                        "U3": "Synthetic:PowerModuleAlias",
                    },
                    part_ids={
                        "U1": "SYNTHETIC-POWER-MODULE-001",
                        "U2": "synthetic-power-module-001",
                        "U3": "Synthetic-Power-Module-001",
                    },
                )
            ),
            DesignLintPolicy(),
        ).model_dump(mode="json"),
        "peer_power_assignment_part_id_fault": peer_power_pin_assignment_lint_report(
            peer_power_netlist(part_ids={"U1": "SYNTHETIC-POWER-001", "U2": "synthetic-power-001"})
        ).model_dump(mode="json"),
        "peer_power_assignment_part_id_control": peer_power_pin_assignment_lint_report(
            peer_power_netlist(
                part_ids={"U1": "SYNTHETIC-POWER-001", "U2": "synthetic-power-001"},
                supply_nets=("+3V3", "+3V3"),
                return_nets=("GND", "GND"),
            )
        ).model_dump(mode="json"),
    }

"""Cross-process determinism checks for source-bound lint reports."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


class DesignLintDeterminismTests(unittest.TestCase):
    def test_high_risk_reports_ignore_python_hash_seed(self) -> None:
        repository = Path(__file__).parents[1]
        probe = Path(__file__).with_name("hashseed_probe.py")
        command = [
            sys.executable,
            "-I",
            "-m",
            "pytest",
            "-q",
            "-s",
            "--override-ini=python_files=hashseed_probe.py",
            str(probe),
        ]
        outputs: list[str] = []
        hash_markers: set[int] = set()
        for _process_index in range(3):
            environment = os.environ.copy()
            environment.pop("PYTHONHASHSEED", None)
            result = subprocess.run(
                command,
                cwd=repository,
                env=environment,
                capture_output=True,
                check=False,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"hash-seed probe failed:\n{result.stdout}\n{result.stderr}",
            )
            payloads = [
                line.removeprefix("DESIGN_LINT_HASHSEED_REPORTS=")
                for line in result.stdout.splitlines()
                if line.startswith("DESIGN_LINT_HASHSEED_REPORTS=")
            ]
            self.assertEqual(len(payloads), 1, result.stdout)
            payload = json.loads(payloads[0])
            self.assertEqual(payload["hash_randomization"], 1)
            hash_markers.add(payload["hash_marker"])
            outputs.append(
                json.dumps(payload["reports"], ensure_ascii=False, separators=(",", ":"))
            )

        self.assertEqual(len(hash_markers), 3, "probe processes did not use distinct hash secrets")
        digests = tuple(hashlib.sha256(output.encode("utf-8")).hexdigest() for output in outputs)
        self.assertEqual(digests[0], digests[1], "full report JSON changed across hash seeds")
        self.assertEqual(digests[1], digests[2], "full report JSON changed across hash seeds")

        reports = json.loads(outputs[0])
        fault = reports["fault"]
        self.assertEqual(fault["status"], "REVIEW")
        self.assertTrue(
            {
                "connector.repeated_pin_function",
                "net.numbered_returns",
            }
            <= {finding["rule_id"] for finding in fault["findings"]}
        )
        self.assertEqual(reports["common_control"]["status"], "PASS")
        self.assertEqual(reports["common_control"]["findings"], [])

        power_input_fault = reports["generic_power_input_fault"]
        self.assertEqual(power_input_fault["status"], "REVIEW")
        self.assertEqual(
            {finding["rule_id"] for finding in power_input_fault["findings"]},
            {"connector.unconnected_power_input"},
        )
        self.assertEqual(
            reports["generic_power_input_control"]["status"],
            "PASS",
        )
        self.assertEqual(reports["generic_power_input_control"]["findings"], [])

        split_common = reports["db9_split_against_common_requirement"]
        split_isolated = reports["db9_split_against_isolated_requirement"]
        common_common = reports["db9_common_against_common_requirement"]
        common_isolated = reports["db9_common_against_isolated_requirement"]
        self.assertEqual(split_common["netlist_sha256"], split_isolated["netlist_sha256"])
        self.assertNotEqual(
            split_common["requirements_sha256"], split_isolated["requirements_sha256"]
        )
        self.assertNotEqual(
            split_common["connectivity_requirements_sha256"],
            split_isolated["connectivity_requirements_sha256"],
        )
        self.assertEqual(common_common["netlist_sha256"], common_isolated["netlist_sha256"])
        self.assertNotEqual(
            common_common["requirements_sha256"], common_isolated["requirements_sha256"]
        )
        self.assertNotEqual(
            common_common["connectivity_requirements_sha256"],
            common_isolated["connectivity_requirements_sha256"],
        )
        grounding_statuses = {
            name: {check["id"]: check["status"] for check in result["checks"]}
            for name, result in (
                ("split_common", split_common),
                ("split_isolated", split_isolated),
                ("common_common", common_common),
                ("common_isolated", common_isolated),
            )
        }
        self.assertEqual(
            grounding_statuses["split_common"],
            {
                "grounding/0V PWM": "FAIL",
                "grounding/return-net-review": "FAIL",
                "grounding/component-coverage": "PASS",
            },
        )
        self.assertEqual(
            grounding_statuses["split_isolated"],
            {
                **{f"grounding/0V PWM {reference}": "PASS" for reference in range(1, 5)},
                "grounding/return-net-review": "PASS",
                "grounding/component-coverage": "PASS",
            },
        )
        self.assertEqual(
            grounding_statuses["common_common"],
            {"grounding/0V PWM": "PASS", "grounding/component-coverage": "PASS"},
        )
        self.assertEqual(
            grounding_statuses["common_isolated"],
            {
                **{f"grounding/0V PWM {reference}": "FAIL" for reference in range(1, 5)},
                "grounding/component-coverage": "PASS",
            },
        )
        pin_connectivity_statuses = {
            name: {check["id"]: check["status"] for check in result["pin_connectivity_checks"]}
            for name, result in (
                ("split_common", split_common),
                ("split_isolated", split_isolated),
                ("common_common", common_common),
                ("common_isolated", common_isolated),
            )
        }
        self.assertEqual(
            pin_connectivity_statuses["split_common"],
            {"pin-connectivity/db9-common-return": "FAIL"},
        )
        self.assertEqual(
            pin_connectivity_statuses["split_isolated"],
            {
                f"pin-connectivity/db9-{reference}-isolated-return": "PASS"
                for reference in range(1, 5)
            },
        )
        self.assertEqual(
            pin_connectivity_statuses["common_common"],
            {"pin-connectivity/db9-common-return": "PASS"},
        )
        self.assertEqual(
            pin_connectivity_statuses["common_isolated"],
            {
                f"pin-connectivity/db9-{reference}-isolated-return": "FAIL"
                for reference in range(1, 5)
            },
        )
        inventory_results = reports["unconnected_pin_inventory"]
        self.assertNotEqual(
            inventory_results["missing_inventory"]["netlist_sha256"],
            inventory_results["complete_inventory_control"]["netlist_sha256"],
        )
        self.assertEqual(inventory_results["missing_inventory"]["checks"][0]["status"], "FAIL")
        self.assertIn(
            "missing symbol pin inventory=['J1']",
            inventory_results["missing_inventory"]["checks"][0]["detail"],
        )
        self.assertEqual(
            inventory_results["complete_inventory_control"]["checks"][0]["status"],
            "PASS",
        )

        diode_fault = reports["diode_fault"]
        self.assertEqual(diode_fault["status"], "REVIEW")
        self.assertIn(
            "component.two_pin_diode_same_net",
            {finding["rule_id"] for finding in diode_fault["findings"]},
        )
        self.assertEqual(reports["diode_control"]["status"], "PASS")
        self.assertEqual(reports["diode_control"]["findings"], [])
        crystal_fault = reports["crystal_fault"]
        self.assertEqual(crystal_fault["status"], "REVIEW")
        self.assertEqual(
            sum(
                finding["rule_id"] == "component.two_pin_crystal_same_net"
                for finding in crystal_fault["findings"]
            ),
            2,
        )
        self.assertEqual(reports["crystal_control"]["status"], "PASS")
        self.assertEqual(reports["crystal_control"]["findings"], [])
        fuse_fault = reports["fuse_fault"]
        self.assertEqual(fuse_fault["status"], "REVIEW")
        self.assertIn(
            "component.two_pin_fuse_same_net",
            {finding["rule_id"] for finding in fuse_fault["findings"]},
        )
        self.assertEqual(reports["fuse_control"]["status"], "PASS")
        self.assertEqual(reports["fuse_control"]["findings"], [])
        ferrite_fault = reports["ferrite_fault"]
        self.assertEqual(ferrite_fault["status"], "REVIEW")
        self.assertEqual(
            sum(
                finding["rule_id"] == "component.two_pin_ferrite_same_net"
                for finding in ferrite_fault["findings"]
            ),
            2,
        )
        self.assertEqual(reports["ferrite_control"]["status"], "PASS")
        self.assertEqual(reports["ferrite_control"]["findings"], [])
        for report_name in (
            "led_output_direct_fault",
            "led_output_parallel_resistor_fault",
        ):
            led_fault = reports[report_name]
            self.assertEqual(led_fault["status"], "REVIEW")
            self.assertIn(
                "component.led_directly_driven_from_output",
                {finding["rule_id"] for finding in led_fault["findings"]},
            )
        led_series = reports["led_output_series_control"]
        self.assertEqual(led_series["status"], "REVIEW")
        led_series_rule_ids = {finding["rule_id"] for finding in led_series["findings"]}
        self.assertNotIn("component.led_directly_driven_from_output", led_series_rule_ids)
        self.assertEqual(led_series_rule_ids, {"net.return_labels_without_pin_roles"})
        peer_pin_fault = reports["peer_pin_fault"]
        self.assertEqual(peer_pin_fault["status"], "REVIEW")
        self.assertIn(
            "connector.peer_pin_assignment_outlier",
            {finding["rule_id"] for finding in peer_pin_fault["findings"]},
        )
        self.assertEqual(reports["peer_pin_control"]["status"], "PASS")
        self.assertEqual(reports["peer_pin_control"]["findings"], [])
        for peer_report, expected_outliers, expected_common, expected_open in (
            (peer_pin_fault, 1, 1, 1),
            (reports["peer_pin_control"], 0, 2, 0),
        ):
            peer_coverage = peer_report["connector_peer_pin_coverage"]
            self.assertEqual(peer_coverage["status"], "EVALUATED")
            self.assertEqual(peer_coverage["netlist_sha256"], peer_report["netlist_sha256"])
            self.assertEqual(peer_coverage["connector_candidate_count"], 3)
            self.assertEqual(peer_coverage["exact_symbol_peer_group_count"], 1)
            self.assertEqual(peer_coverage["exact_symbol_pin_group_count"], 2)
            self.assertEqual(
                peer_coverage["exact_symbol_pin_groups_with_common_assignment_count"],
                expected_common,
            )
            self.assertEqual(
                peer_coverage["exact_symbol_pin_groups_with_open_assignment_count"],
                expected_open,
            )
            self.assertEqual(peer_coverage["peer_pin_outlier_finding_count"], expected_outliers)

        separate_peer_scopes = reports["connector_peer_scope_separate"]
        separate_peer_rule_ids = {
            finding["rule_id"] for finding in separate_peer_scopes["findings"]
        }
        self.assertIn("connector.repeated_pin_function", separate_peer_rule_ids)
        self.assertNotIn("connector.peer_pin_assignment_divergence", separate_peer_rule_ids)
        shared_peer_scopes = reports["connector_peer_scope_shared"]
        shared_peer_divergences = [
            finding
            for finding in shared_peer_scopes["findings"]
            if finding["rule_id"] == "connector.peer_pin_assignment_divergence"
        ]
        self.assertEqual(len(shared_peer_divergences), 2)
        self.assertTrue(
            all(
                finding["evidence"]["peer_assignment_group"] == ["uart-ports"]
                and len(finding["evidence"]["peer_assignment_basis"]) == 2
                for finding in shared_peer_divergences
            )
        )

        unlisted_separate = reports["unlisted_peer_scope_separate_fault"]
        unlisted_separate_findings = {
            finding["rule_id"]: finding for finding in unlisted_separate["findings"]
        }
        self.assertEqual(unlisted_separate["status"], "REVIEW")
        self.assertEqual(set(unlisted_separate_findings), {"connector.repeated_pin_function"})
        self.assertEqual(
            {
                pin: unlisted_separate_findings["connector.repeated_pin_function"]["evidence"][pin]
                for pin in ("J1.2", "J2.2", "J3.2")
            },
            {
                "J1.2": ["RETURN_A"],
                "J2.2": ["RETURN_B"],
                "J3.2": ["RETURN_C"],
            },
        )
        unlisted_shared = reports["unlisted_peer_scope_shared_fault"]
        unlisted_shared_findings = {
            finding["rule_id"]: finding for finding in unlisted_shared["findings"]
        }
        self.assertEqual(unlisted_shared["status"], "REVIEW")
        self.assertEqual(
            set(unlisted_shared_findings),
            {"connector.repeated_pin_function", "connector.peer_pin_assignment_divergence"},
        )
        unlisted_divergence = unlisted_shared_findings["connector.peer_pin_assignment_divergence"]
        self.assertEqual(unlisted_divergence["evidence"]["peer_assignment_group"], ["uart-peers"])
        self.assertEqual(len(unlisted_divergence["evidence"]["peer_assignment_basis"]), 3)
        self.assertEqual(reports["unlisted_peer_scope_shared_control"]["status"], "PASS")
        self.assertEqual(reports["unlisted_peer_scope_shared_control"]["findings"], [])

        mapped_return_fault = reports["mapped_return_fault"]
        self.assertEqual(mapped_return_fault["status"], "REVIEW")
        mapped_return_findings = {
            finding["rule_id"]: finding for finding in mapped_return_fault["findings"]
        }
        self.assertIn("connector.repeated_pin_function", mapped_return_findings)
        self.assertEqual(
            mapped_return_findings["connector.repeated_pin_function"]["evidence"][
                "role_classification_sources"
            ],
            [
                "J1.3: project interface catalog role=return; native symbol function=GND",
                "J2.3: project interface catalog role=return; native symbol function=Pin_3",
            ],
        )
        self.assertEqual(reports["mapped_return_control"]["status"], "PASS")
        self.assertEqual(reports["mapped_return_control"]["findings"], [])

        mapped_supply_fault = reports["mapped_supply_open_peer_fault"]
        self.assertEqual(mapped_supply_fault["status"], "REVIEW")
        self.assertEqual(mapped_supply_fault["connector_coverage"]["status"], "COMPLETE")
        mapped_supply_finding = next(
            finding
            for finding in mapped_supply_fault["findings"]
            if finding["rule_id"] == "connector.repeated_pin_function"
        )
        self.assertEqual(mapped_supply_finding["evidence"]["J2.5"], [])
        self.assertEqual(
            mapped_supply_finding["evidence"]["reviewed_voltage_domain"], ["external-5v"]
        )
        self.assertEqual(
            {finding["rule_id"] for finding in mapped_supply_fault["findings"]},
            {"connector.repeated_pin_function"},
            "the role-aware peer finding reports the open contact without a duplicate prompt",
        )
        self.assertEqual(reports["mapped_supply_common_control"]["status"], "PASS")
        self.assertEqual(reports["mapped_supply_common_control"]["findings"], [])

        contact_rating_fault = reports["connector_contact_rating_over_limit"]
        contact_rating_control = reports["connector_contact_rating_boundary_control"]
        self.assertEqual(
            contact_rating_fault["netlist_sha256"], contact_rating_control["netlist_sha256"]
        )
        self.assertNotEqual(
            contact_rating_fault["requirements_sha256"],
            contact_rating_control["requirements_sha256"],
        )
        fault_checks = {
            check["id"].rsplit("/", maxsplit=1)[-1]: check
            for check in contact_rating_fault["checks"]
        }
        control_checks = {
            check["id"].rsplit("/", maxsplit=1)[-1]: check
            for check in contact_rating_control["checks"]
        }
        self.assertEqual(fault_checks["identity"]["status"], "PASS")
        self.assertEqual(fault_checks["assignment"]["status"], "PASS")
        self.assertEqual(fault_checks["utilization"]["status"], "FAIL")
        self.assertAlmostEqual(fault_checks["utilization"]["observed"], 0.805)
        self.assertEqual(control_checks["utilization"]["status"], "PASS")
        self.assertAlmostEqual(control_checks["utilization"]["observed"], 0.8)

        mosfet_fault = reports["mosfet_stress_q2_over_limit"]
        mosfet_control = reports["mosfet_stress_multi_device_control"]
        self.assertEqual(mosfet_fault["netlist_sha256"], mosfet_control["netlist_sha256"])
        self.assertNotEqual(
            mosfet_fault["requirements_sha256"], mosfet_control["requirements_sha256"]
        )
        mosfet_fault_statuses = {check["id"]: check["status"] for check in mosfet_fault["checks"]}
        mosfet_control_statuses = {
            check["id"]: check["status"] for check in mosfet_control["checks"]
        }
        self.assertEqual(
            {
                check_id
                for check_id, status in mosfet_fault_statuses.items()
                if status != mosfet_control_statuses[check_id]
            },
            {"mosfet-stress/switch-q2/state-on/vds"},
            "the authored Q2 drain envelope changes only Q2 on-state VDS coverage",
        )
        self.assertEqual(mosfet_fault_statuses["mosfet-stress/switch-q2/state-on/vds"], "FAIL")
        self.assertEqual(mosfet_fault_statuses["mosfet-stress/switch-q1/state-on/vds"], "PASS")
        self.assertTrue(all(status == "PASS" for status in mosfet_control_statuses.values()))

        partial_peer_map = reports["partial_mapped_peer_pin_fault"]
        self.assertEqual(partial_peer_map["status"], "REVIEW")
        self.assertEqual(partial_peer_map["connector_coverage"]["status"], "UNDECLARED")
        self.assertEqual(
            next(
                entry["status"]
                for entry in partial_peer_map["connector_coverage"]["entries"]
                if entry["reference"] == "J3"
            ),
            "UNDECLARED",
        )
        partial_peer_findings = {
            finding["rule_id"]: finding for finding in partial_peer_map["findings"]
        }
        self.assertIn("connector.repeated_pin_function", partial_peer_findings)
        generic_peer_finding = partial_peer_findings["connector.peer_pin_assignment_outlier"]
        self.assertEqual(generic_peer_finding["evidence"]["outlier_pins"], ["J2.1"])
        self.assertEqual(generic_peer_finding["evidence"]["J3.1"], ["SUPPLY_A"])

        complete_peer_map = reports["complete_mapped_peer_pin_control"]
        self.assertEqual(complete_peer_map["connector_coverage"]["status"], "COMPLETE")
        complete_peer_rule_ids = {finding["rule_id"] for finding in complete_peer_map["findings"]}
        self.assertIn("connector.repeated_pin_function", complete_peer_rule_ids)
        self.assertNotIn(
            "connector.peer_pin_assignment_outlier",
            complete_peer_rule_ids,
            "complete role coverage may replace the overlapping generic peer warning",
        )
        self.assertEqual(reports["common_peer_pin_control"]["status"], "PASS")
        self.assertEqual(reports["common_peer_pin_control"]["findings"], [])

        decoupling_fault = reports["pcb_decoupling_distance_fault"]
        self.assertEqual(decoupling_fault["status"], "REVIEW")
        self.assertEqual(decoupling_fault["pcb_decoupling"]["status"], "INCOMPLETE")
        self.assertIn(
            "pcb.decoupling_proximity",
            {finding["rule_id"] for finding in decoupling_fault["findings"]},
        )
        self.assertEqual(
            decoupling_fault["pcb_decoupling"]["entries"][0]["candidates"][0]["distance_nm"],
            100_001,
        )
        decoupling_control = reports["pcb_decoupling_distance_control"]
        self.assertEqual(decoupling_control["status"], "PASS")
        self.assertEqual(decoupling_control["pcb_decoupling"]["status"], "COMPLETE")
        self.assertNotIn(
            "pcb.decoupling_proximity",
            {finding["rule_id"] for finding in decoupling_control["findings"]},
        )
        fault_decoupling_coverage = decoupling_fault["pcb_decoupling"]
        control_decoupling_coverage = decoupling_control["pcb_decoupling"]
        self.assertEqual(
            fault_decoupling_coverage["map_sha256"], control_decoupling_coverage["map_sha256"]
        )
        self.assertNotEqual(
            fault_decoupling_coverage["snapshot_sha256"],
            control_decoupling_coverage["snapshot_sha256"],
        )

        mapped_power_path_fault = reports["mapped_power_path_fault"]
        self.assertEqual(mapped_power_path_fault["status"], "REVIEW")
        self.assertIn(
            "power.mapped_series_path_mismatch",
            {finding["rule_id"] for finding in mapped_power_path_fault["findings"]},
        )
        power_path_run = next(
            run
            for run in mapped_power_path_fault["mapped_check_runs"]
            if run["rule_id"] == "power.mapped_series_path_mismatch"
        )
        self.assertEqual(power_path_run["status"], "EVALUATED")
        self.assertEqual(power_path_run["requirement_count"], 1)
        self.assertEqual(power_path_run["finding_count"], 1)
        self.assertEqual(reports["mapped_power_path_control"]["status"], "PASS")
        self.assertEqual(reports["mapped_power_path_control"]["findings"], [])

        power_sequence_fault = reports["mapped_power_sequence_fault"]
        self.assertEqual(power_sequence_fault["status"], "REVIEW")
        self.assertIn(
            "power.mapped_sequence_dependency_mismatch",
            {finding["rule_id"] for finding in power_sequence_fault["findings"]},
        )
        sequence_run = next(
            run
            for run in power_sequence_fault["mapped_check_runs"]
            if run["rule_id"] == "power.mapped_sequence_dependency_mismatch"
        )
        self.assertEqual(sequence_run["status"], "EVALUATED")
        self.assertEqual(sequence_run["requirement_count"], 3)
        self.assertEqual(sequence_run["finding_count"], 1)
        self.assertEqual(reports["mapped_power_sequence_control"]["status"], "PASS")
        self.assertEqual(reports["mapped_power_sequence_control"]["findings"], [])

        serial_label_fault = reports["serial_label_unmapped"]
        self.assertEqual(serial_label_fault["status"], "REVIEW")
        serial_label_findings = {
            finding["rule_id"]: finding for finding in serial_label_fault["findings"]
        }
        self.assertIn("bus.serial_unmapped_peer", serial_label_findings)
        self.assertEqual(
            serial_label_findings["bus.serial_unmapped_peer"]["evidence"]["discovery_basis"],
            ["net_label"],
        )
        serial_label_mapped_control = reports["serial_label_mapped_control"]
        self.assertEqual(serial_label_mapped_control["status"], "REVIEW")
        self.assertEqual(
            [finding["rule_id"] for finding in serial_label_mapped_control["findings"]],
            ["connector.no_connected_return"],
            "the exact serial map clears its candidate but must preserve independent pin-role review",
        )

        serial_reference_fault = reports["serial_reference_fault"]
        self.assertEqual(serial_reference_fault["status"], "REVIEW")
        serial_reference_findings = [
            finding
            for finding in serial_reference_fault["findings"]
            if finding["rule_id"] == "bus.serial_peer_reference_review"
        ]
        self.assertEqual(len(serial_reference_findings), 1)
        self.assertEqual(
            serial_reference_findings[0]["subject"],
            "J1 / U1: serial reference-domain review",
        )
        serial_reference_control = reports["serial_reference_control"]
        self.assertNotIn(
            "bus.serial_peer_reference_review",
            {finding["rule_id"] for finding in serial_reference_control["findings"]},
            "the all-common UART control must clear this heuristic without erasing other review",
        )
        serial_bond_fault = reports["serial_reference_bond_fault"]
        serial_bond_control = reports["serial_reference_bond_control"]
        fault_reference_check = next(
            item for item in serial_bond_fault if item["id"] == "serial/console-link/reference"
        )
        control_reference_check = next(
            item for item in serial_bond_control if item["id"] == "serial/console-link/reference"
        )
        self.assertEqual(fault_reference_check["status"], "FAIL")
        self.assertIn("R3.2 is on FLOATING_GND", fault_reference_check["detail"])
        self.assertEqual(control_reference_check["status"], "PASS")

        serial_label_reference_fault = reports["serial_label_reference_fault"]
        serial_label_reference_findings = tuple(
            finding
            for finding in serial_label_reference_fault["findings"]
            if finding["rule_id"] == "bus.serial_peer_reference_review"
        )
        self.assertEqual(len(serial_label_reference_findings), 1)
        self.assertEqual(
            serial_label_reference_findings[0]["evidence"]["discovery_basis"], ["net_label"]
        )
        self.assertNotIn(
            "bus.serial_peer_reference_review",
            {
                finding["rule_id"]
                for finding in reports["serial_label_reference_control"]["findings"]
            },
        )

        spi_voltage_review = reports["spi_peer_voltage_unmapped"]
        self.assertEqual(spi_voltage_review["status"], "REVIEW")
        self.assertIn(
            "bus.spi_peer_voltage_review",
            {finding["rule_id"] for finding in spi_voltage_review["findings"]},
        )
        spi_voltage_control = reports["spi_peer_voltage_mapped_control"]
        self.assertNotIn(
            "bus.spi_peer_voltage_review",
            {finding["rule_id"] for finding in spi_voltage_control["findings"]},
            "the exact complete voltage map must suppress only the SPI voltage prompt",
        )

        serial_voltage_review = reports["serial_peer_voltage_unmapped"]
        self.assertEqual(serial_voltage_review["status"], "REVIEW")
        self.assertIn(
            "bus.serial_peer_voltage_review",
            {finding["rule_id"] for finding in serial_voltage_review["findings"]},
        )
        serial_voltage_control = reports["serial_peer_voltage_mapped_control"]
        self.assertNotIn(
            "bus.serial_peer_voltage_review",
            {finding["rule_id"] for finding in serial_voltage_control["findings"]},
            "the exact complete voltage map must suppress only the UART voltage prompt",
        )

        can_fault = reports["can_peer_fault"]
        self.assertEqual(can_fault["status"], "REVIEW")
        self.assertIn(
            "bus.can_peer_assignment_divergence",
            {finding["rule_id"] for finding in can_fault["findings"]},
        )
        can_control = reports["can_peer_control"]
        self.assertNotIn(
            "bus.can_peer_assignment_divergence",
            {finding["rule_id"] for finding in can_control["findings"]},
        )
        self.assertNotEqual(
            can_fault["netlist_sha256"],
            can_control["netlist_sha256"],
            "fault and control reports must bind their distinct typed-netlist inputs",
        )

        usb_path_fault = reports["usb_data_path_series_fault"]
        usb_path_control = reports["usb_data_path_series_control"]
        usb_direct_control = reports["usb_data_path_direct_topology_control"]
        usb_path_fault_ids = {item["rule_id"] for item in usb_path_fault["findings"]}
        self.assertEqual(usb_path_fault["status"], "REVIEW")
        self.assertEqual(usb_path_fault_ids, {"bus.usb_data_path_mismatch"})
        usb_path_finding = usb_path_fault["findings"][0]
        self.assertEqual(usb_path_finding["subject"], "usb-port-1: USB D+ path")
        self.assertIn("R1 is absent", usb_path_finding["evidence"]["issues"][0])
        usb_path_run = next(
            item
            for item in usb_path_fault["mapped_check_runs"]
            if item["rule_id"] == "bus.usb_data_path_mismatch"
        )
        usb_control_run = next(
            item
            for item in usb_path_control["mapped_check_runs"]
            if item["rule_id"] == "bus.usb_data_path_mismatch"
        )
        self.assertEqual(usb_path_run["status"], "EVALUATED")
        self.assertEqual(usb_path_run["requirement_count"], 1)
        self.assertEqual(usb_path_run["finding_count"], 1)
        self.assertEqual(usb_control_run["status"], "EVALUATED")
        self.assertEqual(usb_control_run["finding_count"], 0)
        self.assertEqual(usb_path_run["map_sha256"], usb_control_run["map_sha256"])
        self.assertNotEqual(usb_path_fault["netlist_sha256"], usb_path_control["netlist_sha256"])
        self.assertEqual(usb_path_control["status"], "PASS")
        self.assertEqual(usb_path_control["findings"], [])
        self.assertEqual(usb_direct_control["status"], "REVIEW")
        self.assertEqual(
            {item["rule_id"] for item in usb_direct_control["findings"]},
            {"mcu.stm32_cubemx_pin_map", "signal.named_pair_without_reviewed_requirement"},
            "the USB path map must preserve independent firmware-map and PCB-pair review prompts",
        )
        self.assertNotIn(
            "bus.usb_data_path_mismatch",
            {item["rule_id"] for item in usb_direct_control["findings"]},
        )

        usb_bond_fault = reports["usb_reference_bond_fault"]
        self.assertEqual(usb_bond_fault["status"], "REVIEW")
        self.assertEqual(
            {item["rule_id"] for item in usb_bond_fault["findings"]},
            {"bus.usb_data_path_mismatch"},
        )
        bond_finding = usb_bond_fault["findings"][0]
        self.assertEqual(bond_finding["subject"], "usb-port-1: USB reference path")
        self.assertTrue(
            any("R3.2 is on FLOATING_GND" in issue for issue in bond_finding["evidence"]["issues"])
        )
        self.assertEqual(reports["usb_reference_bond_control"]["status"], "PASS")
        self.assertEqual(reports["usb_reference_bond_control"]["findings"], [])

        usb_multiport_fault = reports["usb_multiport_peer_fault"]
        usb_fault_coverage = usb_multiport_fault["usb_peer_reference_coverage"]
        self.assertEqual(usb_fault_coverage["status"], "EVALUATED")
        self.assertEqual(usb_fault_coverage["recognized_connector_group_count"], 2)
        self.assertEqual(usb_fault_coverage["supported_connector_group_count"], 2)
        self.assertEqual(usb_fault_coverage["recognized_phy_group_count"], 2)
        self.assertEqual(usb_fault_coverage["supported_phy_group_count"], 2)
        self.assertEqual(usb_fault_coverage["supported_data_path_count"], 2)
        self.assertEqual(usb_fault_coverage["separate_reference_path_count"], 2)
        self.assertEqual(usb_fault_coverage["candidate_group_count"], 2)
        multiport_findings = tuple(
            finding
            for finding in usb_multiport_fault["findings"]
            if finding["rule_id"] == "bus.usb_peer_reference_review"
        )
        self.assertEqual(
            tuple(
                (finding["subject"], finding["evidence"]["USB_port_group"])
                for finding in multiport_findings
            ),
            (
                ("J1 / U1: USB reference-domain review (port 1)", ["1"]),
                ("J2 / U1: USB reference-domain review (port 2)", ["2"]),
            ),
        )
        self.assertNotIn(
            "bus.usb_peer_reference_review",
            {finding["rule_id"] for finding in reports["usb_multiport_peer_control"]["findings"]},
        )
        usb_control_coverage = reports["usb_multiport_peer_control"]["usb_peer_reference_coverage"]
        self.assertEqual(usb_control_coverage["common_reference_path_count"], 2)
        self.assertEqual(usb_control_coverage["separate_reference_path_count"], 0)
        self.assertEqual(usb_control_coverage["candidate_group_count"], 0)

        header_boundary = reports["header_only_spi_uart_boundary"]
        self.assertEqual(
            {
                item["rule_id"]: (
                    item["status"],
                    item["recognized_endpoint_count"],
                    item["direct_peer_link_count"],
                    item["voltage_comparison_count"],
                    item["candidate_group_count"],
                )
                for item in header_boundary["digital_peer_voltage_coverage"]
            },
            {
                "bus.spi_peer_voltage_review": ("NO_SUPPORTED_ENDPOINTS", 0, 0, 0, 0),
                "bus.serial_peer_voltage_review": ("NO_SUPPORTED_ENDPOINTS", 0, 0, 0, 0),
            },
        )
        self.assertFalse(
            {
                "bus.spi_peer_voltage_review",
                "bus.serial_peer_voltage_review",
            }
            & {finding["rule_id"] for finding in header_boundary["findings"]}
        )

        stm32_fault = reports["stm32_pin_map_fault"]
        self.assertEqual(stm32_fault["status"], "REVIEW")
        self.assertEqual(
            {finding["rule_id"] for finding in stm32_fault["findings"]},
            {"mcu.stm32_cubemx_pin_map"},
        )
        stm32_fault_coverage = stm32_fault["stm32_pin_map_coverage"]
        stm32_control = reports["stm32_pin_map_control"]
        self.assertEqual(stm32_control["status"], "PASS")
        self.assertEqual(stm32_control["findings"], [])
        stm32_control_coverage = stm32_control["stm32_pin_map_coverage"]
        self.assertEqual(stm32_fault_coverage["status"], "COMPLETE")
        self.assertEqual(stm32_fault_coverage["mapped_pin_count"], 3)
        self.assertEqual(stm32_fault_coverage["excluded_pin_count"], 1)
        self.assertEqual(stm32_fault_coverage["map_sha256"], stm32_control_coverage["map_sha256"])
        self.assertNotEqual(
            stm32_fault_coverage["ioc_source_hashes"]["firmware/controller.ioc"],
            stm32_control_coverage["ioc_source_hashes"]["firmware/controller.ioc"],
        )
        self.assertEqual(
            stm32_fault["source_hashes"]["firmware/controller.ioc"],
            stm32_fault_coverage["ioc_source_hashes"]["firmware/controller.ioc"],
        )
        self.assertEqual(
            stm32_control["source_hashes"]["firmware/controller.ioc"],
            stm32_control_coverage["ioc_source_hashes"]["firmware/controller.ioc"],
        )
        stm32_finding_evidence = stm32_fault["findings"][0]["evidence"]
        self.assertEqual(
            stm32_finding_evidence["ioc_sha256"],
            [stm32_fault_coverage["ioc_source_hashes"]["firmware/controller.ioc"]],
        )
        self.assertEqual(stm32_finding_evidence["map_sha256"], [stm32_fault_coverage["map_sha256"]])

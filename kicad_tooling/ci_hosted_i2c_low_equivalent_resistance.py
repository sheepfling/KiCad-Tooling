"""Hosted native regressions for low equivalent I2C pull-up resistance."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .ci_hosted_support import HostedLog
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.design_lint import evaluate
from .hwrepo.i2c_pullup_heuristics import i2c_buses_with_low_equivalent_pullup_resistance
from .hwrepo.models import DesignLintPolicy
from .hwrepo.netlist_contract_models import NetlistContract


def check_i2c_low_equivalent_native_cases(
    *,
    project: str,
    kicad_version: str,
    image: str,
    source_hashes: Mapping[str, str],
    raw_hashes: Mapping[tuple[str, str], str],
    normalized_hashes: Mapping[tuple[str, str], str],
    observations: Mapping[tuple[str, str], NetlistContract],
    command_receipt: Path,
    root: Path,
    log: HostedLog,
) -> None:
    """Require native fault/control exports to preserve the low-resistance predicate."""

    for case, expected_value, expected_equivalent in (
        ("low_resistance_control", "2,0k", 1_000.0),
        ("low_resistance_fault", "1,5k", 750.0),
    ):
        observed = observations[(case, "first")]
        expected_net_members = {
            "I2C_SDA": {"R1.2", "R2.2", "U1.1"},
            "+3V3": {"R1.1", "R2.1"},
        }
        if any(
            observed.components.get(reference) is None
            or observed.components[reference].value != expected_value
            or observed.component_symbols.get(reference) != "Device:R"
            or set(observed.component_pin_numbers.get(reference, ())) != {"1", "2"}
            for reference in ("R1", "R2")
        ) or any(
            not members <= set(observed.nets.get(net, ()))
            for net, members in expected_net_members.items()
        ):
            raise ValueError(f"Native I2C {case} lost the exact resistor or net assignments")

        resistance_observations = i2c_buses_with_low_equivalent_pullup_resistance(observed)
        project_id = f"synthetic-i2c-{case}"
        report = evaluate(
            project_id,
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, "first")],
            ),
            DesignLintPolicy(),
        )
        findings = tuple(
            item for item in report.findings if item.rule_id == "bus.i2c_low_equivalent_resistance"
        )
        if case == "low_resistance_fault":
            if (
                len(resistance_observations) != 1
                or len(resistance_observations[0].lines) != 1
                or resistance_observations[0].lines[0].line != "SDA"
                or resistance_observations[0].lines[0].equivalent_resistance_ohms
                != expected_equivalent
                or len(findings) != 1
                or findings[0].evidence["equivalent_ohms"] != ("SDA=750Ω",)
                or findings[0].evidence["pullup_resistors"]
                != ("R1=1500Ω to +3V3", "R2=1500Ω to +3V3")
            ):
                raise ValueError("Native I2C low-resistance fault did not produce the exact REVIEW")
            rule_findings = "bus.i2c_low_equivalent_resistance"
            equivalent_ohms = "SDA=750Ω"
            pullup_resistors = "R1=1500Ω to +3V3,R2=1500Ω to +3V3"
        else:
            if resistance_observations or findings:
                raise ValueError(
                    "Native I2C exact 1 kΩ boundary control unexpectedly produced a finding"
                )
            rule_findings = "none"
            equivalent_ohms = "1000Ω"
            pullup_resistors = "R1=2000Ω to +3V3,R2=2000Ω to +3V3"

        first_hash = normalized_hashes[(case, "first")]
        repeat_hash = normalized_hashes[(case, "repeat")]
        if first_hash != repeat_hash:
            raise ValueError(f"Native I2C {case} exports differ after typed normalization")
        log.event(
            f"i2c-pullup-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=kicad_version,
            image=image,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=first_hash,
            repeat_normalized_netlist_sha256=repeat_hash,
            equivalent_ohms=equivalent_ohms,
            pullup_resistors=pullup_resistors,
            rule_findings=rule_findings,
            repeatable="true",
            command_receipt=command_receipt.relative_to(root).as_posix(),
        )

"""Read-only electrical setup and exact simulator readiness checks."""

from __future__ import annotations

from pathlib import Path

from .contract_coach import run_command
from .electrical import load_analysis, policy_issues, selected_config, simulation_cases
from .models import EnvironmentCheck
from .spice import executable_path, observed_versions


def electrical_checks(
    root: Path, project_id: str | None, ngspice: str
) -> tuple[EnvironmentCheck, ...]:
    if project_id is None:
        return (
            EnvironmentCheck(
                id="electrical-target",
                required=True,
                status="FAIL",
                expected="Registered project ID",
                next_action="Run doctor --electrical --project-id <id> for the board you intend to analyze.",
            ),
        )
    try:
        config = selected_config(root, project_id)
        contract = load_analysis(root, config)
        if contract is None:
            return (
                EnvironmentCheck(
                    id="electrical-contract",
                    required=True,
                    status="FAIL",
                    expected="Reviewed electrical contract",
                    observed="NOT_CONFIGURED",
                    next_action=f"Run python -B -m kicad_tooling.electrical --project {project_id} --init, then complete its pending requirements.",
                ),
            )
        issues = policy_issues(root, config)
        checks = [
            EnvironmentCheck(
                id="electrical-contract",
                required=True,
                status="FAIL" if issues else "PASS",
                expected="Complete requirements, current model bindings and passing power budgets",
                observed="; ".join(issues)
                if issues
                else "Ready for analysis; no simulation has run",
                next_action="Review the named requirement or binding using docs/workflow/ELECTRICAL_ANALYSIS.md."
                if issues
                else "Requirements are configured; run the electrical verification depth.",
            )
        ]
        needs_simulator = bool(simulation_cases(contract)) or any(
            section.mode == "pending" for section in (contract.power, contract.high_frequency)
        )
        if not needs_simulator:
            checks.append(
                EnvironmentCheck(
                    id="ngspice",
                    required=False,
                    status="PASS",
                    expected="No simulator needed for this contract",
                    observed="NOT_REQUIRED",
                    next_action="The declared scope needs no SPICE run.",
                )
            )
        elif contract.ngspice_version == "UNREVIEWED":
            checks.append(
                EnvironmentCheck(
                    id="ngspice",
                    required=True,
                    status="FAIL",
                    expected="Engineer-selected exact ngspice version",
                    observed="UNREVIEWED",
                    next_action="Choose and install an approved ngspice version, set ngspice_version in the contract, then rerun doctor.",
                )
            )
        else:
            command = run_command(
                root.resolve(), (executable_path(ngspice), "--version"), timeout=30
            )
            versions = observed_versions(command)
            success = (
                command.returncode == 0
                and command.error is None
                and contract.ngspice_version in versions
            )
            checks.append(
                EnvironmentCheck(
                    id="ngspice",
                    required=True,
                    status="PASS" if success else "FAIL",
                    expected=f"Exact ngspice {contract.ngspice_version}",
                    observed=", ".join(versions)
                    or command.error
                    or command.stderr.strip()
                    or "No version banner",
                    next_action="Simulator is ready; doctor has not run a circuit."
                    if success
                    else f"Install ngspice {contract.ngspice_version} or select its executable with --ngspice /path/to/ngspice. The KiCad container does not supply the host simulator.",
                )
            )
        return tuple(checks)
    except (OSError, ValueError) as exc:
        return (
            EnvironmentCheck(
                id="electrical-contract",
                required=True,
                status="FAIL",
                expected="Valid electrical project and contract",
                observed=str(exc),
                next_action="Repair the named configuration field; follow docs/workflow/ELECTRICAL_ANALYSIS.md.",
            ),
        )

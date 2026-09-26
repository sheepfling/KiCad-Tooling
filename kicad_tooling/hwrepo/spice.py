"""Bounded ngspice batch adapter with reviewed inputs and explicit measurement limits."""
from __future__ import annotations

import hashlib
import math
import re
import shlex
import shutil
from pathlib import Path

from .contract_coach import run_command
from .contracts import repo_path, write_model
from .electrical import SimulationCase, regular_input_bytes
from .models import CommandEvidence, ElectricalCheck, TransientAnalysis
from .waveform_data import read_waveform

# Analysis/control directives are generated here, never inherited from a model file.
MODEL_DIRECTIVES = {
    ".model", ".subckt", ".ends", ".param", ".func", ".global", ".ic", ".nodeset",
    ".options", ".option", ".temp",
}


def expanded_deck(root: Path, case: SimulationCase) -> str:
    """Flatten inventoried relative .include files; reject hidden dependencies and control code."""
    root = root.resolve()
    used: set[str] = set()

    def expand(name: str, ancestors: tuple[str, ...], main: bool = False) -> list[str]:
        if name in ancestors:
            raise ValueError(f"Recursive SPICE include: {name}")
        if name not in case.model_sha256:
            raise ValueError(f"Unbound SPICE dependency: {name}")
        used.add(name)
        path = repo_path(root, name)
        data = regular_input_bytes(path)
        if hashlib.sha256(data).hexdigest() != case.model_sha256[name]:
            raise ValueError(f"Stale reviewed model hash: {name}")
        lines = data.decode("utf-8").splitlines()
        if main:
            if not lines:
                raise ValueError("SPICE deck is empty")
            lines = lines[1:]  # SPICE always treats the first deck line as its title.
        output: list[str] = []
        ended = False
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("*"):
                output.append(line)
                continue
            if ended:
                raise ValueError(f"Content after .end in {name}")
            token = stripped.split()[0].lower()
            if token == ".end" and main and stripped.lower() == ".end":
                ended = True
                continue
            if token in {".include", ".inc"}:
                parts = shlex.split(stripped, comments=False, posix=True)
                if len(parts) != 2:
                    raise ValueError(f"Use one quoted relative include path in {name}")
                included = repo_path(path.parent, parts[1]).relative_to(root).as_posix()
                output.extend(expand(included, (*ancestors, name)))
            elif token.startswith(".") and token not in MODEL_DIRECTIVES:
                raise ValueError(f"Unsupported SPICE directive {token} in {name}; use a model-only deck")
            else:
                output.append(line)
        return output

    lines = expand(case.deck, (), True)
    if used != set(case.model_sha256):
        raise ValueError(f"Unused model dependencies: {sorted(set(case.model_sha256) - used)}")
    return "\n".join(lines)


def simulation_deck(root: Path, case: SimulationCase) -> str:
    if isinstance(case, TransientAnalysis):
        # Explicitly cap the internal step as well as requesting an output step.
        analysis = f"tran {case.step_s:.17g} {case.stop_s:.17g} 0 {case.step_s:.17g}"
    else:
        analysis = f"ac dec {case.points_per_decade} {case.start_hz:.17g} {case.stop_hz:.17g}"
    commands = [".control", "set filetype=ascii", "set numdgt=15",
                "set measureprec=15", "set rawfileprec=17", analysis]
    for index, measure in enumerate(case.measures):
        commands.extend((
            f"let value{index} = {measure.expression}",
            (f"meas {case.analysis} check{index} {measure.statistic} value{index} "
             f"from={measure.start:.17g} to={measure.stop:.17g}"),
        ))
    commands.extend(("write waveforms.raw all", "quit", ".endc", ".end"))
    return f"* Reviewed electrical case {case.id}\n{expanded_deck(root, case)}\n" + "\n".join(commands) + "\n"


def measured_checks(case: SimulationCase, command: CommandEvidence) -> tuple[ElectricalCheck, ...]:
    results: list[ElectricalCheck] = []
    if command.returncode != 0 or command.error:
        return (ElectricalCheck(id=case.id, status="FAIL",
                                detail=command.error or f"ngspice exited {command.returncode}; inspect its log."),)
    for index, measure in enumerate(case.measures):
        matches = re.findall(rf"^\s*check{index}\s*=\s*(\S+)", command.stdout, re.MULTILINE | re.IGNORECASE)
        try:
            if len(matches) != 1:
                raise ValueError("Missing or duplicate measurement")
            value = float(matches[0])
            if not math.isfinite(value):
                raise ValueError("Non-finite measurement")
        except ValueError as exc:
            results.append(ElectricalCheck(id=f"{case.id}/{measure.id}", status="FAIL", detail=str(exc)))
            continue
        passed = ((measure.minimum is None or value >= measure.minimum)
                  and (measure.maximum is None or value <= measure.maximum))
        results.append(ElectricalCheck(
            id=f"{case.id}/{measure.id}", status="PASS" if passed else "FAIL",
            observed=value, unit=measure.unit,
            detail=f"{measure.statistic}({measure.expression}) in [{measure.start:g}, {measure.stop:g}]; "
                   f"limits [{measure.minimum}, {measure.maximum}] {measure.unit}.",
        ))
    # ngspice may return zero after a control-language error.
    if re.search(r"(?im)^\s*(?:fatal\s+)?error\b|simulation interrupted|timestep too small", command.stdout + "\n" + command.stderr):
        results.append(ElectricalCheck(id=f"{case.id}/simulator", status="FAIL",
                                      detail="ngspice reported an error; inspect the command receipt."))
    return tuple(results)


def waveform_checks(path: Path, case: SimulationCase) -> tuple[ElectricalCheck, ...]:
    """Reject truncated/non-finite raw data and windows outside actual samples."""
    expected_scale = "time" if isinstance(case, TransientAnalysis) else "frequency"
    axis = read_waveform(path, expected_axis=expected_scale).axis
    results: list[ElectricalCheck] = []
    for measure in case.measures:
        tolerance = max(abs(measure.stop), 1e-15) * 1e-8
        covered = (axis[0] <= measure.start + tolerance and axis[-1] >= measure.stop - tolerance
                   and sum(measure.start - tolerance <= point <= measure.stop + tolerance
                           for point in axis) >= 2)
        results.append(ElectricalCheck(
            id=f"{case.id}/{measure.id}/coverage", status="PASS" if covered else "FAIL",
            detail="Measured window covered by waveform samples." if covered else
                   "Actual waveform does not cover the complete requested measurement window.",
        ))
    return tuple(results)


def executable_path(cli: str) -> str:
    candidate = shutil.which(cli)
    if candidate:
        return str(Path(candidate).resolve())
    path = Path(cli)
    return str(path.resolve()) if path.is_absolute() or path.parent != Path(".") else cli


def observed_versions(command: CommandEvidence) -> tuple[str, ...]:
    return tuple(re.findall(r"(?i)\bngspice-([0-9][A-Za-z0-9.+_-]*)", command.stdout))


def simulator_version(output: Path, cli: str, expected: str) -> CommandEvidence:
    command = run_command(output, (cli, "--version"), timeout=30)
    write_model(output / "ngspice-version.command.json", command)
    versions = observed_versions(command)
    if command.returncode != 0 or command.error or expected not in versions:
        raise ValueError(f"Exact ngspice {expected} required; observed {versions or command.error or command.stderr}")
    return command


def run_case(root: Path, output: Path, cli: str, case: SimulationCase,
             timeout: int = 120) -> tuple[CommandEvidence, tuple[ElectricalCheck, ...]]:
    directory = output / case.id
    directory.mkdir(exist_ok=False)
    deck = directory / "simulation.cir"
    deck.write_text(simulation_deck(root, case), encoding="utf-8")
    command = run_command(directory, (cli, "-n", "-b", str(deck)), timeout=timeout)
    write_model(directory / "ngspice.command.json", command)
    checks = list(measured_checks(case, command))
    raw = directory / "waveforms.raw"
    if not raw.is_file() or raw.stat().st_size == 0:
        checks.append(ElectricalCheck(id=f"{case.id}/waveforms", status="FAIL",
                                     detail="Simulation produced no waveform artifact."))
    else:
        try:
            checks.extend(waveform_checks(raw, case))
        except (OSError, ValueError) as exc:
            checks.append(ElectricalCheck(id=f"{case.id}/waveforms", status="FAIL", detail=str(exc)))
    return command, tuple(checks)

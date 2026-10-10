"""Project electrical-contract contexts for interface and input heuristics."""

from __future__ import annotations

from pathlib import Path

from .contracts import repo_path
from .control_input_bias import control_input_bias_heuristic_coverage
from .digital_peer_voltage_types import DigitalPeerVoltageLintContext
from .discovery import ProjectConfig
from .electrical import load_analysis
from .evidence import digest
from .i2c_pullup_heuristics import (
    i2c_pullup_heuristic_coverage as resolve_i2c_pullup_heuristic_coverage,
)
from .i2c_pullup_models import (
    I2cPullupAnalysis,
    I2cPullupHeuristicCoverage,
)
from .models import (
    AnalysisNotApplicable,
    AnalysisPending,
    ControlInputBiasHeuristicCoverage,
    ControlInputsAnalysis,
    DigitalPeerVoltageAnalysis,
    NetlistContract,
    SerialPeerAnalysis,
    SpiAnalysis,
    UsbCAnalysis,
)
from .serial_participants import SerialPeerRosterContext
from .spi_participants import SpiRosterContext
from .usb_c_ports import UsbCPortRosterContext


def spi_roster_context(root: Path, config: ProjectConfig) -> SpiRosterContext:
    """Load the SPI roster and bind it to the exact project electrical contract."""
    if config.electrical is None:
        return SpiRosterContext(state="not_configured")
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during SPI roster inspection")
    spi = None if contract is None else contract.spi
    if isinstance(spi, SpiAnalysis):
        state = "required"
        analysis = spi
    else:
        mode = getattr(spi, "mode", None)
        state = mode if mode in {"pending", "not_applicable"} else "not_configured"
        analysis = None
    return SpiRosterContext(
        state=state,
        analysis=analysis,
        source_path=relative_path,
        source_sha256=expected_digest,
    )


def serial_peer_roster_context(root: Path, config: ProjectConfig) -> SerialPeerRosterContext:
    """Load the serial peer map and bind it to the exact electrical contract."""
    if config.electrical is None:
        return SerialPeerRosterContext(state="not_configured")
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during serial-peer map inspection")
    section = None if contract is None else contract.serial_peers
    if isinstance(section, SerialPeerAnalysis):
        state = "required"
        analysis = section
    else:
        mode = getattr(section, "mode", None)
        state = mode if mode in {"pending", "not_applicable"} else "not_configured"
        analysis = None
    return SerialPeerRosterContext(
        state=state,
        analysis=analysis,
        source_path=relative_path,
        source_sha256=expected_digest,
    )


def digital_peer_voltage_context(
    root: Path, config: ProjectConfig
) -> DigitalPeerVoltageLintContext:
    """Read and hash-bind the optional exact digital-peer voltage map."""
    if config.electrical is None:
        return DigitalPeerVoltageLintContext(state="not_configured")
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during digital-peer voltage inspection")
    section = None if contract is None else contract.digital_peer_voltages
    if isinstance(section, DigitalPeerVoltageAnalysis):
        state = "required"
        analysis = section
    elif isinstance(section, AnalysisPending):
        state = "pending"
        analysis = None
    elif isinstance(section, AnalysisNotApplicable):
        state = "not_applicable"
        analysis = None
    else:
        state = "not_configured"
        analysis = None
    return DigitalPeerVoltageLintContext(
        state=state,
        analysis=analysis,
        source_path=relative_path,
        source_sha256=expected_digest,
    )


def control_input_bias_coverage_from_project(
    root: Path,
    config: ProjectConfig,
    observed: NetlistContract,
    netlist_sha256: str,
) -> ControlInputBiasHeuristicCoverage:
    """Bind control-bias heuristic resolution to the current electrical contract bytes."""
    if config.electrical is None:
        return control_input_bias_heuristic_coverage(
            observed,
            netlist_sha256=netlist_sha256,
            source_path=None,
            source_sha256=None,
            state="not_configured",
        )
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during control-input heuristic inspection")
    control_inputs = None if contract is None else contract.control_inputs
    if isinstance(control_inputs, ControlInputsAnalysis):
        state = "required"
        spec = control_inputs
    elif isinstance(control_inputs, AnalysisPending):
        state = "pending"
        spec = None
    elif isinstance(control_inputs, AnalysisNotApplicable):
        state = "not_applicable"
        spec = None
    else:
        state = "not_configured"
        spec = None
    return control_input_bias_heuristic_coverage(
        observed,
        netlist_sha256=netlist_sha256,
        source_path=relative_path,
        source_sha256=expected_digest,
        state=state,
        spec=spec,
    )


def i2c_pullup_coverage_from_project(
    root: Path,
    config: ProjectConfig,
    observed: NetlistContract,
    netlist_sha256: str,
) -> I2cPullupHeuristicCoverage:
    """Bind I2C hint resolution to the exact electrical contract and native netlist."""
    if config.electrical is None:
        return resolve_i2c_pullup_heuristic_coverage(
            observed,
            netlist_sha256=netlist_sha256,
            source_path=None,
            source_sha256=None,
            state="not_configured",
        )
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during I2C pull-up heuristic inspection")
    pullups = None if contract is None else contract.i2c_pullups
    if isinstance(pullups, I2cPullupAnalysis):
        state = "required"
        spec = pullups
    elif isinstance(pullups, AnalysisPending):
        state = "pending"
        spec = None
    elif isinstance(pullups, AnalysisNotApplicable):
        state = "not_applicable"
        spec = None
    else:
        state = "not_configured"
        spec = None
    return resolve_i2c_pullup_heuristic_coverage(
        observed,
        netlist_sha256=netlist_sha256,
        source_path=relative_path,
        source_sha256=expected_digest,
        state=state,
        spec=spec,
    )


def usb_c_port_roster_context(root: Path, config: ProjectConfig) -> UsbCPortRosterContext:
    """Load USB-C role coverage and bind it to the exact project electrical contract."""
    if config.electrical is None:
        return UsbCPortRosterContext(state="not_configured")
    path = repo_path(root, config.electrical)
    relative_path = path.relative_to(root).as_posix()
    expected_digest = digest(path)
    contract = load_analysis(root, config)
    if digest(path) != expected_digest:
        raise ValueError("Electrical contract changed during USB-C port roster inspection")
    usb_c = None if contract is None else contract.usb_c
    if isinstance(usb_c, UsbCAnalysis):
        state = "required"
        analysis = usb_c
    else:
        mode = getattr(usb_c, "mode", None)
        state = mode if mode in {"pending", "not_applicable"} else "not_configured"
        analysis = None
    return UsbCPortRosterContext(
        state=state,
        analysis=analysis,
        source_path=relative_path,
        source_sha256=expected_digest,
    )

"""Load checked electrical analysis inputs for offline relationship views."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..validate import hashes
from .contracts import read_model
from .electrical import selected_config
from .electrical_analysis_contract_models import ElectricalAnalysisContract
from .electrical_charts import checked_artifact, source_receipt
from .evidence import digest
from .models import ContractCoachReport, ElectricalAnalysisReport, NetlistContract


@dataclass(frozen=True)
class ElectricalViewEvidence:
    root: Path
    directory: Path
    report_path: Path
    analysis: ElectricalAnalysisReport
    report_sha256: str
    requirements_path: Path
    requirements_sha256: str
    contract: ElectricalAnalysisContract
    observed: NetlistContract | None
    observed_sha256: str | None
    native_sha256: str | None
    source_status: Literal["CURRENT", "STALE", "UNKNOWN", "UNAVAILABLE"]
    current_source_sha256: dict[str, str] | None

    def verify(self) -> None:
        """Reject changes between input selection and receipt publication."""
        if digest(self.report_path) != self.report_sha256:
            raise ValueError("Electrical analysis report changed during view creation")
        checked_artifact(self.directory, self.analysis, "requirements.json")
        if self.observed_sha256 is not None:
            checked_artifact(self.directory, self.analysis, "netlist-evidence.json")
        if self.native_sha256 is not None:
            checked_artifact(self.directory, self.analysis, "netlist.xml")
        if self.current_source_sha256 is not None:
            try:
                current = hashes(
                    self.root, selected_config(self.root, self.analysis.project_id).source_roots
                )
            except (OSError, ValueError) as exc:
                raise ValueError("Project source became unavailable during view creation") from exc
            if dict(current) != self.current_source_sha256:
                raise ValueError("Project source changed during view creation")


def load_electrical_view_evidence(root: Path, receipt: Path) -> ElectricalViewEvidence:
    """Read authored requirements and an optional hash-bound native netlist."""
    root = root.resolve()
    source = source_receipt(root, receipt)
    report_path = source / "electrical.json"
    analysis = read_model(report_path, ElectricalAnalysisReport)
    report_hash = digest(report_path)
    if Path(analysis.run_directory) != source:
        raise ValueError("Electrical report points to another receipt")
    requirements = checked_artifact(source, analysis, "requirements.json")
    contract = read_model(requirements, ElectricalAnalysisContract)
    if contract.project_id != analysis.project_id:
        raise ValueError("Analysis and requirements project IDs differ")
    recorded_source: dict[str, str] = (
        dict(analysis.source.files_sha256) if analysis.source is not None else {}
    )
    source_status: Literal["CURRENT", "STALE", "UNKNOWN", "UNAVAILABLE"] = "UNKNOWN"
    current_source_hashes: dict[str, str] | None = None
    if recorded_source:
        try:
            current_source = hashes(root, selected_config(root, analysis.project_id).source_roots)
        except (OSError, ValueError):
            source_status = "UNAVAILABLE"
        else:
            source_status = "CURRENT" if dict(current_source) == dict(recorded_source) else "STALE"
            current_source_hashes = dict(current_source)
    observed: NetlistContract | None = None
    observed_hash: str | None = None
    native_hash: str | None = None
    if "netlist-evidence.json" in analysis.artifacts_sha256:
        coach_path = checked_artifact(source, analysis, "netlist-evidence.json")
        coach = read_model(coach_path, ContractCoachReport)
        if coach.project_id != analysis.project_id:
            raise ValueError("Observed netlist evidence belongs to another project")
        observed_hash = digest(coach_path)
        if coach.status == "READY_FOR_REVIEW" and coach.observed is not None:
            native = checked_artifact(source, analysis, "netlist.xml")
            native_hash = digest(native)
            if coach.netlist_sha256 != native_hash:
                raise ValueError("Observed netlist digest differs from retained native artifact")
            observed = coach.observed
    return ElectricalViewEvidence(
        root=root,
        directory=source,
        report_path=report_path,
        analysis=analysis,
        report_sha256=report_hash,
        requirements_path=requirements,
        requirements_sha256=digest(requirements),
        contract=contract,
        observed=observed,
        observed_sha256=observed_hash,
        native_sha256=native_hash,
        source_status=source_status,
        current_source_sha256=current_source_hashes,
    )

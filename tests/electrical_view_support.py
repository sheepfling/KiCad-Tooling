"""Saved, hash-bound electrical receipts for offline relationship-view tests."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.electrical_analysis_contract_models import ElectricalAnalysisContract
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    ElectricalAnalysisReport,
    NetlistContract,
    SourceState,
)
from kicad_tooling.validate import hashes
from tests.electrical_parity_support import contract_netlist_xml


def saved_electrical_view(
    root: Path, contract: ElectricalAnalysisContract, observed: NetlistContract | None
) -> Path:
    directory = root / "build/electrical/saved"
    directory.mkdir(parents=True)
    write_model(directory / "requirements.json", contract)
    if observed is not None:
        native = directory / "netlist.xml"
        native.write_text(contract_netlist_xml(observed), encoding="utf-8")
        write_model(
            directory / "netlist-evidence.json",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=contract.project_id,
                netlist_sha256=digest(native),
                observed=observed,
            ),
        )
    config = selected_config(root, contract.project_id)
    source = SourceState(files_sha256=hashes(root, config.source_roots))
    artifacts = {path.name: digest(path) for path in directory.iterdir() if path.is_file()}
    receipt = directory / "electrical.json"
    write_model(
        receipt,
        ElectricalAnalysisReport(
            project_id=contract.project_id,
            source=source,
            status="PASS",
            run_directory=str(directory),
            artifacts_sha256=artifacts,
            checks=(),
        ),
    )
    return receipt

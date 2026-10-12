"""Shared synthetic release-evidence workspace for electrical regressions."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.electrical_evidence import verify_electrical
from kicad_tooling.hwrepo.electrical_runner import analyze
from kicad_tooling.hwrepo.evidence import digest, source_state
from kicad_tooling.hwrepo.models import (
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    EvidenceFile,
    SourceState,
    ValidationSummary,
)
from kicad_tooling.hwrepo.releasing import reference
from tests import test_contract_coach as coaching
from tests.electrical_simulation_support import ISLAND, NA, PROJECT, install_fixture
from tests.support import initialize_git


@dataclass
class ElectricalEvidenceWorkspace:
    """A disposable source-bound electrical report and native-summary pair."""

    fixture: coaching.ContractCoachTests
    root: Path
    contract: ElectricalAnalysisContract
    native: EvidenceFile
    source: SourceState
    simulator: Path
    output: Path
    path: Path

    def cleanup(self) -> None:
        self.fixture.doCleanups()

    def verify(self) -> ElectricalAnalysisReport:
        return verify_electrical(
            self.root, reference(self.root, self.path), self.source, PROJECT, self.native
        )

    def run_native_requirement(
        self,
        *,
        contract_field: str,
        requirement: object,
        netlist_xml: str,
        output_name: str,
    ) -> ElectricalAnalysisReport:
        contract_path = self.root / ISLAND / "tests/electrical.json"
        contract = read_model(contract_path, ElectricalAnalysisContract).model_copy(
            update={contract_field: requirement}
        )
        write_model(contract_path, contract)
        relative_contract = contract_path.relative_to(self.root).as_posix()
        subprocess.run(
            ("git", "-C", str(self.root), "add", "--", relative_contract),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            (
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                f"Synthetic {contract_field} requirement",
            ),
            check=True,
            capture_output=True,
        )
        self.source = source_state(self.root)

        native_summary = self.root / "build/native/controller/summary.json"
        native_netlist = native_summary.parent / "netlist.xml"
        native_netlist.write_text(netlist_xml, encoding="utf-8")
        summary = read_model(native_summary, ValidationSummary)
        write_model(
            native_summary,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(native_netlist),
                    }
                }
            ),
        )
        self.native = reference(self.root, native_summary)
        self.output = self.root / "build/electrical" / output_name
        result = analyze(
            self.root,
            PROJECT,
            self.output,
            native_summary=native_summary,
            ngspice=str(self.simulator),
        )
        assert result.status == "PASS", result
        self.path = self.output / "electrical.json"
        return result


def create_electrical_evidence_workspace() -> ElectricalEvidenceWorkspace:
    """Build the public-template synthetic repo used by electrical evidence tests."""
    fixture = coaching.ContractCoachTests()
    fixture.setUp()
    try:
        root = fixture.root
        native = reference(root, fixture.native / "summary.json")
        contract = install_fixture(root).model_copy(update={"grounding": NA, "high_frequency": NA})
        write_model(root / ISLAND / "tests/electrical.json", contract)
        initialize_git(root)
        subprocess.run(
            (
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=Synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Synthetic requirements",
            ),
            check=True,
            capture_output=True,
        )
        source = source_state(root)
        waveform = (
            "Title: synthetic\nFlags: real\nNo. Variables: 2\nNo. Points: 4\n"
            "Variables:\n0 time time\n1 v(out) voltage\nValues:\n"
            "0 0\n0\n1 0.001\n4.9\n2 0.004\n4.95\n3 0.005\n5\n"
        )
        simulator = coaching.fake_executable(
            root.parent / "ngspice",
            (
                "from pathlib import Path\nimport sys\n"
                "if sys.argv[1:] == ['--version']:\n    print('ngspice-47')\n"
                "else:\n"
                f"    Path('waveforms.raw').write_text({waveform!r})\n"
                "    print('check0 = 4.95' if Path.cwd().name == 'startup' else "
                "'check0 = 0.05\\ncheck1 = 0.25\\ncheck2 = 4.95')\n"
            ),
        )
        output = root / "build/electrical/release"
        result = analyze(root, PROJECT, output, ngspice=str(simulator))
        assert result.status == "PASS", result
        return ElectricalEvidenceWorkspace(
            fixture=fixture,
            root=root,
            contract=contract,
            native=native,
            source=source,
            simulator=simulator,
            output=output,
            path=output / "electrical.json",
        )
    except BaseException:
        fixture.doCleanups()
        raise


def reject_omitted_electrical_checks(
    workspace: ElectricalEvidenceWorkspace, check_ids: tuple[str, ...]
) -> None:
    """Require each removed retained check to fail source-bound replay."""
    saved_report = workspace.path.read_bytes()
    report = read_model(workspace.path, ElectricalAnalysisReport)
    try:
        for omitted in check_ids:
            write_model(
                workspace.path,
                report.model_copy(
                    update={"checks": tuple(item for item in report.checks if item.id != omitted)}
                ),
            )
            with pytest.raises(ValueError, match="checks fail or omit"):
                workspace.verify()
    finally:
        workspace.path.write_bytes(saved_report)
    workspace.verify()


@pytest.fixture(name="electrical_evidence_workspace")
def electrical_evidence_workspace() -> Iterator[ElectricalEvidenceWorkspace]:
    workspace = create_electrical_evidence_workspace()
    try:
        yield workspace
    finally:
        workspace.cleanup()

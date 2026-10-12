"""Source-bound digital peer-voltage evidence replay regression."""

from __future__ import annotations

import subprocess

import pytest

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.electrical_runner import analyze
from kicad_tooling.hwrepo.evidence import digest, source_state
from kicad_tooling.hwrepo.models import (
    ElectricalAnalysisContract,
    ValidationSummary,
)
from kicad_tooling.hwrepo.releasing import reference
from tests.electrical_evidence_support import ElectricalEvidenceWorkspace
from tests.electrical_evidence_support import (
    electrical_evidence_workspace as _electrical_evidence_workspace_fixture,  # noqa: F401
)
from tests.electrical_simulation_support import ISLAND, PROJECT
from tests.test_digital_peer_voltages import requirement as digital_peer_requirement

pytestmark = [
    pytest.mark.evidence_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


def digital_peer_netlist_xml() -> str:
    return (
        "<export><components>"
        '<comp ref="U1"><value>Synthetic controller</value>'
        "<footprint>Package_QFP:LQFP-48</footprint>"
        '<libsource lib="Synthetic" part="Controller"/>'
        '<units><unit name="A"><pins><pin num="12"/></pins></unit></units></comp>'
        '<comp ref="U2"><value>Synthetic peripheral</value>'
        "<footprint>Package_SO:SOIC-8</footprint>"
        '<libsource lib="Synthetic" part="Peripheral"/>'
        '<units><unit name="A"><pins><pin num="3"/></pins></unit></units></comp>'
        "</components><libparts>"
        '<libpart lib="Synthetic" part="Controller"><pins>'
        '<pin num="12" name="MOSI" type="output"/></pins></libpart>'
        '<libpart lib="Synthetic" part="Peripheral"><pins>'
        '<pin num="3" name="SDI" type="input"/></pins></libpart>'
        "</libparts><nets>"
        '<net name="SPI_MOSI"><node ref="U1" pin="12"/>'
        '<node ref="U2" pin="3"/></net>'
        "</nets></export>"
    )


def test_digital_peer_voltage_result_replays_from_bound_native_netlist(
    electrical_evidence_workspace: ElectricalEvidenceWorkspace,
) -> None:
    workspace = electrical_evidence_workspace
    contract_path = workspace.root / ISLAND / "tests/electrical.json"
    contract = read_model(contract_path, ElectricalAnalysisContract).model_copy(
        update={"digital_peer_voltages": digital_peer_requirement()}
    )
    write_model(contract_path, contract)
    relative_contract = contract_path.relative_to(workspace.root).as_posix()
    subprocess.run(
        ("git", "-C", str(workspace.root), "add", "--", relative_contract),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(workspace.root),
            "-c",
            "user.name=Synthetic fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Synthetic direct digital peer requirements",
        ),
        check=True,
        capture_output=True,
    )
    workspace.source = source_state(workspace.root)
    native_summary = workspace.root / "build/native/controller/summary.json"
    native_netlist = native_summary.parent / "netlist.xml"
    native_netlist.write_text(digital_peer_netlist_xml(), encoding="utf-8")
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
    workspace.native = reference(workspace.root, native_summary)
    workspace.output = workspace.root / "build/electrical/digital-peer-replay"
    result = analyze(
        workspace.root,
        PROJECT,
        workspace.output,
        native_summary=native_summary,
        ngspice=str(workspace.simulator),
    )
    assert result.status == "PASS", result
    checks = {item.id: item for item in result.checks}
    assert checks["digital-peer-voltage/spi-mosi/compatibility"].status == "PASS"
    workspace.path = workspace.output / "electrical.json"
    workspace.verify()

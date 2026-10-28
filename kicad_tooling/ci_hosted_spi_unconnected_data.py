"""Digest-pinned native fixtures for open SPI data-function pins."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import MappingProxyType

from .ci_hosted_spi_native import SPI_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_finding_models import DesignLintRuleOverride
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy, NetlistContract
from .validate import read_netlist

_SOURCE_HASHES = MappingProxyType(
    {
        "control": "af3490ef9bd15a32ec307a50c807a56611ca3f2e6e597bc66368b4fdadc97a2a",
        "fault": "d18786cbb35cf58f723b452b12b61abe5b3f347ebc1a540e3b9655097e98f13d",
    }
)


def spi_unconnected_data_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Verify open-MOSI and connected-control exports on exact pinned KiCad images."""
    if (version, image) not in SPI_NATIVE_TOOLCHAINS:
        raise ValueError(
            f"SPI unconnected-data fixtures do not cover KiCad {version} with this image"
        )
    root = root.resolve()
    pinned = pinned_image(image)
    repository = tooling_checkout_root()
    fixture_root = repository / "tests/fixtures/design_lint/spi-unconnected-data-native"
    sources = {
        "control": fixture_root / "control.kicad_sch",
        "fault": fixture_root / "open-mosi.kicad_sch",
    }
    source_hashes = MappingProxyType({case: digest(source) for case, source in sources.items()})
    if source_hashes != _SOURCE_HASHES:
        raise ValueError("SPI unconnected-data fixture sources changed from their reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"spi-unconnected-data-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        shutil.copyfile(source, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic SPI {case} source changed while preparing native input")
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{version}"\n'
        "for case in control fault; do\n"
        "  for run in first repeat; do\n"
        '    kicad-cli sch export netlist --format kicadxml --output "/output/${case}.${run}.netlist.xml" '
        '"/fixtures/${case}.kicad_sch"\n'
        "  done\n"
        "done\n"
    )
    argv = (
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",
        *user,
        "-e",
        "HOME=/tmp/kicad-spi-unconnected-data-fixtures",
        "-v",
        f"{inputs}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        script,
    )
    prefix = "spi-unconnected-data-fixture"
    log.event(f"{prefix}/native-export", "START", kicad_version=version, image=pinned)
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            f"{prefix}/native-export",
            "FAIL",
            kicad_version=version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native SPI unconnected-data export failed: {command.stderr or command.error}"
        )

    raw_hashes: dict[tuple[str, str], str] = {}
    normalized_hashes: dict[tuple[str, str], str] = {}
    contracts: dict[tuple[str, str], NetlistContract] = {}
    for case in sources:
        for run in ("first", "repeat"):
            path = output / f"{case}.{run}.netlist.xml"
            if not path.is_file():
                raise ValueError(f"Native SPI unconnected-data export omitted {path.name}")
            raw_hashes[(case, run)] = digest(path)
            observed = read_netlist(path)
            contracts[(case, run)] = observed
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native SPI {case} exports differ after typed-netlist normalization")

    control = contracts[("control", "first")]
    fault = contracts[("fault", "first")]
    for case, observed in (("control", control), ("fault", fault)):
        if observed.pin_functions != {"U1.1": "MOSI", "U1.2": "MISO"}:
            raise ValueError(
                f"Native SPI {case} data-function inventory changed: {observed.pin_functions}"
            )
        if observed.component_pin_numbers != {"U1": ("1", "2")}:
            raise ValueError(f"Native SPI {case} component pin inventory changed")
        if set(observed.components) != {"U1"}:
            raise ValueError(
                f"Native SPI {case} component inventory changed: {observed.components}"
            )
    if {net: set(pins) for net, pins in control.nets.items()} != {
        "SPI_MISO": {"U1.2"},
        "SPI_MOSI": {"U1.1"},
    }:
        raise ValueError("Native SPI connected control assignments changed")
    if {net: set(pins) for net, pins in fault.nets.items()} != {"SPI_MISO": {"U1.2"}}:
        raise ValueError("Native SPI fault changed more than the U1.1 assignment")

    rule_id = "bus.spi_unconnected_data_pin"
    fault_reports: dict[str, DesignLintReport] = {}
    for run in ("first", "repeat"):
        observed = contracts[("fault", run)]
        project_id = "synthetic-spi-unconnected-data-fault"
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=project_id,
            observed=observed,
            netlist_sha256=raw_hashes[("fault", run)],
        )
        fault_reports[run] = evaluate(project_id, coach, DesignLintPolicy())
    default_findings = tuple(
        item for item in fault_reports["first"].findings if item.rule_id == rule_id
    )
    if (
        len(default_findings) != 1
        or default_findings[0].subject != "U1.1: MOSI"
        or default_findings[0].mode != "off"
        or default_findings[0].disposition != "RULE_OFF"
    ):
        raise ValueError("Native SPI open-MOSI fault no longer emits one default-off candidate")
    review_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=rule_id,
                mode="review",
                reason="Exercise the synthetic native open-MOSI review candidate.",
            ),
        )
    )
    review_reports = [
        evaluate(
            "synthetic-spi-unconnected-data-fault",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id="synthetic-spi-unconnected-data-fault",
                observed=contracts[("fault", run)],
                netlist_sha256=raw_hashes[("fault", run)],
            ),
            review_policy,
        )
        for run in ("first", "repeat")
    ]
    review_findings = [
        tuple(item for item in report.findings if item.rule_id == rule_id)
        for report in review_reports
    ]
    if (
        any(len(findings) != 1 for findings in review_findings)
        or any(findings[0].subject != "U1.1: MOSI" for findings in review_findings)
        or review_findings[0][0].mode != "review"
        or review_findings[0][0].disposition != "OPEN"
        or review_findings[0][0].fingerprint != review_findings[1][0].fingerprint
        or review_findings[0][0].evidence != review_findings[1][0].evidence
    ):
        raise ValueError("Native SPI review evidence changed across repeated exports")

    control_report = evaluate(
        "synthetic-spi-unconnected-data-control",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-spi-unconnected-data-control",
            observed=control,
            netlist_sha256=raw_hashes[("control", "first")],
        ),
        review_policy,
    )
    if any(item.rule_id == rule_id for item in control_report.findings):
        raise ValueError("Connected native SPI control unexpectedly emitted an open-pin prompt")

    receipt_path = receipt.relative_to(root).as_posix()
    for case in ("control", "fault"):
        findings = () if case == "control" else review_findings[0]
        log.event(
            f"{prefix}/{case}",
            "PASS",
            kicad_version=version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            repeatable="true",
            findings=";".join(item.subject for item in findings) if findings else "none",
            **(
                {"review_mode": "review"}
                if case == "control"
                else {
                    "default_mode": default_findings[0].mode,
                    "default_disposition": default_findings[0].disposition,
                    "review_mode": review_findings[0][0].mode,
                    "review_disposition": review_findings[0][0].disposition,
                    "evidence": ";".join(
                        f"{key}={'|'.join(value)}"
                        for key, value in sorted(review_findings[0][0].evidence.items())
                    ),
                }
            ),
        )
    log.event(
        f"{prefix}/native-export",
        "PASS",
        kicad_version=version,
        image=pinned,
        control_source_sha256=source_hashes["control"],
        fault_source_sha256=source_hashes["fault"],
        control_normalized_netlist_sha256=normalized_hashes[("control", "first")],
        fault_normalized_netlist_sha256=normalized_hashes[("fault", "first")],
        repeatable="true",
        command_receipt=receipt_path,
    )
    log.finish()

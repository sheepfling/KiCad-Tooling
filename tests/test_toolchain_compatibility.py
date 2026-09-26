"""Version migration must retain exact identities and explicit native adapters."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from kicad_tooling.check_toolchain import assessment, toolchain
from kicad_tooling.hwrepo.doctor import doctor
from kicad_tooling.hwrepo.kicad_compatibility import require_cli_profile
from kicad_tooling.hwrepo.models import (
    ProjectConfig,
    TemplatePreflightReport,
    ToolchainRecord,
    ToolchainsCatalog,
)
from kicad_tooling.validate import check_report


def record(version: str = "10.0.5", **changes: object) -> ToolchainRecord:
    return ToolchainRecord.model_validate(
        {
            "id": "approved",
            "kicad_version": version,
            "image": "example.invalid/kicad@sha256:" + "a" * 64,
            "desktop_edit_policy": "approved_for_editing",
            "installer_source": "Reviewed source",
            "migration_policy": "Review on a branch",
            **changes,
        }
    )


class ToolchainCompatibilityTest(unittest.TestCase):
    def test_existing_ten_catalogs_keep_default_adapter(self) -> None:
        self.assertEqual("kicad-10", require_cli_profile(record()))

    def test_new_major_requires_explicit_author_declaration(self) -> None:
        with self.assertRaisesRegex(ValueError, "no declared CLI compatibility profile"):
            require_cli_profile(record("11.0.0"))
        self.assertEqual(
            "kicad-10",
            require_cli_profile(
                record("11.0.0", cli_profile="kicad-10"),
            ),
        )

    def test_unknown_adapters_are_rejected_at_configuration_boundary(self) -> None:
        with self.assertRaises(ValidationError):
            record("11.0.0", cli_profile="unimplemented")

    def test_compatibility_declaration_does_not_accept_version_drift(self) -> None:
        configured = record("11.0.0", cli_profile="kicad-10")
        self.assertEqual("PASS", assessment(configured, "11.0.0").status)
        for observed in ("11.0.1", "10.0.5", None):
            report = assessment(configured, observed)
            self.assertEqual("FAIL", report.status)
            self.assertFalse(report.desktop_editing_allowed)

    def test_doctor_blocks_undeclared_native_profile_but_preserves_portable_checks(self) -> None:
        configured = record("11.0.0")
        with (
            patch("kicad_tooling.hwrepo.doctor.toolchain", return_value=configured),
            patch(
                "kicad_tooling.hwrepo.doctor.preflight",
                return_value=TemplatePreflightReport(
                    template_version="1.0.0",
                    status="PASS",
                    issues=(),
                ),
            ),
            patch("kicad_tooling.hwrepo.doctor.command_output", return_value="true"),
            patch("kicad_tooling.hwrepo.doctor.shutil.which", return_value="/mock/executable"),
            patch("kicad_tooling.hwrepo.doctor.observed_version", return_value="11.0.0"),
        ):
            portable = doctor(Path.cwd(), toolchain_id="approved")
            self.assertEqual("PASS", portable.status)
            native = doctor(Path.cwd(), native=True, toolchain_id="approved", runner="local")
            self.assertEqual("FAIL", native.status)
            checks = {check.id: check for check in native.checks}
            self.assertEqual("FAIL", checks["cli-profile"].status)
            self.assertEqual("FAIL", checks["native-runner"].status)
            self.assertIsNone(checks["native-runner"].observed)

    def test_doctor_reports_explicit_profile_without_certifying_new_version(self) -> None:
        with (
            patch(
                "kicad_tooling.hwrepo.doctor.toolchain",
                return_value=record(
                    "11.0.0",
                    cli_profile="kicad-10",
                ),
            ),
            patch(
                "kicad_tooling.hwrepo.doctor.preflight",
                return_value=TemplatePreflightReport(
                    template_version="1.0.0",
                    status="PASS",
                    issues=(),
                ),
            ),
            patch("kicad_tooling.hwrepo.doctor.command_output", return_value="true"),
            patch("kicad_tooling.hwrepo.doctor.shutil.which", return_value="/mock/executable"),
            patch("kicad_tooling.hwrepo.doctor.observed_version", return_value="11.0.0"),
        ):
            report = doctor(Path.cwd(), native=True, toolchain_id="approved", runner="local")
        self.assertEqual("PASS", report.status)
        profile = next(check for check in report.checks if check.id == "cli-profile")
        self.assertEqual("kicad-10", profile.observed)
        self.assertIn("not tested-version certification", profile.next_action)

    def test_native_report_keeps_schema_and_exact_version_checks(self) -> None:
        config = ProjectConfig.model_validate_json(
            json.dumps(
                {
                    "schema_version": "1",
                    "kind": "pcb_only",
                    "assurance_profile": "training",
                    "not_for_manufacture": True,
                    "project_id": "board",
                    "component_identity": {"required": False, "part_ids": []},
                    "toolchain_id": "approved",
                    "kicad_version": "11.0.0",
                    "cli_profile": "kicad-10",
                    "image": record().image,
                    "project": "projects/board/design/main.kicad_pro",
                    "source_roots": ["projects/board/design"],
                    "required_inputs": [],
                    "validation": {
                        "kind": "pcb_only",
                        "expected_ignored_checks": {"erc": [], "drc": []},
                    },
                }
            )
        )
        data = {
            "$schema": "https://schemas.kicad.org/drc.v1.json",
            "kicad_version": "11.0.0",
            "included_severities": ["error", "warning", "exclusion"],
            "ignored_checks": [],
            "violations": [],
            "unconnected_items": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "drc.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(0, check_report(path, "drc", config))
            for field, value, message in (
                ("kicad_version", "11.0.1", "identity differs"),
                ("$schema", "https://schemas.kicad.org/drc.v2.json", "Unexpected report schema"),
            ):
                path.write_text(json.dumps({**data, field: value}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    check_report(path, "drc", config)

    def test_unspecified_toolchain_is_selected_only_when_unambiguous(self) -> None:
        with (
            patch("kicad_tooling.check_toolchain.settings"),
            patch(
                "kicad_tooling.check_toolchain.repo_path",
                return_value=Path("catalog.json"),
            ),
            patch("kicad_tooling.check_toolchain.read_model") as read,
        ):
            read.return_value = ToolchainsCatalog(schema_version="1", toolchains=(record(),))
            self.assertEqual("approved", toolchain(Path.cwd(), None).id)
            read.return_value = ToolchainsCatalog(
                schema_version="1",
                toolchains=(
                    record(),
                    record("11.0.0", id="next", cli_profile="kicad-10"),
                ),
            )
            with self.assertRaisesRegex(ValueError, "Select --toolchain"):
                toolchain(Path.cwd(), None)
            self.assertEqual("next", toolchain(Path.cwd(), "next").id)


if __name__ == "__main__":
    unittest.main()

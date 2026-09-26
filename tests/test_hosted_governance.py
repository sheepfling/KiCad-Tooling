"""Hosted governance observations must preserve missing controls and API uncertainty."""
from __future__ import annotations

import base64
import json
import shutil
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.governance_audit import main as audit_main
from kicad_tooling.hwrepo.hosted_governance import ApiError, _gh, audit
from tests.support import reference_root

ROOT = reference_root()
REPO = "example/hardware"


def api_response(root: Path, *args: str) -> object:
    """Active rulesets, a hidden legacy API, and a real-looking CODEOWNERS file."""
    endpoint = args[-1]
    if endpoint == f"repos/{REPO}":
        return {"full_name": REPO, "default_branch": "main"}
    if "/rules/branches/main?" in endpoint:
        return [[
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": 1,
                "dismiss_stale_reviews_on_push": True,
                "require_code_owner_review": True,
            }},
            {"type": "required_status_checks", "parameters": {
                "required_status_checks": [{"context": "Template acceptance"}],
                "strict_required_status_checks_policy": True,
            }},
            {"type": "non_fast_forward"},
        ]]
    if endpoint.endswith("/protection"):
        raise ApiError(endpoint, "HTTP 404: Resource not found", 404)
    if "/codeowners/errors?" in endpoint:
        return {"errors": []}
    if "/contents/.github/CODEOWNERS?" in endpoint:
        contents = "/projects/ @hardware-team\n/tools/ @process-maintainer\n"
        return {"type": "file", "encoding": "base64",
                "content": base64.encodebytes(contents.encode()).decode()}
    raise AssertionError(f"Unexpected gh call: {args}")


class HostedGovernanceAuditTests(unittest.TestCase):
    def test_transport_rejects_write_capable_gh_arguments(self) -> None:
        with self.assertRaisesRegex(ApiError, "Only read-only"):
            _gh(ROOT, "api", "-X", "POST", "repos/example/hardware/rulesets")

    def test_ruleset_controls_pass_but_unverified_people_remain_unknown(self) -> None:
        with patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=api_response):
            report = audit(ROOT, REPO)
        checks = {check.id: check for check in report.checks}
        self.assertEqual(report.status, "UNKNOWN")
        self.assertEqual(report.hosted_controls_status, "PASS")
        self.assertEqual(report.default_branch, "main")
        for name in (
            "branch_protected", "pull_requests_required", "required_checks", "approvals",
            "dismiss_stale_reviews", "up_to_date", "force_push_blocked",
            "codeowners_file", "code_owner_review",
        ):
            self.assertEqual(checks[name].status, "PASS", name)
        self.assertEqual(checks["team_identities"].status, "UNKNOWN")
        self.assertFalse(report.build_authorized)

    def test_current_gh_repository_is_discovered_when_repo_is_omitted(self) -> None:
        def current(root: Path, *args: str) -> object:
            if args == ("repo", "view", "--json", "nameWithOwner"):
                return {"nameWithOwner": REPO}
            return api_response(root, *args)

        with patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=current):
            report = audit(ROOT)
        self.assertEqual(report.repository, REPO)
        self.assertEqual(report.hosted_controls_status, "PASS")

    def test_missing_legacy_controls_and_codeowners_are_needs_setup(self) -> None:
        def missing(root: Path, *args: str) -> object:
            endpoint = args[-1]
            if endpoint == f"repos/{REPO}":
                return {"full_name": REPO, "default_branch": "main"}
            if "/rules/branches/main?" in endpoint:
                return [[]]
            if endpoint.endswith("/protection"):
                return {
                    "required_pull_request_reviews": {
                        "required_approving_review_count": 0,
                        "dismiss_stale_reviews": False,
                        "require_code_owner_reviews": False,
                    },
                    "required_status_checks": {"strict": False, "contexts": [], "checks": []},
                    "allow_force_pushes": {"enabled": True},
                }
            if endpoint.endswith("/contents?ref=main"):
                return []
            if "/contents/" in endpoint:
                raise ApiError(endpoint, "HTTP 404: Not Found", 404)
            raise AssertionError(endpoint)

        with patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=missing):
            report = audit(ROOT, REPO)
        checks = {check.id: check for check in report.checks}
        self.assertEqual(report.status, "NEEDS_SETUP")
        self.assertEqual(report.hosted_controls_status, "NEEDS_SETUP")
        for name in ("required_checks", "approvals", "dismiss_stale_reviews", "up_to_date",
                     "force_push_blocked", "codeowners_file", "code_owner_review"):
            self.assertEqual(checks[name].status, "NEEDS_SETUP", name)

    def test_inaccessible_protection_does_not_prove_absence(self) -> None:
        def inaccessible(root: Path, *args: str) -> object:
            endpoint = args[-1]
            if endpoint == f"repos/{REPO}":
                return {"full_name": REPO, "default_branch": "main"}
            if "/rules/branches/main?" in endpoint:
                return [[]]
            if endpoint.endswith("/protection"):
                raise ApiError(endpoint, "HTTP 404: Resource not found", 404)
            if "/contents/" in endpoint or endpoint.endswith("/contents?ref=main"):
                raise ApiError(endpoint, "HTTP 403: Resource not accessible", 403)
            raise AssertionError(endpoint)

        with patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=inaccessible):
            report = audit(ROOT, REPO)
        checks = {check.id: check for check in report.checks}
        self.assertEqual(report.status, "UNKNOWN")
        self.assertEqual(report.hosted_controls_status, "UNKNOWN")
        self.assertEqual(checks["branch_protected"].status, "UNKNOWN")
        self.assertEqual(checks["pull_requests_required"].status, "UNKNOWN")
        self.assertEqual(checks["required_checks"].status, "UNKNOWN")
        self.assertEqual(checks["codeowners_file"].status, "UNKNOWN")

    def test_unreadable_high_priority_codeowners_cannot_be_bypassed(self) -> None:
        def hidden(root: Path, *args: str) -> object:
            endpoint = args[-1]
            if "/contents/.github/CODEOWNERS?" in endpoint:
                raise ApiError(endpoint, "HTTP 403: Resource not accessible", 403)
            if "/contents/CODEOWNERS?" in endpoint:
                raise AssertionError("Lower-priority CODEOWNERS must not prove the active file")
            return api_response(root, *args)

        with patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=hidden):
            report = audit(ROOT, REPO)
        self.assertEqual(next(check for check in report.checks
                              if check.id == "codeowners_file").status, "UNKNOWN")

    def test_codeowners_email_is_allowed_but_oversized_file_is_not(self) -> None:
        def email_owner(root: Path, *args: str) -> object:
            if "/contents/.github/CODEOWNERS?" in args[-1]:
                contents = "/projects/ engineer@example.com\n"
                return {"type": "file", "encoding": "base64", "size": len(contents),
                        "content": base64.b64encode(contents.encode()).decode()}
            return api_response(root, *args)

        with patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=email_owner):
            report = audit(ROOT, REPO)
        self.assertEqual(next(check for check in report.checks
                              if check.id == "codeowners_file").status, "PASS")

        def oversized(root: Path, *args: str) -> object:
            if "/contents/.github/CODEOWNERS?" in args[-1]:
                return {"type": "file", "encoding": "base64", "size": 3 * 1024 * 1024,
                        "content": ""}
            return api_response(root, *args)

        with patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=oversized):
            report = audit(ROOT, REPO)
        self.assertEqual(next(check for check in report.checks
                              if check.id == "codeowners_file").status, "NEEDS_SETUP")

    def test_malformed_codeowners_entry_never_passes_even_with_other_valid_owners(self) -> None:
        def malformed(root: Path, *args: str) -> object:
            endpoint = args[-1]
            if "/contents/.github/CODEOWNERS?" in endpoint:
                contents = "/projects/ @hardware-team\n/tools/ @process-maintainer broken-owner\n"
                return {"type": "file", "encoding": "base64",
                        "content": base64.b64encode(contents.encode()).decode()}
            return api_response(root, *args)

        with patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=malformed):
            report = audit(ROOT, REPO)
        codeowners = next(check for check in report.checks if check.id == "codeowners_file")
        self.assertEqual(codeowners.status, "NEEDS_SETUP")
        self.assertIn("line 2", codeowners.observed)
        self.assertEqual(report.hosted_controls_status, "NEEDS_SETUP")

    def test_github_codeowners_errors_and_unavailable_validation_fail_closed(self) -> None:
        def invalid_pattern(root: Path, *args: str) -> object:
            if "/codeowners/errors?" in args[-1]:
                return {"errors": [{"line": 2, "kind": "Invalid pattern",
                                    "message": "unsupported pattern", "path": ".github/CODEOWNERS"}]}
            return api_response(root, *args)

        with patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=invalid_pattern):
            report = audit(ROOT, REPO)
        codeowners = next(check for check in report.checks if check.id == "codeowners_file")
        self.assertEqual(codeowners.status, "NEEDS_SETUP")
        self.assertIn("Invalid pattern", codeowners.observed)

        def unavailable(root: Path, *args: str) -> object:
            if "/codeowners/errors?" in args[-1]:
                raise ApiError(args[-1], "HTTP 403: Resource not accessible", 403)
            return api_response(root, *args)

        with patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=unavailable):
            report = audit(ROOT, REPO)
        codeowners = next(check for check in report.checks if check.id == "codeowners_file")
        self.assertEqual(codeowners.status, "UNKNOWN")
        self.assertEqual(report.hosted_controls_status, "UNKNOWN")

        def malformed_response(root: Path, *args: str) -> object:
            if "/codeowners/errors?" in args[-1]:
                return {"syntax_errors": []}
            return api_response(root, *args)

        with patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=malformed_response):
            report = audit(ROOT, REPO)
        self.assertEqual(next(check for check in report.checks
                              if check.id == "codeowners_file").status, "UNKNOWN")

    def test_empty_governance_roles_need_setup_even_with_enough_unique_people(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hosted-governance-roles-") as temporary:
            root = Path(temporary)
            (root / "catalog").mkdir()
            shutil.copy2(ROOT / "catalog/team-policy.json", root / "catalog/team-policy.json")
            record = json.loads((ROOT / "templates/github-governance.example.json").read_text())
            record.update({
                "authors": ["alice", "bob"],
                "reviewers": ["carol"],
                "integrators": ["alice"],
            })
            for missing in ("authors", "reviewers", "integrators"):
                with self.subTest(missing=missing):
                    variant = {**record, missing: []}
                    (root / "governance.json").write_text(json.dumps(variant))
                    with patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=api_response):
                        report = audit(root, REPO, "governance.json")
                    identities = next(check for check in report.checks
                                      if check.id == "team_identities")
                    self.assertEqual(identities.status, "NEEDS_SETUP")
                    self.assertIn(missing, identities.observed)
                    self.assertEqual(report.hosted_controls_status, "PASS")
                    self.assertEqual(report.status, "NEEDS_SETUP")

    def test_invalid_auth_and_governance_branch_mismatch_are_explicit(self) -> None:
        with patch("kicad_tooling.hwrepo.hosted_governance._gh",
                   side_effect=ApiError("repos/example/hardware", "HTTP 401: Bad credentials", 401)):
            inaccessible = audit(ROOT, REPO)
        self.assertEqual(inaccessible.status, "UNKNOWN")
        self.assertIn("authentication", inaccessible.checks[0].next_action or "")

        def trunk(root: Path, *args: str) -> object:
            if args[-1] == f"repos/{REPO}":
                return {"full_name": REPO, "default_branch": "trunk"}
            adapted = (*args[:-1], args[-1].replace("trunk", "main"))
            return api_response(root, *adapted)

        # The record can be checked without assuming that its people have live permissions.
        with patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=trunk):
            mismatch = audit(ROOT, REPO, "templates/github-governance.example.json")
        self.assertEqual(mismatch.status, "NEEDS_SETUP")
        self.assertEqual(next(check for check in mismatch.checks
                              if check.id == "governance_branch").status, "NEEDS_SETUP")

    def test_cli_exposes_typed_json_and_brief_text(self) -> None:
        with (
            patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=api_response),
            patch.object(sys, "argv", ["kicad_tooling.governance_audit", "--root", str(ROOT),
                                       "--repo", REPO]),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(audit_main(), 2)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["lane"], "HOSTED_GOVERNANCE_AUDIT")
        self.assertEqual(payload["status"], "UNKNOWN")
        self.assertEqual(payload["required_status_checks"], ["Template acceptance"])
        with (
            patch("kicad_tooling.hwrepo.hosted_governance._gh", side_effect=api_response),
            patch.object(sys, "argv", ["kicad_tooling.governance_audit", "--root", str(ROOT),
                                       "--repo", REPO, "--format", "text"]),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(audit_main(), 2)
        self.assertIn("Hosted governance audit: UNKNOWN", output.getvalue())
        self.assertIn("team_identities: UNKNOWN", output.getvalue())


if __name__ == "__main__":
    unittest.main()

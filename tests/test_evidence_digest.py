"""Stable file identity hashing behavior."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.evidence import digest


def test_digest_matches_sha256_for_a_regular_file(tmp_path: Path) -> None:
    source = tmp_path / "evidence.json"
    content = b'{"status":"PASS"}\n'
    source.write_bytes(content)

    assert digest(source) == hashlib.sha256(content).hexdigest()


def test_digest_rejects_symlinked_evidence(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "evidence.json"
    link.symlink_to(target)

    with pytest.raises(ValueError, match="regular file"):
        digest(link)

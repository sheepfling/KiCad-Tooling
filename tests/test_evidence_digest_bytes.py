"""Tests for deterministic hashes of already-read evidence bytes."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.evidence import digest, digest_bytes


def test_digest_bytes_matches_the_canonical_stable_file_digest(tmp_path: Path) -> None:
    content = b"source-bound evidence\x00with binary data\n"
    path = tmp_path / "evidence.bin"
    path.write_bytes(content)

    assert digest_bytes(content) == digest(path)

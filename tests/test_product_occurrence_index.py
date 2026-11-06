"""Source identity and immutability checks for expanded product occurrences."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.product import load_repository
from kicad_tooling.hwrepo.product_occurrences import (
    occurrences,
    occurrences_for,
    product_occurrence_index,
)

ROOT = Path()


def test_occurrence_index_binds_exact_product_source_and_instance_paths() -> None:
    repository = load_repository(ROOT)
    product = repository.products[0]
    source = repository.product_sources[product.id]

    assert source.record is product
    assert source.sha256 == hashlib.sha256((ROOT / source.path).read_bytes()).hexdigest()
    index = product_occurrence_index(source)
    assert index.root_assembly == product.root_assembly
    assert "UNO.R1" in index.by_path
    assert dict(index.by_path) == dict(occurrences(product))
    with pytest.raises(TypeError):
        index.by_path["UNAUTHORED"] = index.by_path["UNO.R1"]

    changed_record = product.model_copy(
        update={"blocking_issues": (*product.blocking_issues, "changed in memory")}
    )
    with pytest.raises(ValueError, match="source identity"):
        occurrences_for(changed_record, index)


def test_repository_keeps_source_identity_for_policy_invalid_product(tmp_path: Path) -> None:
    for directory in ("catalog", "examples", "docs"):
        shutil.copytree(ROOT / directory, tmp_path / directory)

    original = load_repository(ROOT).product_sources
    source = next(iter(original.values()))
    path = tmp_path / source.path
    source_data = json.loads(path.read_text(encoding="utf-8"))
    source_data["assemblies"][0]["members"][0]["item"] = "missing-part"
    path.write_text(json.dumps(source_data), encoding="utf-8")

    repository = load_repository(tmp_path)
    assert repository.issues
    assert source.record.id not in {product.id for product in repository.products}
    captured = repository.product_sources[source.record.id]
    assert captured.path == source.path
    assert captured.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()

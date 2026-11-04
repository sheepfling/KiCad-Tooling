"""Source-bound plan and receipt contracts for explicit supplier handoffs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import StringConstraints

from .digikey_handoff_models import DigiKeyHandoffPayload
from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel


class SupplierHandoffPlan(StrictModel):
    """Reviewed, source-bound BOM payload for one explicit supplier submission."""

    schema_version: Literal["1"] = "1"
    supplier: Literal["digikey"] = "digikey"
    project_id: Identifier
    parts_report: RepositoryPath
    report_sha256: Digest
    payload: DigiKeyHandoffPayload
    payload_sha256: Digest
    source_hashes: Mapping[RepositoryPath, Digest]
    preconditions: Mapping[RepositoryPath, Digest | None]
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False


class SupplierHandoffReport(StrictModel):
    schema_version: Literal["1"] = "1"
    status: Literal["PREPARED", "SENT", "UNCERTAIN", "BLOCKED"]
    project_id: Identifier
    supplier: Literal["digikey"] = "digikey"
    handoff: RepositoryPath
    handoff_sha256: Digest
    payload_sha256: Digest
    attempt_receipt: RepositoryPath | None = None
    single_use_url: (
        Annotated[
            str,
            StringConstraints(pattern=r"^https://www\.digikey\.com/short/[a-z0-9]{7,8}$"),
        ]
        | None
    ) = None
    issues: tuple[NonEmptyText, ...] = ()
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False

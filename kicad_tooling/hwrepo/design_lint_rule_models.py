"""Typed catalog records for deterministic design-lint rules."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .design_lint_rule_types import DesignLintRuleId, DesignLintTheme
from .model_primitives import Digest, NonEmptyText, StrictModel


class DesignLintRuleMetadata(StrictModel):
    """Tool-owned definition and regression evidence for one deterministic lint rule."""

    rule_id: DesignLintRuleId
    title: NonEmptyText
    theme: DesignLintTheme | Literal["legacy"] = "legacy"
    implementation_owner: NonEmptyText = "legacy"
    status: Literal["active", "prototype", "retired"]
    maturity: Literal["synthetic_validated", "cohort_candidate", "field_validated"]
    default_mode: Literal["review", "block", "off"]
    evidence_adapter: NonEmptyText
    predicate: NonEmptyText
    supported_kicad_versions: tuple[NonEmptyText, ...]
    limitations: tuple[NonEmptyText, ...]
    fault_fixtures: tuple[NonEmptyText, ...] = ()
    valid_control_fixtures: tuple[NonEmptyText, ...] = ()
    metamorphic_fixtures: tuple[NonEmptyText, ...] = ()
    metamorphic_status: Literal["unreviewed", "covered", "not_applicable"] = "unreviewed"
    metamorphic_not_applicable_basis: NonEmptyText | None = None
    implementation_refs: tuple[NonEmptyText, ...]

    @model_validator(mode="after")
    def active_rule_has_regressions(self) -> DesignLintRuleMetadata:
        if self.status == "active" and (not self.fault_fixtures or not self.valid_control_fixtures):
            raise ValueError("Active design-lint rules need fault and valid-control fixtures")
        if not self.supported_kicad_versions:
            raise ValueError("Design-lint rules must declare supported KiCad evidence versions")
        if not self.limitations:
            raise ValueError("Design-lint rules must state at least one limitation")
        if not self.implementation_refs:
            raise ValueError("Design-lint rules must reference their implementation")
        if (
            self.implementation_owner != "legacy"
            and self.implementation_owner not in self.implementation_refs
        ):
            raise ValueError(
                "Design-lint implementation owner must be listed in implementation_refs"
            )
        if self.metamorphic_status == "covered":
            if not self.metamorphic_fixtures:
                raise ValueError("Covered metamorphic status needs a registered fixture")
            if self.metamorphic_not_applicable_basis is not None:
                raise ValueError("Covered metamorphic status cannot have a not-applicable basis")
        elif self.metamorphic_status == "not_applicable":
            if self.metamorphic_fixtures:
                raise ValueError("Not-applicable metamorphic status cannot register fixtures")
            if self.metamorphic_not_applicable_basis is None:
                raise ValueError("Not-applicable metamorphic status needs a reason")
        elif self.metamorphic_fixtures or self.metamorphic_not_applicable_basis is not None:
            raise ValueError(
                "Unreviewed metamorphic status cannot claim coverage or not-applicability"
            )
        return self


class DesignLintRuleCatalogDocument(StrictModel):
    """Packaged rule inventory before its exact file digest is attached."""

    schema_version: Literal["3"] = "3"
    rules: Annotated[tuple[DesignLintRuleMetadata, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_rule_ids(self) -> DesignLintRuleCatalogDocument:
        identifiers = [item.rule_id for item in self.rules]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Design-lint catalog rule IDs must be unique")
        if any(item.theme == "legacy" for item in self.rules):
            raise ValueError("Current design-lint catalog rules must declare their theme")
        if any(item.implementation_owner == "legacy" for item in self.rules):
            raise ValueError(
                "Current design-lint catalog rules must declare an implementation owner"
            )
        return self


class DesignLintRuleCatalog(StrictModel):
    """Versioned analyzer inventory bound to the exact packaged catalog bytes."""

    schema_version: Literal["1", "2", "3"]
    sha256: Digest
    rules: tuple[DesignLintRuleMetadata, ...]

    @model_validator(mode="after")
    def unique_rule_ids(self) -> DesignLintRuleCatalog:
        identifiers = [item.rule_id for item in self.rules]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Design-lint catalog rule IDs must be unique")
        if self.schema_version == "3" and any(
            item.theme == "legacy" or item.implementation_owner == "legacy" for item in self.rules
        ):
            raise ValueError("Schema 3 design-lint catalogs must declare each rule theme and owner")
        return self

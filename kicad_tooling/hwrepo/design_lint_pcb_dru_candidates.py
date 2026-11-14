"""Assemble source-bound PCB custom-rule candidates by their shared review phase."""

from __future__ import annotations

from pathlib import Path

from .design_lint_policy_models import DesignLintPolicy
from .design_lint_types import Candidate
from .pcb_drc_duplicate_board_section_review import (
    source_bound_pcb_drc_duplicate_board_section_candidates,
)
from .pcb_drc_duplicate_net_settings_section_review import (
    source_bound_pcb_drc_duplicate_net_settings_section_candidates,
)
from .pcb_drc_duplicate_severity_key_review import (
    source_bound_pcb_drc_duplicate_severity_key_candidates,
)
from .pcb_drc_exact_netclass_scope_scan import scan_unmatched_exact_netclass_drc_scopes
from .pcb_drc_exact_reference_pad_scope_scan import (
    scan_unmatched_exact_reference_pad_drc_scopes,
)
from .pcb_drc_exact_reference_scope_scan import scan_unmatched_exact_reference_drc_scopes
from .pcb_drc_exclusion_review import source_bound_pcb_drc_exclusion_candidates
from .pcb_drc_global_severity_review import (
    downgraded_electrical_drc_check_candidates,
    downgraded_miscellaneous_drc_check_candidates,
    downgraded_signal_integrity_drc_check_candidates,
    ignored_core_native_drc_check_candidates,
    ignored_dfm_native_drc_check_candidates,
    ignored_warning_default_native_drc_check_candidates,
    warning_core_native_drc_check_candidates,
    warning_dfm_native_drc_check_candidates,
)
from .pcb_drc_invalid_severity_value_review import (
    source_bound_pcb_drc_invalid_severity_value_candidates,
)
from .pcb_drc_netclass_settings_review import source_bound_pcb_netclass_settings_candidates
from .pcb_drc_nonstring_severity_value_review import (
    source_bound_pcb_drc_nonstring_severity_value_candidates,
)
from .pcb_drc_unknown_severity_key_review import (
    source_bound_pcb_drc_unknown_severity_key_candidates,
)
from .pcb_dru_contradictory_bounds_review import (
    contradictory_custom_drc_constraint_candidates,
)
from .pcb_dru_deprecated_function_review import (
    custom_drc_deprecated_condition_function_candidates,
)
from .pcb_dru_empty_disallow_review import empty_custom_drc_disallow_candidates
from .pcb_dru_layer_review import custom_drc_layer_reference_candidates
from .pcb_dru_malformed_bounds_review import custom_drc_malformed_bound_candidates
from .pcb_dru_malformed_condition_review import custom_drc_malformed_condition_candidates
from .pcb_dru_rule_review import (
    custom_drc_casefold_rule_name_collision_candidates,
    custom_drc_conflicting_severity_candidates,
    custom_drc_duplicate_rule_name_candidates,
    custom_drc_rule_without_constraint_candidates,
    excluded_custom_drc_rule_candidates,
    ignored_custom_drc_rule_candidates,
    text_variable_custom_drc_rule_candidates,
)
from .pcb_dru_unknown_constraint_review import unknown_custom_drc_constraint_candidates
from .pcb_dru_unknown_disallowed_object_review import (
    unknown_custom_drc_disallowed_object_candidates,
)
from .pcb_mechanical_edge_clearance import mechanical_edge_rule_coverage_candidates
from .project_models import ProjectConfig
from .source_state_models import SourceHashInventory


def collect_pcb_dru_candidates(
    root: Path,
    config: ProjectConfig,
    policy: DesignLintPolicy,
    source_hashes: SourceHashInventory,
    native_summary: Path,
) -> tuple[Candidate, ...]:
    """Collect PCB custom-rule and mechanical-edge review candidates."""
    return (
        *mechanical_edge_rule_coverage_candidates(
            root,
            config,
            policy,
            source_hashes,
            native_summary,
        ),
        *scan_unmatched_exact_netclass_drc_scopes(
            root,
            config,
            policy,
            source_hashes,
            native_summary,
        ),
        *scan_unmatched_exact_reference_drc_scopes(
            root,
            config,
            policy,
            source_hashes,
            native_summary,
        ),
        *scan_unmatched_exact_reference_pad_drc_scopes(
            root,
            config,
            policy,
            source_hashes,
            native_summary,
        ),
        *ignored_custom_drc_rule_candidates(root, config, source_hashes),
        *excluded_custom_drc_rule_candidates(root, config, source_hashes),
        *text_variable_custom_drc_rule_candidates(root, config, source_hashes),
        *custom_drc_rule_without_constraint_candidates(root, config, source_hashes),
        *custom_drc_duplicate_rule_name_candidates(root, config, source_hashes),
        *custom_drc_casefold_rule_name_collision_candidates(root, config, source_hashes),
        *custom_drc_conflicting_severity_candidates(root, config, source_hashes),
        *contradictory_custom_drc_constraint_candidates(root, config, source_hashes),
        *custom_drc_layer_reference_candidates(root, config, source_hashes),
        *custom_drc_malformed_condition_candidates(root, config, source_hashes),
        *unknown_custom_drc_constraint_candidates(root, config, source_hashes),
        *unknown_custom_drc_disallowed_object_candidates(root, config, source_hashes),
        *empty_custom_drc_disallow_candidates(root, config, source_hashes),
        *custom_drc_malformed_bound_candidates(root, config, source_hashes),
        *custom_drc_deprecated_condition_function_candidates(root, config, source_hashes),
    )


def collect_pcb_native_drc_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
    native_summary: Path,
) -> tuple[Candidate, ...]:
    """Collect source-bound native DRC configuration review candidates."""
    return (
        *source_bound_pcb_drc_duplicate_board_section_candidates(
            root,
            config,
            source_hashes,
        ),
        *source_bound_pcb_drc_duplicate_net_settings_section_candidates(
            root,
            config,
            source_hashes,
        ),
        *source_bound_pcb_netclass_settings_candidates(root, config, source_hashes),
        *source_bound_pcb_drc_duplicate_severity_key_candidates(
            root,
            config,
            source_hashes,
        ),
        *source_bound_pcb_drc_invalid_severity_value_candidates(root, config, source_hashes),
        *source_bound_pcb_drc_nonstring_severity_value_candidates(root, config, source_hashes),
        *source_bound_pcb_drc_unknown_severity_key_candidates(root, config, source_hashes),
        *ignored_core_native_drc_check_candidates(root, config, source_hashes),
        *ignored_dfm_native_drc_check_candidates(root, config, source_hashes),
        *ignored_warning_default_native_drc_check_candidates(root, config, source_hashes),
        *warning_core_native_drc_check_candidates(root, config, source_hashes),
        *warning_dfm_native_drc_check_candidates(root, config, source_hashes),
        *downgraded_signal_integrity_drc_check_candidates(root, config, source_hashes),
        *downgraded_electrical_drc_check_candidates(root, config, source_hashes),
        *downgraded_miscellaneous_drc_check_candidates(root, config, source_hashes),
        *source_bound_pcb_drc_exclusion_candidates(
            root, config, source_hashes, native_summary=native_summary
        ),
    )

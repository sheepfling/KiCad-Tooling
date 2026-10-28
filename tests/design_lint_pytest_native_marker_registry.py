"""Aggregate expected pytest markers from theme-owned registries."""

from types import MappingProxyType

from tests.design_lint_pytest_native_marker_registry_components import (
    PYTEST_NATIVE_LINT_SUITES as COMPONENT_SUITES,
)
from tests.design_lint_pytest_native_marker_registry_connectors import (
    PYTEST_NATIVE_LINT_SUITES as CONNECTOR_SUITES,
)
from tests.design_lint_pytest_native_marker_registry_interfaces import (
    PYTEST_NATIVE_LINT_SUITES as INTERFACE_SUITES,
)
from tests.design_lint_pytest_native_marker_registry_pcb import (
    PYTEST_NATIVE_LINT_SUITES as PCB_SUITES,
)
from tests.design_lint_pytest_native_marker_registry_shared import (
    PYTEST_NATIVE_LINT_SUITES as SHARED_SUITES,
)

PYTEST_NATIVE_LINT_SUITES = MappingProxyType(
    {**INTERFACE_SUITES, **CONNECTOR_SUITES, **COMPONENT_SUITES, **PCB_SUITES, **SHARED_SUITES}
)

"""Build the early pytest command for the repository-wide module-size guard."""

from __future__ import annotations

MODULE_SIZE_TEST_PATH = "tests/test_module_size_architecture.py"


def module_size_preflight_command(python_executable: str) -> tuple[str, ...]:
    """Run the module-size architecture test before the selected unit suite."""
    return (
        python_executable,
        "-B",
        "-I",
        "-m",
        "pytest",
        "-q",
        MODULE_SIZE_TEST_PATH,
    )

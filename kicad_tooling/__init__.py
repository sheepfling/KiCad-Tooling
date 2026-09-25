"""Reusable automation for KiCad project repositories.

Run commands from the repository root with ``python -m kicad_tooling.<command>``.
Direct execution of files under this package is deliberately unsupported: it
silently changes Python's import root and can run a different module graph.
"""

from importlib.metadata import version


def package_version() -> str:
    """Read the installed distribution version, independent of project Git tags.

    A source checkout without distribution metadata raises
    ``importlib.metadata.PackageNotFoundError``. Install it (optionally editable)
    before requesting its version. Policy versions remain separate in ``hwrepo``.
    """
    return version("kicad-team-tooling")

"""Reusable automation for KiCad project repositories.

Run commands from the repository root with ``python -m kicad_tooling.<command>``.
Direct execution of files under this package is deliberately unsupported: it
silently changes Python's import root and can run a different module graph.
"""

from importlib.metadata import distributions, version


def package_version() -> str:
    """Read the installed distribution version, independent of project Git tags.

    Prefer installed ``.dist-info`` over a stale source-tree ``.egg-info`` when
    both are visible to the active interpreter. A source checkout without
    distribution metadata raises ``importlib.metadata.PackageNotFoundError``.
    Install it (optionally editable) before requesting its version. Policy
    versions remain separate in ``hwrepo``.
    """
    name = "kicad-team-tooling"
    for distribution in distributions(name=name):
        files = distribution.files
        if files is not None and any(
            part.endswith(".dist-info") for item in files for part in item.parts
        ):
            return distribution.version
    return version(name)

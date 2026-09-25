"""Repository-local automation package.

Run commands from the repository root with ``python -m kicad_tooling.<command>``.
Direct execution of files under this package is deliberately unsupported: it
silently changes Python's import root and can run a different module graph.
"""

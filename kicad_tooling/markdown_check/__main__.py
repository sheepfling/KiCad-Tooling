"""Run the installed Markdown checker through the active Python environment."""
import sys

from . import run

raise SystemExit(run(sys.argv[1:]))

# Review one authored ground net

Select a saved electrical analysis receipt and an exact net name declared in
its grounding requirements:

```sh
kicad-team grounding-view --root /path/to/project-checkout \
  --receipt build/electrical/<run>/electrical.json \
  --net PILOT_B --format json
```

The command checks the saved requirements and optional native netlist evidence
against hashes in the analysis receipt. It writes a fresh ignored
`build/grounding-view/` receipt with an offline pin table and structured JSON.
The page also reports whether recorded analysis source files still match the
selected checkout, are stale, were not recorded, or cannot be checked.
Each declared pin is shown as matched, different, missing, unconnected,
ambiguous, or unreviewed. Pins observed on the selected net but absent from the
authored domain appear as undeclared. A similar net name remains a separate net.

MCP `export_grounding_view` uses the same service with `receipt`, exact `net`,
and a fresh `view_id` when exports are enabled.

This view compares authored schematic intent with retained netlist membership.
Missing native evidence stays `UNREVIEWED`. It does not derive required ground
topology from names or prove PCB copper, bonds, or physical continuity. Other
power and connectivity views remain on the feature backlog.
For authored source and load relationships, see [power-tree view](POWER_TREE_VIEW.md).

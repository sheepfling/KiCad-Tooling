# Review an authored power rail

Select one saved electrical analysis receipt and the exact rail ID from its
project-owned `power_connectivity` requirements:

```sh
kicad-team power-tree-view --root /path/to/project-checkout \
  --receipt build/electrical/<run>/electrical.json \
  --rail supply --format json
```

The command writes a fresh ignored `build/power-tree-view/` receipt with an
offline source → rail → load page and structured JSON. MCP
`export_power_tree_view` uses the same typed service with `receipt`, exact
`rail`, and a fresh `view_id` when exports are enabled.

The view reads the authored source groups, their `all` or `any` selection rule,
load endpoints, and exact net from the saved requirements. It checks every
retained artifact hash. If a ready native netlist observation is available, it
uses the existing power-connectivity checks for each source group and load and
shows each declared pin as matched, different, missing, unconnected, or
ambiguous. Pins observed on the selected rail but absent from its authored map
appear separately as undeclared. Without a usable native observation, the
relationships and pins remain `UNREVIEWED`.
Each endpoint also shows the authored and observed symbol and footprint, plus
the observed DNP flag when available. An `any` source group can pass while an
unused alternative is disconnected or DNP; that alternative stays visible.

If the same saved contract has an authored power budget, the page also shows
the nominal voltage, steady and startup demand, limits, and the existing budget
check calculations. These are calculated from declared loads; they are not measured
current. The page shows whether the analysis's recorded source inventory still
matches the current checkout, is stale, was not recorded, or is unavailable.
Historical netlist evidence remains labeled as such when the source has changed.
The saved analysis's overall status is shown separately from the selected rail.

This review compares schematic netlist membership and authored budget math. It
does not infer a required power path from a signal name or prove component
behavior, PCB copper, thermal margin, or physical continuity. Broader
connectivity tracing and measured power comparison remain separate backlog work.

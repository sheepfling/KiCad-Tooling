# Review one net and its neighboring component terminals

Select an exact net from a saved [electrical analysis](POWER_TREE_VIEW.md)
receipt:

```sh
kicad-team connectivity-view --root /path/to/project-checkout \
  --receipt build/electrical/<run>/electrical.json \
  --net PILOT_B
```

The command writes a fresh ignored `build/connectivity-view/` receipt with an
offline `index.html` and `connectivity-view.json`. Use `--output` for a specific
fresh `build/` directory or `--format json` for the structured result. MCP
`export_connectivity_view` uses the same service with `receipt`, exact `net`,
and a fresh `view_id` when exports are enabled.

The page shows pins on the selected net and a single neighboring component hop:
other terminals on those components and the nets observed at those terminals.
It retains exact authored ground or power roles when the saved requirements
declare the selected net. Matched, different, unconnected, ambiguous, and
undeclared pins remain distinct. Similar labels are separate nets. A net seen
only in the native observation is labeled as having no authored role; an
authored net without a retained observation stays unreviewed.

The saved analysis, requirements, native netlist, and source are checked through
the shared electrical evidence service. The result records their hashes and
labels the source against the current checkout. Changed inputs are rejected
before the view is saved. Bounds on selected pins, components, and neighboring
pins prevent a large netlist from creating an unusable page.

The neighboring nets share a component with the selected net. This does not
establish internal conduction through that component, PCB copper continuity,
component behavior, or an approved electrical path.

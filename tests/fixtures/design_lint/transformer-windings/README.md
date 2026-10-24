# Transformer winding same-net fixtures

These synthetic sources exercise `component.transformer_winding_same_net` for
the exact `Transformer:TRANSF1` identity. The KiCad 10.0.5 symbol definition
declares four passive terminals in two winding groups: pins 1/2 and pins 3/4.
The rule checks those groups only and does not assign functional roles to the
windings.
See the
[pinned official symbol source](https://gitlab.com/kicad/libraries/kicad-symbols/-/blob/10.0.5/Transformer.kicad_symdir/TRANSF1.kicad_sym).

`same-net-winding-1.kicad_sch` puts pins 1 and 2 on one native net while
keeping pins 3 and 4 separate. `distinct-winding-terminal-nets.kicad_sch`
assigns all four terminals to separate nets. Embedded symbols are minimal
tooling-owned pin maps; no upstream library drawing or product design is copied.

`shared-winding-groups-net.kicad_sch` adds a separate fault for
`component.transformer_winding_groups_share_net`: pin 1 from the first winding
and pin 3 from the second share one net, while pins 2 and 4 remain distinct.
The distinct-net control above is also its no-finding control. This is a
schematic review prompt; an intentional shared reference remains a project
decision and can be dispositioned with the normal rule policy or an exact
finding ignore.

The native lane exports each source twice with the project's exact pinned
KiCad 10.0.0 and 10.0.5 images, checks stable normalized netlists, and confirms
the fault/control lint result. This verifies source-to-netlist behavior; it
does not establish transformer operation, isolation suitability, or PCB
continuity.

Run the focused synthetic checks:

```sh
.venv/bin/python -I -m pytest tests/test_transformer_winding_same_net.py \
  -m 'design_lint and component_lint and design_lint_rule(rule_id="component.transformer_winding_same_net")'
```

Run the pinned native acceptance test:

```sh
KICAD_RUN_NATIVE_TRANSFORMER_WINDING_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_transformer_winding_native_fixture_lane.py \
  -m 'design_lint and component_lint and native_kicad and design_lint_rule(rule_id="component.transformer_winding_same_net")'
```

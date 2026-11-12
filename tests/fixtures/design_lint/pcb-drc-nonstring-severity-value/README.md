# Non-string PCB DRC severity-value fixtures

These synthetic project settings contain a boolean `track_dangling` severity
fault and an exact `warning` control. Both use the tooling-owned
`pcb-reference-zone-island/fault.kicad_pcb` fixture.

The digest-pinned KiCad 10.0.8 Docker probe also checked number, null, array,
and object values for `track_dangling`. Each native run kept the fixture's
Warning severity, while the adjacent invalid-string rule demonstrates that an
unrecognized string maps to Error. The type review reports the saved JSON
value and does not infer whether KiCad's built-in default is appropriate.

The rule covers only the 62 current string-valued DRC keys and the
`hole_near_hole` string migration alias. The two legacy boolean migration
aliases and other KiCad versions remain outside its scope.

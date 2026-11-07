# SWD connector return review fixtures

These are tooling-owned synthetic KiCad schematics. The fault case retains the
native SWDIO/SWCLK connector assignments from the generic SWD review fixture,
but its last connector contact is generically named `Pin_5`. Its net label is
still `GND`, which intentionally confirms that a net name alone does not
establish a connector return role. The valid control uses the same source with
an explicit native `GND` connector pin function.

Reviewed source hashes:

- `fault.kicad_sch`: `5962aae08d6eef3581371b2410a45ec68f33158c303fe114287a629ba3965485`
- `control.kicad_sch`: `45e993200c7ba4669083de09c93fbcb5082bdecd540214bdbd7b01da600a1118`
  (shared with `swd-generic-connector-native/fault.kicad_sch`)

The native lane exports each case twice with digest-pinned KiCad 10.0.0 and
10.0.5 images. It checks repeatable normalized netlists, exact SWDIO/SWCLK
assignments, a fault-only review cue, and native-return suppression. It does
not establish debug-header purpose, external wiring, copper continuity,
reviewer value, or manufacturing readiness.

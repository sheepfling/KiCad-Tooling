# Synthetic active regulator-support pin-role fixtures

These source-only KiCad schematics are tooling-owned fixtures marked not for
manufacture. They model generic active feedback-support symbols with no copied
product design or vendor reference circuit.

- `control.kicad_sch` has the authored pin functions and electrical types for
  a synthetic two-pin feedback isolator and a synthetic three-pin secondary
  reference.
- `wrong-optocoupler-function.kicad_sch` changes U2.1's native symbol function
  while preserving its pin number and component identity.
- `wrong-reference-type.kicad_sch` changes U3.3's native electrical type while
  preserving its pin number, function, and component identity.

The exact-version native test binds source hashes and repeats exports with the
digest-pinned KiCad 10.0.0 and 10.0.5 images. This check compares only mapped
identity, complete native pin inventory, and authored symbol metadata. The
unconnected support pins intentionally do not demonstrate feedback
connectivity, galvanic isolation, physical pinout, analog behavior, or PCB
return paths.

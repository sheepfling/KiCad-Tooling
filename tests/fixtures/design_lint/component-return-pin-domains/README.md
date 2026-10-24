# Component return pins on distinct nets

These tooling-authored schematics exercise a configurable review heuristic.
The fault assigns two recognized return pins on one fitted synthetic component
to separate neutral nets. The control assigns both to one net. A split can be
intentional, including separate analog and digital returns; the heuristic asks
for review and never declares that the nets must be joined.

The native fixture lane repeats netlist export and lint evaluation with the
digest-pinned KiCad 10.0.0 and 10.0.5 images. These files contain no product
source and are not suitable for manufacture.

# Conflicting placed Datasheet property fixtures

These tooling-owned schematic sources are synthetic and not for manufacture.
The fault gives J1 two different direct `Datasheet` values. Digest-pinned
KiCad 10.0.0, 10.0.5, and 10.0.8 netlist exports accept the source and retain
only the later value in J1's exported `Datasheet` field.

Controls cover one direct value, two identical direct values, and conflicting
values in an embedded library definition while the placed symbol retains its
ordinary empty value. The lint is source-bound and default REVIEW. It identifies
an inconsistent source; it does not choose the correct URL or establish
datasheet accuracy, electrical behavior, BOM correctness, or manufacturing
approval.

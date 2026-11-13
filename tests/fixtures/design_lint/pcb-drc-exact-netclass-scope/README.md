# Unmatched exact-netclass custom DRC scope fixtures

These tooling-authored rules select project netclasses on the shared synthetic
two-track board documented by the
[exact-net scope fixtures](../pcb-drc-exact-net-scope/README.md). Each rule
sets a 0.4 mm minimum against 0.2 mm tracks. The `absent` selector names no
class in the project settings and produces no `track_width` violation in the
pinned native lane.

The controls cover a declared `Narrow` class, KiCad's case-insensitive match
for `narrow`, an undeclared class referenced by `netclass_assignments`, and an
undeclared class referenced by `netclass_patterns`. The last two cases still
match native DRC even though the class is absent from `classes`; the linter
therefore treats all three project sources as the class-name inventory.

The files are synthetic test data, not an electrical design or recommended
track width. No project or cohort source is included.

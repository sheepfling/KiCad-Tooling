# Exact DRC reference and pad-number scope fixture

These custom-rule snippets exercise an exact `A.Reference` plus
`A.Pad_Number` selector against the tooling-owned J1 board in
`pcb-mechanical-edge-clearance`. `present` selects its pad 1;
`absent-pad` selects nonexistent pad 9; `reversed` checks condition order;
`case-reference` checks reference case; and the `pad-*` rules check native pad
number case matching against a synthetic board where pad 1 is changed to A1.

The fixture characterizes KiCad DRC selector behavior. The lint result is a
default review prompt about saved-rule scope, not a requirement to add the
selected pad or a claim that the board is electrically defective. It does not
reference a project checkout or a board outside this tooling repository.

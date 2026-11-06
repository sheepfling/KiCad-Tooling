# Custom DRC missing-constraint fixtures

These tooling-owned `.kicad_dru` and KiCad project-setting inputs contain no
product design data. The fault is a named, source-bound rule with a condition
and severity but no direct `(constraint ...)` clause. The control has one
direct track-width constraint.

Synthetic lint checks verify default REVIEW evidence, policy handling, source
hash binding, variable-substitution scope, and the quiet constrained control.
The exact-version native fixture runs the existing terminal-sentinel probe for
both files on KiCad 10.0.0 and 10.0.5. The sentinel can pass for the
unconstrained rule, showing that rule-file load proof does not enumerate each
authored rule's contents.

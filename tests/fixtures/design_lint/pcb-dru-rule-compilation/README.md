# Custom DRC rule compilation fixtures

These source files are synthetic probes for the `kicad-druid` cohort's
terminal-rule idea. The packaged probe board contains one 0.3 mm track. The
tooling appends a uniquely named 10 mm minimum-width rule to a temporary copy
of each source file and requires KiCad to report that rule by name.

- `control.kicad_dru` is syntactically valid. Its lower-case item type is a
  deliberately nonmatching but parseable condition, so the terminal sentinel
  must still fire. This demonstrates that compilation proof does not establish
  semantic correctness of every authored condition.
- `fault-malformed-syntax.kicad_dru` omits a closing parenthesis from a rule.
  KiCad documents that custom-rule syntax errors prevent DRC from running; the
  native lane requires this case to fail without evidence that the terminal
  sentinel was evaluated. A syntactically valid but nonmatching condition is
  deliberately kept in the control to show the sentinel's semantic limit.

The fixtures contain no project design data. Exact-native tests use the
digest-pinned KiCad 10.0.0 and 10.0.5 images. The report proves only that the
native rule parser reached the final appended rule for this supported KiCad
version; it does not prove that project-specific custom rules match intended
objects, satisfy electrical requirements, or describe valid fabrication
limits.

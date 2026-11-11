# Custom DRC deprecated condition function fixtures

These small `.kicad_dru` inputs are synthetic tooling fixtures. They contain
no project or product design data.

- `fault.kicad_dru` exercises all five deprecated function spellings that the
  KiCad 10 custom-rule reference labels deprecated.
- `control.kicad_dru` uses the documented replacements and puts old spellings
  only inside quoted string values and a source comment.

The review is source-level evidence. It does not claim that an old expression
is rejected, changes its result, or creates an electrical defect. It asks a
reviewer to check KiCad's documented replacement before maintaining that
custom rule. The native sentinel fixture confirms only that the fault and
replacement sources reach the terminal rule on the digest-pinned KiCad 10.0.8
image; it does not evaluate whether either condition matches the intended board
objects.

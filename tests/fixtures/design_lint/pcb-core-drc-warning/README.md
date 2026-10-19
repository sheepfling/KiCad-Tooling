# Core DRC warning-severity fixtures

These tooling-owned KiCad 10 project-settings fragments exercise review of
Error-default core DRC checks that a project explicitly sets to Warning.

- `fault.kicad_pro` lowers `clearance` and `unconnected_items` to Warning and
  keeps `shorting_items` at Error. It should produce two review candidates.
- `control.kicad_pro` keeps the covered checks at Error and sets an unrelated
  `missing_courtyard` check to Warning. It should produce no candidate.

The fixtures contain no board or project source. They test only the authored
severity settings and do not claim a DRC violation exists or that Warning is
unacceptable for a particular project.

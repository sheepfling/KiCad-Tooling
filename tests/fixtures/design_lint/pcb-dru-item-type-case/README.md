# Negative custom DRC item-type case trial

All inputs in this directory are tooling-owned synthetic fixtures. The trial
does not contain external board or project data. It checks whether a cohort
claim about case-sensitive `.kicad_dru` object-type literals justifies a local
source-review lint.

The original probe compares `A.Type == 'track'` with `A.Type == 'Track'`. Both
rules set a 0.4 mm minimum width against synthetic 0.3 mm tracks. KiCad 10.0.0
reports zero named track-width violations for both spellings; 10.0.5 and 10.0.8
report two for both.

The object-type probe adds a synthetic via and plated through-hole pad, each
with a 0.3 mm drill. Its case variants apply a 0.5 mm `hole_size` minimum using
`A.Type == 'via'`/`'Via'` and `A.Type == 'pad'`/`'Pad'`. A track-clearance
sentinel proves the custom-rule source was loaded. Each spelling and version
repeats twice. The exact native test pins KiCad 10.0.0, 10.0.5, and 10.0.8.

The lowercase and canonical pad rules each match once on all three versions.
The via rules each match zero times on 10.0.0 and once on 10.0.5 and 10.0.8.
The results show no case-dependent behavior for the tested object types, so the
cohort's lowercase-type warning was not adopted as a lint. The result does not
generalize to untested expression properties or other object types.

Object-type input SHA-256 values:

- `object-types.kicad_pcb`: `e55ce86bf38967b0b23fa505eef9ffd2ae3644648c4a5df5881ef85a919c06ae`
- `object-types.kicad_pro`: `1ee7c90b06eb5357aa8370f83a632757819492d86f1ef53e121e548de6ec4ebf`
- `fault-lowercase-object-types.kicad_dru`:
  `29395c601533b803df6353a4e8895e9a4ae21b520f68316fefd5daedf3788802`
- `control-canonical-object-types.kicad_dru`:
  `6aeb92220da79a500a3b9fc68b6815796667b598d21c521ca6cb17af69a7302b`

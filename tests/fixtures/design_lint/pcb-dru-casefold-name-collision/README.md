# Custom DRC case-folded name-collision fixtures

These version-1 `.kicad_dru` files are synthetic tooling inputs. The fault has
two pairs of distinct exact rule names that share a case-folded
spelling. The control uses distinct names, while a comment mentions a spelling
that would otherwise match. These files do not assert that KiCad treats
case-folded names as duplicate identifiers or changes native DRC behavior.

`fault-casefold-names.kicad_dru` SHA-256:

```text
f92b0cd958ba30798d29732d511df1a98e4bb2b46b1dde294a86b69fd9d352ff
```

`control-distinct-names.kicad_dru` SHA-256:

```text
1cdb168ab7a34214ab8a695bb8ea05bfdfb9f50ce93a9ab1a7df43ac2680e8a7
```

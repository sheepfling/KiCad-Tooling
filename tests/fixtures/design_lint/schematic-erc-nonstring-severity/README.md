# Schematic ERC non-string severity fixtures

These tooling-owned KiCad project settings put JSON booleans, numbers, null,
arrays, and objects in `erc.rule_severities`. The fault cases use the
recognized `pin_not_connected` key; a separate unknown-key case verifies that
the type check also covers malformed entries that the other ERC reviews cannot
interpret. The control uses the valid string `warning`. No customer or board
source is included.

The digest-pinned KiCad 10.0.8 native lane repeats each case and verifies that
the non-string values leave this Error-default fixture finding at Error while
the string control changes it to Warning. This measures the saved setting for
one recognized Error-default key; it does not claim native behavior for every
ERC key or infer the intended setting.

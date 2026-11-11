# Schematic ERC global severity fixtures

These synthetic KiCad 10.0 project settings exercise a globally ignored
`pin_not_connected` rule, a control containing the four documented
KiCad-default ignored rules plus an active `pin_not_connected` severity, and an
unknown-key case. The unknown-key case keeps the known `pin_not_connected`
rule at Error while assigning Ignore and Warning to two unrecognized keys.
The native lane pairs them with the separate tooling-owned schematic named in
its runner. No customer or project board source is included.

The key catalog is limited to KiCad 10.0.0 and 10.0.5 source. KiCad reads
`erc.rule_severities` by walking its registered ERC items and applying only
matching settings keys, so unknown entries do not change native severities.
KiCad 10.0.7 adds `same_local_global_power` ([ERC item definitions][items-107]);
a single 10.0.x key list would therefore be unsafe, so this lint leaves 10.0.7
out of scope until its complete catalog and native behavior are reviewed.
The versioned sources are [10.0.0 ERC settings][settings-100],
[10.0.0 ERC items][items-100], [10.0.5 ERC settings][settings-105], and
[10.0.5 ERC items][items-105].

[settings-100]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.0/eeschema/erc/erc_settings.cpp
[items-100]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.0/eeschema/erc/erc_item.cpp
[settings-105]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/eeschema/erc/erc_settings.cpp
[items-105]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/eeschema/erc/erc_item.cpp
[items-107]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.7/eeschema/erc/erc_item.cpp

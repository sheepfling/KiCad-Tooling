# Schematic ERC global severity fixtures

These synthetic KiCad 10.0 project settings exercise a globally ignored
`pin_not_connected` rule, a control containing the four documented
KiCad-default ignored rules plus an active `pin_not_connected` severity, and an
unknown-key case. The unknown-key case keeps the known `pin_not_connected`
rule at Error while assigning Ignore and Warning to two unrecognized keys.
The native lane pairs them with the separate tooling-owned schematic named in
its runner. No customer or project board source is included.

The exact-patch key catalog covers KiCad 10.0.0, 10.0.1, 10.0.2, 10.0.4,
10.0.5, 10.0.6, 10.0.7, and 10.0.8. KiCad reads `erc.rule_severities` by
walking its registered ERC items and applying only matching settings keys, so
unknown entries do not change native severities. KiCad 10.0.7 adds
`same_local_global_power`; the rule keeps separate catalogs for that release
and 10.0.8. KiCad 10.0.3 and unaudited releases remain out of scope. The
patch-tagged settings and item sources cover [10.0.0][settings-100] and
[its ERC items][items-100], [10.0.1][settings-101] and [its ERC items][items-101],
[10.0.2][settings-102] and [its ERC items][items-102],
[10.0.4][settings-104] and [its ERC items][items-104],
[10.0.5][settings-105] and [its ERC items][items-105],
[10.0.6][settings-106] and [its ERC items][items-106],
[10.0.7][settings-107] and [its ERC items][items-107],
[10.0.8][settings-108] and [its ERC items][items-108].

[settings-100]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.0/eeschema/erc/erc_settings.cpp
[settings-101]: https://raw.githubusercontent.com/KiCad/kicad-source-mirror/10.0.1/eeschema/erc/erc_settings.cpp
[settings-102]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.2/eeschema/erc/erc_settings.cpp
[settings-104]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.4/eeschema/erc/erc_settings.cpp
[settings-105]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.5/eeschema/erc/erc_settings.cpp
[settings-106]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.6/eeschema/erc/erc_settings.cpp
[settings-107]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.7/eeschema/erc/erc_settings.cpp
[settings-108]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.8/eeschema/erc/erc_settings.cpp
[items-100]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.0/eeschema/erc/erc_item.cpp
[items-101]: https://raw.githubusercontent.com/KiCad/kicad-source-mirror/10.0.1/eeschema/erc/erc_item.cpp
[items-102]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.2/eeschema/erc/erc_item.cpp
[items-104]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.4/eeschema/erc/erc_item.cpp
[items-105]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.5/eeschema/erc/erc_item.cpp
[items-106]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.6/eeschema/erc/erc_item.cpp
[items-107]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.7/eeschema/erc/erc_item.cpp
[items-108]: https://gitlab.com/kicad/code/kicad/-/raw/10.0.8/eeschema/erc/erc_item.cpp

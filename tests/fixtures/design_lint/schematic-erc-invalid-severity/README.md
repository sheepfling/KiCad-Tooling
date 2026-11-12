# Schematic ERC invalid-severity fixtures

These tooling-owned KiCad 10.0 project settings differ only in the configured
severity string for the recognized `pin_not_connected` ERC key. The fault uses
`warnnig`; the valid control uses the exact supported value `warning`. They
contain no board or customer source.

KiCad 10.0.8 applies saved severity strings while iterating registered ERC
items. The native regression runs both inputs on each audited, digest-pinned
KiCad 10.0 patch image and verifies that the typo leaves the native finding at
Error while the control lowers it to Warning. The checker reports only that
the saved string is outside the supported `error`, `warning`, and `ignore`
values. It does not infer which level the author intended.

Exact tagged implementation references: [KiCad 10.0.8 ERC settings][settings]
and [severity string conversion][conversion].

[settings]: https://raw.githubusercontent.com/KiCad/kicad-source-mirror/10.0.8/eeschema/erc/erc_settings.cpp
[conversion]: https://github.com/KiCad/kicad-source-mirror/blob/10.0.8/common/widgets/ui_common.cpp

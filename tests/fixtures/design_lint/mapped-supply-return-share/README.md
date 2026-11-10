# Mapped connector supply/return sharing fixtures

These tooling-owned schematics exercise the default-REVIEW
`connector.mapped_supply_return_share_net` rule.

- `fault.kicad_sch` assigns the generic two-pin connector to one unclassified
  `AUX_SHARED_NODE` net. Its independently authored interface map identifies
  J1.1 as supply and J1.2 as return.
- `control.kicad_sch` assigns the same contacts to separate
  `SUPPLY_SOURCE` and `RETURN_REFERENCE` nets.

Both sources contain only a generic two-pin symbol. They are repeated through
digest-pinned KiCad 10.0.0 and 10.0.5 Docker exports. The map supplies role
context; a shared schematic net is a review clue and does not prove copper
continuity or that the board must use separate nets. The rule supports project
policy overrides and exact finding ignores.

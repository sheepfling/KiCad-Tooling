# Mapped connector supply/signal sharing fixtures

These tooling-owned schematic fixtures exercise the default-REVIEW
`connector.mapped_supply_signal_share_net` rule.

- `fault.kicad_sch` assigns J1.1 and J1.2 to `SHARED_NET` while the current
  interface map classifies J1.1 as supply and J1.2 as signal. SHA-256:
  `1fed938a34c42fcbb5518de81eca7bf2698e47e6b739c750e77ee56e914bd8a5`.
- `control.kicad_sch` assigns those contacts to separate `SUPPLY_NET` and
  `SIGNAL_NET` nets. SHA-256:
  `b71ebb62b93bd63a6f52c4540f41e85ddafede34253df708e4834b71272dbb15`.

Both sources contain only a minimal generic two-pin symbol. The native lane
exports each twice using digest-pinned KiCad 10.0.0 and 10.0.5 Docker images.
The map supplies role context; the review does not establish incompatible
voltage, a design defect, required separation, or PCB copper continuity.
An intentionally shared net remains valid and can be ignored or overridden
through the project design-lint policy.

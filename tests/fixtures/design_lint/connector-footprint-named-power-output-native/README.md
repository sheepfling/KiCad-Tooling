# Footprint-alias named power-output fixtures

These tooling-owned KiCad schematics exercise the default-review rule
`connector.footprint_named_power_output_open_outlier`. Distinct synthetic
connector symbols share the same value, footprint, complete two-pin inventory,
and native pin metadata. Pin 1 is `BIAS_OUT` with native `power_out` type; pin 2
is a passive common anchor. The fault assigns J1.1 and leaves J2.1 open. The
control assigns both BIAS_OUT contacts to one net.

The finding is only a review prompt. It does not establish that the contacts
share a role or must connect, and these sources are not based on a product
board or project expectation.

SHA-256 source digests:
fault.kicad_sch: `f4d0b2505410d37a4a5b26598bcdc6b030fab5190290fcbea2690f59142e01b2`
control.kicad_sch: `43fcd7e09c75bba6d11b12ce937fd808c4e694b17fc4551769fdccd38abfde29`

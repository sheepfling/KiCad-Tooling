# Conflicting placed Reference fixtures

These small tooling-owned schematics are synthetic and not for manufacture.
The fault gives placed symbol J1 two direct `Reference` properties, `J1` and
`J9`. Digest-pinned KiCad 10.0.0, 10.0.5, and 10.0.8 exports succeed and
identify the component as J1 from its instance path, while omitting both
conflicting placed values from the component properties. The source-bound
review preserves both values and their source lines.

Controls cover one ordinary `Reference` property, two identical direct values,
and a conflicting property pair confined to an embedded library definition.
The lint is a REVIEW prompt for source inconsistency. It does not determine
which annotation is intended, certify project annotation, or replace native
ERC and source review.

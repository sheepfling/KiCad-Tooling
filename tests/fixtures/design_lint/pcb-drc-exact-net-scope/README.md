# Unmatched exact-net custom DRC scope fixtures

These tooling-authored KiCad fixtures contain two simple copper tracks on the
named nets `N1` and `N2`. The fault rule targets absent net `GHOST`; the valid
control targets `N1`. Both set a 0.4 mm minimum track width against 0.2 mm
tracks. The pinned native lane checks that KiCad reports the control violation
and leaves the absent selector without a track-width violation.
The case-variant rule targets lowercase `n1` to confirm KiCad's exact
`A.NetName` equality is case-insensitive and still selects the `N1` copper.

The files are synthetic test data, not an example electrical design or a
recommended width. They contain no project or cohort source.

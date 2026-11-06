# Negative custom DRC item-type case trial

These tooling-owned `.kicad_dru` inputs have no project design data. The trial
compares `A.Type == 'track'` with the canonical `A.Type == 'Track'`; both rules
set a 0.4 mm minimum width against the synthetic probe board's 0.3 mm tracks.
The exact-version native test runs both variants with the terminal compilation
sentinel and compares findings named for the authored track-width rule.

The pinned KiCad 10.0.0 image reports zero named track-width violations for
both spellings; the pinned 10.0.5 image reports two for both. The sentinel fires
in every run. Because the comparison found no case-dependent behavior, this
cohort idea was not adopted as a lint. These fixtures preserve the tested
boundary and contain no external board or project source.

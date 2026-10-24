# Design-lint cohort trial register

This register contains the detailed, feature-by-feature trials and public
applicability screens summarized under LINT-031 in the
[design-lint backlog](DESIGN_LINT_BACKLOG.md#lint-031--candidate-analyzer-trial-and-incremental-value-register).
Use the [review measurement worksheet](DESIGN_LINT_REVIEW_MEASUREMENT.md)
for dispositions and timing; leave unmeasured values unstated.

## LINT-031 — Candidate analyzer trial and incremental-value register

- **Status:** Partial v24; read-only synthetic comparisons across seven cohort
  repositories, a first-party public-template applicability replay,
  kicad_skills schematic-rule trials, a ThomsonLint board-export trial, and
  public project review samples are recorded below, plus a source-only audit of
  kicad-happy v2.3.1 CP-003. The UART peer heuristic now
  has an alternate-function net-label path, covered by synthetic fault/control
  tests and a pinned public hardware applicability screen; the screen found
  map-coverage candidates, not confirmed defects. A repeated
  public-template LED trial now records a contradictory cohort LED error on
  valid GPIO-side resistor paths. The latest
  `analog.clock_no_series_resistor` run covers seven tooling-owned schematic
  controls through the candidate's `--no-cli` fallback. A pinned kicad-happy
  single-pin connectivity follow-up covers a synthetic open-contact fault and
  common-net control, a native explicit-no-connect case, and a valid off-board
  endpoint comparison against project-authored connector coverage. Additional
  UART-peer, test-point, repeated-sheet, and off-board serial comparisons now
  measure the rule against local source-bound coverage and exact-version native
  ERC. Each trial is evaluated by feature, not by wholesale adoption. The
  off-board serial warnings duplicate native `isolated_pin_label` diagnostics;
  an authored external peer map clears the local TX/RX coverage prompts. The
  exact-version LINT-024 geometry
  re-screen and local explicit-no-connect comparison are also recorded; the
  latter preserves the peer REVIEW finding while the pinned candidate suppresses
  it. A pinned `kicad-happy` singleton-net comparison on the USB split-reference
  fault and common-reference control produced identical candidate findings on
  both inputs, adding no incremental USB reference-domain result. A v2.3.1
  follow-up also records a GPIO-to-regulator-enable false-positive boundary for
  the voltage-domain analyzer; local LINT-066 remains protocol-specific and
  now has a synthetic non-applicability control. A source-pinned
  STM32-KiCad-Pin-Checker parser trial compares suffix-collision ordering and
  escaped pin keys against LINT-050; it adds no local detection and is not an
  adoption case. A pinned KiCad Library Tools KLC S5.1 runtime trial is also
  recorded below; it found a valid generic-connector false positive and no
  board-design lint gain.

### Recorded source audit: kicad-happy CP-003 touch-pad copper clearance (2026-10-13)

- **Pinned source:** `kicad-happy` release `v2.3.1`, commit
  [`06840467ad0f5d76af45f64449b1f5ecb10f052f`][happy-cp003-commit]. The
  [CP-003 implementation][happy-cp003-source] and [license][happy-cp003-license]
  were checked at that revision. Its [release notes][happy-cp003-release]
  report fixes for round and oval touch-pad geometry after an earlier
  measurement sampled outside the actual copper.
- **Observed predicate:** CP-003 measures clearance only for footprints already
  classified as having no opposite-layer copper. It requires positive touch
  evidence in the footprint library/value or a `TOUCH`/`TCH` reference prefix,
  explicitly excluding test-point libraries. It selects same-layer zones whose
  names look like ground and reports an INFO measurement. Filled-polygon data
  uses outline samples; absent that data, the code falls back to filled or
  authored zone bounding boxes and labels the basis as heuristic. The rule
  supplies no minimum clearance or project-specific sensitivity requirement.
- **Local overlap and gap:** LINT-096 checks a project-authored keepout
  signature, and native DRC enforces configured copper spacing. The general
  native PCB snapshot retains filled-zone contours and pad nets, but not
  arbitrary pad outlines. LINT-133 now addresses the bounded requirement case:
  a project-authored exact pad/net/layer/minimum request is measured by a
  read-only native probe using KiCad's effective pad shape and filled-zone
  clearance API. Its tooling-owned circle, oval, and rotated-pad controls run
  against pinned KiCad 10.0.0 and 10.0.5. This does not add a generic name-based
  detector or universal clearance default.
- **Disposition:** The cohort's sampled GP-001 implementation remains deferred;
  its fixed 2 mm sampling missed the narrow synthetic midpoint void. LINT-133
  supplies a first-party, project-authored contract check for exact mapped
  pads and independently reviewed minimums, with native DRC comparison. It
  does not establish applicability or reviewer value on production boards.
  No cohort code or board fixture was copied, and no universal clearance
  requirement is adopted.
- **Recorded runtime trial — kicad-happy `checks_run` (2026-10-12):** Tested
  release tag `v2.2.1` at commit
  [`d5fd7da585fce7e59329b68fd065384216d4ff0a`](https://github.com/aklofas/kicad-happy/commit/d5fd7da585fce7e59329b68fd065384216d4ff0a);
  the pinned `LICENSE` declares MIT. Ten downloaded implementation/dependency
  files were checked against the official Git tree blob SHAs and kept in a
  temporary directory, outside this repository. Under Python 3.11.16, the
  pure `run_all_checks` function was called twice for each of two synthetic
  inputs: an empty schematic without PCB data, and the same schematic with an
  empty PCB structure. Both pairs returned identical findings and manifests.
  Each manifest had ten fixed-order check entries with `ran`, skip reason,
  examined-item count, and finding count. With no PCB, one check ran and nine
  were skipped; with the empty PCB, three ran and seven were skipped. Every
  examined-item and finding count was zero. This verifies reproducible
  observability of absent prerequisites, not detector behavior, useful item
  counting, or incremental fault detection. The candidate is not installed;
  its CLI and full workflow were not run. Compared with LINT-076's bounded,
  source-bound mapped-check receipts, the candidate exposes a broader aggregate
  cross-analysis skip ledger, but the empty-input trial establishes no unique
  review or detection value. Keep the global-ledger deferral; reopen only with
  a concrete missed-coverage regression.
- **References:** [kicad-happy](https://github.com/aklofas/kicad-happy),
  [pcb-inspector](https://github.com/takzen/pcb-inspector),
  [kilint](https://github.com/romkey/kilint),
  [kicad-sch-lint](https://github.com/rashuky/kicad-sch-lint),
  [KiDiff](https://github.com/INTI-CMNB/KiDiff),
  [kicad_skills](https://github.com/sabas0ba/kicad_skills),
  [kicad-tools](https://github.com/rjwalters/kicad-tools), and
  [ThomsonLint](https://github.com/holla2040/ThomsonLint).
- **Work:** For each useful candidate feature, record version/commit, license,
  installation friction, data boundary, supported KiCad versions, reproducible
  invocation, confirmed unique findings, duplicate findings, missed fixture
  faults, false positives, reviewer effort, and maintenance cost.
- **Boundary:** Documentation is not a local benchmark. Do not claim a
  candidate found a real defect until it is run on approved synthetic fixtures
  or otherwise authorized non-proprietary inputs.

### Recorded trial: KiCad Library Tools KLC S5.1 (2026-10-22)

- **Pinned source and license:** KiCad Library Tools commit
  [`a903a695bf4e69905e9e56548f44dd46cdc1130e`](https://gitlab.com/kicad/libraries/kicad-library-tools/-/commit/a903a695).
  The tested file is `library_utils/klc-check/rules_symbol/S5_1.py`. Its pinned README
  declares GPL-3.0-or-later by default, with per-file exceptions. The tested
  rule has no different license header.
- **Scope and boundary:** This is symbol-library authoring QA, not an
  electrical board check. The official [KLC S5.1 guidance](https://klc.kicad.org/symbol/s5/s5.1/)
  says fully specified symbols need a valid default footprint and generic
  symbols leave that field blank. The current [generic-symbol list](https://klc.kicad.org/)
  includes all `Connector` libraries. The KLC describes its content as
  guidelines with possible exceptions and says helper scripts cover only some
  guidance; library-team review remains manual.
- **Environment and execution:** Python 3.11.16. The candidate's own S5.1
  fault and control fixtures both passed in `--unittest` mode using the
  documented `check_symbol.py` entry point from `library_utils`. Running
  `python -I check_symbol.py --help` from `library_utils/klc-check` failed
  because isolated mode could not import the sibling `junit` module; the
  candidate's full installation and CI workflow were not tested.
- **Reproduction command:** From `library_utils` in the pinned checkout:

  ```sh
  python ./klc-check/check_symbol.py \
    ./klc-check/test_symbol/CI_Test_S5.x.kicad_symdir/Fail__S5.1__Filled_FT_Field_WithMoreThanOne_FT_Filter.kicad_sym \
    ./klc-check/test_symbol/CI_Test_S5.x.kicad_symdir/Pass__S5.1__Empty_FT_Field.kicad_sym \
    --rule S5.1 --unittest --nocolor
  ```

  Both upstream unit cases passed. The normal-mode fault and control invocations used the same input
  paths without `--unittest`, with `--rule S5.1 --nocolor`; they exited 3 and 0 respectively. The
  derived generic Connector control was run in normal mode with the same rule selection and exited
  2.
- **Fault and controls:** The upstream
  `Fail__S5.1__Filled_FT_Field_WithMoreThanOne_FT_Filter` fixture produced an
  S5.1 violation (exit 3); the upstream
  `Pass__S5.1__Empty_FT_Field` control was quiet (exit 0). A separate
  tooling-only valid `Connector_Generic` control was derived by changing only
  the upstream control's footprint-filter text to `SOT?23*`, keeping its
  default footprint empty. The checker warned that the default footprint was
  possibly missing (exit 2), because its generic-library allowlist contains
  `Device` but not `Connector`. This is a false positive for the documented
  generic connector case, not a product-board finding.
- **Incremental-value result and disposition:** The trial found no electrical
  design-lint gain. Keep KLC scripts outside the board design-lint catalog.
  Reconsider them as an optional library-admission preflight only if the
  tooling gains an explicit custom or supplier library intake boundary, and
  only after valid generic Connector symbols are handled. Do not make KLC
  guidance a universal blocking rule.
- **Reproducibility:** The checkout was kept under `/private/tmp`; no source,
  library, board, or fixture was copied into this repository. SHA-256 digests:
  `check_symbol.py` `d00d74050cd4df8c005d17d0545e7a83217d3e07652cad1e3877dc86597de5ec`;
  `S5_1.py` `11dbfaec088a6abdb49cdf8b5ccaff23cd89c1f13dd91cf6641fcbd24f8982b4`;
  `kicad_sym.py` `e0b0cb0029c399156e6d23254bd161ce5b942f9a6ac922da536f66522fc542c3`;
  `rulebase.py` `044d05bd58cfd05c4b8c51921f778792622bd46fd3deadd5d2770ef8caddbc0a`.
  The upstream fault fixture hash is
  `d8cb27ce434490321761cd8705d63489ae38a84460f2d486252bb1bded5d17c3`; the
  upstream empty-footprint control is
  `0c0d90bca4731c06098cecf6daf4cce99059e400fc0acc5ca2ea6fc31d90a23a`.
  The derived Connector control is
  `3a1245b775fc849563258aeffd6700c6fc8783ed8807c6d55759f1ff06908d99`. The
  three JUnit reports, also outside the repository, hash to
  `fa9b4246bacb69e8193ce6f555fe19d47dc2b8fc806e82c298c8391c66cb2b4b`
  (fault),
  `36a5dd7f448a75913d2b5a87a9c53ae0a5a9e7e0ea8bb9961ea9aea40a7799f8`
  (upstream control), and
  `ad61f0d798683d14d8966ed6324667d33087d1cfde813d354e5b4ba7b4de6762`
  (generic Connector control).
- **Done when:** Adopt only the analyzer or knowledge item with demonstrated
  incremental detection, review, or maintenance value; retain no dependency
  solely to aggregate duplicate warnings.

### Recorded review sample: Calcumaker UART-label applicability screen (2026-10-07)

- **Source boundary:** Read-only screen of the public `calcumaker` repository
  at pinned commit `113a2837bd155566d753635fb2cec1cb0458fa9f` ([source][calcumaker-revision]).
  Its [design document][calcumaker-design]
  describes the MCU-to-keyboard USART link and its +3V3/GND interface. The
  [hardware directory][calcumaker-hardware] declares CERN-OHL-S-2.0; its
  [license][calcumaker-license] SHA-256 is
  `253ad3f89603e728abfa60c36fbcaf8225cf55c1eab12725f19fb3d74d647f3a`.
  The selected root schematics are `calcumaker-mcu.kicad_sch`
  (`33654a8c539f58635376d16e400b3aacfe9c89163e889fdea7111687bd5b1693`)
  and `calcumaker-keyboard.kicad_sch`
  (`1657bb5bd63965eef0e046ef557605547cbda8eca3bcbd191c2b79063388562f`).
  The checkout, native exports, and trial script stayed under `/private/tmp`;
  no source or generated report was copied into Tooling.
- **Native evidence:** Exported both roots with the digest-pinned KiCad 10.0.5
  image `sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  The exported native XML netlist hashes are
  `9ba5a2009d518267e450dd9e89c0edd494c282e3942da9560faf88220992ad02` for the
  75-component MCU root and
  `3f69a81eebcf5023d38d218146edfb8912817ec77d68db737cdce76040ca3a3f` for the
  227-component keyboard root. ERC emitted 155 and 198 warnings respectively,
  with no errors; these are not clean-project acceptance results.
- **Observed result:** Under an intentionally unconfigured serial-map context,
  LINT-072 emitted one REVIEW coverage candidate per root from exact `UART_TX`
  and `UART_RX` net labels. The MCU candidate is U1.16/U1.17 and the keyboard
  candidate is U1.10/U1.9; each pair shares its TX/RX nets with a fitted
  connector candidate. Neither root exports native TX/RX function names for
  those pins, and the connector pins are generic. The earlier native-function
  detector and direct-peer/reference predicates returned no candidates. The
  netlist shows +3V3 and GND on both roots; the single +3V3 family makes
  LINT-066 inapplicable, while generic serial functions keep LINT-074 outside
  its predicate.
- **Incremental-value result:** The sample demonstrates that strict labeled-net
  discovery reaches a documented interface the function-only path cannot
  classify. It does not show an omitted project requirement, wrong wiring,
  missing ground, field precision, reviewer-effort reduction, or a true positive.
  Keep the result REVIEW-only and use an independently authored peer map to
  resolve it in a real project.
- **Reproduction and disposition:** The pinned source, exact hashes, native
  exports, and a temporary screen asserting one `net_label` result per root are
  recorded in the task's external scratch area only. The checked-in synthetic
  fixture and native lane independently verify the detector and exact-map
  suppression on KiCad 10.0.0 and 10.0.5. No candidate analyzer was installed;
  no cohort code, project source, or board expectation was adopted.

### Recorded sample: Calcumaker PCB geometry screen (2026-10-07)

- **Source boundary:** Read-only screen of the same public `calcumaker`
  checkout and pinned commit `113a2837bd155566d753635fb2cec1cb0458fa9f`.
  Its [display floor plan][calcumaker-display-floorplan] says the display PCB
  has no tracks, routed vias, or copper zones; the [hardware wiring
  review][calcumaker-wiring-review] describes KiCad 10.0.6 verification. No
  source or snapshot was copied into tracked Tooling content.
- **Native probe:** Ran the tooling-owned `native_pcb_probe.py.in` with the
  installed KiCad 10.0.6 `pcbnew` Python. The display board
  (`2078707fbe48a3a0d683cb14bbba8b94532819d502de2f390937ef191e2f0579`) had
  86 components and 699 pads; the MCU board
  (`f343795fc150aa5ac5bd68b7fb7f5391b8c813530fbefae01f51b14a21272490`) had
  75 components and 329 pads; the keyboard board
  (`9b20249b35ddfa956b9222186c94529a80edd493a146b424d280175eb4bef83a`) had
  227 components and 618 pads. Each snapshot reports zero tracks, zero zones,
  zero vias, and `zones_refilled=true`. Receipts are under ignored
  `build/public-lint-screen/`; they use the installed app rather than a
  project-selected digest-pinned container.
- **Applicability result:** These are placement-stage PCBs, not routed copper
  examples. LINT-020 requires native copper connectivity to decide whether
  mapped IC and capacitor pads form eligible candidates, so this sample cannot
  measure its connection or proximity findings. The result is inapplicable,
  not a finding or false-positive count. Re-screen only after a routed public
  revision is available; no universal distance or electrical expectation is
  inferred.

### Recorded review sample: Antmicro CM4 Baseboard multi-UART boundary screen (2026-10-07)

- **Source boundary:** Read-only screen of the public
  [antmicro/cm4-baseboard repository][antmicro-cm4] at commit
  `d248c2921e8e7f4c9b30c96ea5f376d9b2780f1e`. The repository declares
  Apache-2.0; its `LICENSE` SHA-256 is
  `c95bae1d1ce0235ecccd3560b772ec1efb97f348a79f0fbe0a634f0c2ccefe2c`.
  The root schematic SHA-256 is
  `e56bfc07b813d5f4d6b3e7c713c2096806a800c1877a3f9ef80fed27d8d41551`, and
  the PCB SHA-256 is
  `e6d5b83d6086030c290afe2d5e7c8035408697d3611ba4f28b83fc75451cdff5`.
  The README identifies KiCad 9.x and describes a USB-C input with a USB-4xUART
  bridge. The [hardware portal](https://openhardware.antmicro.com/boards/cm4-baseboard/)
  also describes four UARTs exposed over USB, and the
  [source schematic PDF](https://openhardware.antmicro.com/imported/boards/cm4-baseboard/doc/cm4-baseboard-main-d248c292-schematic.pdf)
  shows the bridge channels. The public checkout and all exports stayed under
  `/private/tmp`; no source, project expectation, or generated output was copied
  into Tooling.
- **Native evidence:** KiCad 10.0.5 ran from the digest-pinned image
  `sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  Two repeat exports had byte-identical XML; a separate earlier XML differed
  only in its volatile `<date>` field. All parsed to the same normalized
  `NetlistContract` SHA-256
  `cf012f85fea7458c2b7c05e6a609269ca8de0a15365a3ef85164bbdc53b5a8e5`:
  506 components, 393 nets, 1,821 pin assignments, and 36 DNP components. This
  is a KiCad 9-to-10 compatibility probe, not acceptance under the source's
  authored KiCad version. ERC reported 1,338 violations (13 errors and 1,325
  warnings), including 818 symbol-library and 506 footprint-link issues because
  the custom libraries were not configured; it is not a clean ERC baseline.
- **Observed result:** The native netlist has eight hierarchical labels from
  `UART.0.TX/RX` through `UART.3.TX/RX`. Their paired pins use generic function
  names such as `B1`, `B2`, `ADBUS0`, and `DDBUS1`, with active components on
  the labeled nets. The baseline `directly_linked_serial_peers` and
  `bus.serial_unmapped_peer` predicates did not identify UART participants.
  LINT-082 now recognizes four direct label-paired IC segments, while
  `bus.serial_peer_reference_review` remains quiet because each pair's explicit
  return pins are assigned to the same schematic net `GND`. The netlist also
  contains distinct `GNDD` and `Ethernet/VSS` names. No numbered-return group
  was found. These assignments do not establish the intended bonding of all
  return domains or PCB copper continuity.
- **Review load and interpretation:** With no project-authored connector map,
  the lint run returned 173 REVIEW findings, including ten
  `connector.no_connected_return` prompts on connectors whose native pin roles
  are generic or unavailable. The public source provides no independently
  approved external pinout to classify these as defects or false positives.
  This count is coverage and review workload, not a precision measurement.
  The common `GND` assignment across the four UART channels is a useful
  schematic control; it is not proof that a different return would be wrong.
- **Incremental-value result:** The screen exposed a gap in the native
  TX/RX-function predicate: explicitly UART-labeled signal pairs can cross two
  fitted ICs whose pin functions are generic. LINT-082 now adds a narrow
  label-based REVIEW path for numbered UART/USART labels and exact two-IC direct
  segments. Synthetic split/common, stale/exact map, ambiguity, DNP, incomplete
  metadata, CLI/MCP parity, and hash-seed coverage pass. The exact native fault/
  control lane now passes on KiCad 10.0.0 and 10.0.5; see LINT-082 for normalized
  netlist hashes. The public sample still shows no defect and does not establish
  that the labeled components are complete end-to-end serial peers.
- **Reproduction and disposition:** The two repeated raw XML exports had SHA-256
  `31f1125c5b04efc4f70d7c697fea415f717c7c9e232a54110e89865d9c7d9cdf`; the
  normalized report SHA-256 was
  `35a31e63e6f07eac7c1292805979535ebb643b949597a8ac16c91e3eebc4ace8` on both
  runs. Keep the export and typed evidence outside the repository. No cohort
  analyzer was installed, no code or expectation was copied, and no electrical
  conclusion was drawn from the sample.

### Recorded review sample: public STM32 USB device schematic (2026-10-03)

- **Source boundary:** Read-only trial of
  [stm32_usb_device](https://github.com/tmilkovic51/stm32_usb_device) at commit
  `93225b1d01f7e2a995875d1724888b313120c652`. The declared CERN-OHL-P-2.0
  license file SHA-256 is
  `5c82236273f7fa5d569c152951904c711f549cb786e829bc489486c41838255f`; the
  selected schematic SHA-256 is
  `4b6eed311ab9eec4c456476c488e5cce5497fc45f490ea42f180829da58368ea`. The
  checkout and trial output stayed under `/private/tmp`; no source or output
  was copied into this repository.
- **Native evidence:** KiCad 10.0.5 used the pinned
  `ghcr.io/kicad/kicad:10.0.5` image with digest
  `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  The exported netlist SHA-256 is
  `ece16a554cd97be8efaa516d2569175f84da0a91f584db07d7287a758ac1c422`; the
  parsed netlist contains 33 components. The review run produced nine lint
  prompts. Two exact-symbol connector prompts on native `Pin_2`/`Pin_3`
  placeholders were corrected to `connector.peer_pin_assignment_divergence`,
  which treats those roles as unknown and lower confidence.
- **Interpretation:** The sample has no approved external pinout or owner
  dispositions, so the prompts are not confirmed defects and cannot measure
  precision. No seeded defect was present, so misses were not measured. Its
  single D1 is a power LED, not an output-driven LED topology; LINT-063 is
  inapplicable. Reviewer value and effort remain unmeasured. This is an
  applicability and classification check only, not a clean-project benchmark.
- **Next evidence:** Keep these rules at REVIEW. Evaluate further public
  examples only when connector role and intended connectivity can be resolved
  from an independent public pinout or an explicitly synthetic requirement.
  Record owner disposition, confirmed defects, valid alternatives, seeded
  misses, and review effort before changing policy or claiming detection gain.

### Recorded trial: kicad-happy LED checks on public template examples (2026-10-03)

- **Candidate and installation:** `aklofas/kicad-happy` at commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT. The tested
  `skills/kicad/scripts/analyze_schematic.py` SHA-256 is
  `beea21348a0794bd3ce02ea85cb537ff8efe7e63bad70bc7773d7bbe4e484315`.
  This used the GitHub checkout and Python 3.11 directly; no package or
  dependency was installed. Candidate reports and the local report were saved
  under ignored `build/cohort-public-led-review-20261003/`. No project source
  or candidate code was copied into Tooling.
- **Inputs and repeatability:** Read-only screening of the clean public
  KiCad-Team-Workflow-Template at commit
  `ed89536f0dbbcb013145af2994fef41b2250143e`. The Arduino status LED schematic
  SHA-256 is
  `c2d8442412cb251472a08df31109b8633655aaa375598abbb2e7bbc00961fa1b`; the
  controller is
  `bd3f349233ffc44f030b1004a1c08e51d1ec0589ecf646384f1ed3353806e5ad`; the
  Raspberry Pi status LED is
  `b99ad47237f3f36aaefa3a2ed08e3dae12d9131c7f9a52355401c9d5bada3fba`. Each
  invocation used `--no-hierarchy --only-deterministic --compact`; the two
  reports for each input were byte-identical. First/repeat report SHA-256:
  Arduino `797c5d818dec18a4c68d38a829a0ce5c3b75d5c246cd524e729410ea18751619`,
  controller `773c0ebd0dad02a626547d6c3249140b62f391872c89bf412553cde5dde6298a`,
  Raspberry Pi
  `037a0b84f8119dc75983fe27eaad5924954acbd8566f29aec4a3d52798b79e8e`.
- **Observed result:** Both LED examples emitted `LA-AUD` INFO findings naming
  `D1`, `R1`, and a 1000 Ω resistor with `drive_method=resistor_limited`. Each
  same report also emitted heuristic-error `LR-001` for D1, claiming there is
  no series current-limiting resistor. Their public design notes independently
  describe GPIO → 1 kΩ R1 → D1 → ground. Source review of this candidate
  revision confirms `LR-001` accepts an adjacent resistor only when its other
  net is classified as a power or ground rail; the valid GPIO-side resistor
  ends at a signal net. The controller example had no LED and no LR-001 prompt.
- **Local comparison:** The Arduino example has no custom-LED PART_ID role map,
  so local LINT-063 is not applicable. The current source-bound local report
  used the same schematic SHA and KiCad 10.0.5 netlist SHA-256
  `900a175d05b135f37bdd582cc07e83e637b0933b3fe99713e74b0615ff1ad5cf`; it has
  zero heuristic findings and `REVIEW` status because connector inventory is
  `UNDECLARED`. Its retained native summary status is `FAIL`, so this is not a
  clean project result. The report SHA-256 is
  `ac46ee1b8444f43b25202cecad9d7ad774b4098ab24888fcc4fb81aff902bb51`; the
  source-matched native summary SHA-256 is
  `1cea5943ae950f150c78443c8a168e1922da709f072740c63029b90489f135fa1`.
- **Incremental-value result:** `LR-001` did not add a valid detection; it
  produced a repeatable false positive on two documented series-resistor
  controls, and its own `LA-AUD` output contradicted it. `LA-AUD` did provide
  concise resistor-reference/value context, but the benefit over the native
  netlist and project documentation was not measured. Do not adopt the
  candidate check, its error severity, or its generic resistor recommendation.
  Keep a local rule conditional on exact supported component roles and
  source-bound connectivity evidence.
- **Boundary:** This is one public template revision with two similar training
  examples and one no-LED control. It does not estimate field precision,
  false-negative rate, reviewer effort, or behavior on other resistor
  placements. It does not establish current adequacy, LED ratings, or hardware
  safety.

### Methodology review: kicad-happy-testharness

- **Source:** The public
  [testharness README](https://github.com/aklofas/kicad-happy-testharness)
  and [methodology](https://github.com/aklofas/kicad-happy-testharness/blob/main/methodology.md)
  were read on 2026-09-30. The inspected `main` revision was not pinned and the
  harness was not installed or run.
- **Observed practice:** Its documentation says corpus baselines primarily
  measure consistency rather than correctness, and describes a correctness
  layer with parser verification, synthetic detector fixtures, a small curated
  gold tier, metamorphic tests, and property invariants.
- **Incremental disposition:** Adopt only the test-method idea through
  LINT-054. The LINT-050 parser now has a synthetic metamorphic pilot: both
  orderings of conflicting suffixed pin keys produce `BLOCKED` coverage. This
  is local test evidence, not a result from the candidate harness.
- **Boundary:** No candidate code, corpus project, analyzer baseline, output,
  or project fixture was copied. The harness license and runtime behavior were
  not evaluated because no dependency or source reuse is proposed. A large
  open-source corpus or a passing seeded baseline is not treated as independent
  correctness evidence.

### First-party public reference-template applicability replay (2026-10-01)

- **Corpus and source boundary:** Read-only native verification used the public
  reference-template checkout at commit
  `5ca79bedf665a9b6577d96b1d47f13ccd518c968`. The four selected example
  projects were `arduino-uno-status-led`, `controller`,
  `passive-signal-reference`, and `raspberry-pi-status-led`. No project source
  was copied into Tooling or changed; all generated receipts are under the
  template checkout's ignored `build/` directory.
- **Tooling and native pins:** The Tooling checkout was at `cbaed9b` with uncommitted goal changes.
  Its runtime source closure was recorded as SHA-256
  `3d28fc31b5d6273e803b2a180afd410f52e24b157688e0936570d289bc178431` over `pyproject.toml` and the
  sorted `.py`, `.json`, `.in`, and `.txt` files under `kicad_tooling/`. The 162-file digest hashes
  each relative path, NUL, file bytes, and NUL, with `pyproject.toml` first and package files in
  sorted path order. Native runs used each project's catalogued image: KiCad 10.0.0
  (`ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`)
  for `controller`, and KiCad 10.0.5
  (`ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`)
  for the other three projects.
- **Invocation and repetition:** Each project ran twice through
  `kicad-team verify --depth native --runner container`, using fresh receipt directories. Both runs
  had identical project source-hash maps, parsed `NetlistContract` values, lint findings,
  connector-coverage state, and next action. The raw netlist SHA changed on every repeat because
  KiCad writes a timestamp into `<design><date>`; after replacing only that element, all four raw
  XML pairs were byte-identical. The report intentionally retains the hash of the exact native
  artifact; the timestamp does not change the parsed evidence or the deterministic lint decision.
  Table digests are SHA-256 over sorted, compact JSON from
  `read_netlist(...).model_dump(mode="json")`.

  | Public example             | KiCad  | Lint   | Findings | Connector coverage        | Parsed-netlist SHA-256 prefix |
  | -------------------------- | ------ | ------ | -------- | ------------------------- | ----------------------------- |
  | `arduino-uno-status-led`   | 10.0.5 | REVIEW | 0        | UNDECLARED (`J1`)         | 50085baec78f4726              |
  | `controller`               | 10.0.0 | REVIEW | 0        | UNASSESSED (no candidate) | c42f2a6ba6b4230b              |
  | `passive-signal-reference` | 10.0.5 | REVIEW | 0        | UNASSESSED (no candidate) | d893aaecc8176cc3              |
  | `raspberry-pi-status-led`  | 10.0.5 | REVIEW | 0        | UNDECLARED (`J1`)         | 099a7c3df72d1d37              |

- **Interpretation:** The reports surfaced explicit connector-inventory
  coverage gaps and emitted no heuristic candidate on these four examples.
  `UNASSESSED` is not a reviewed no-interface decision. All four overall native
  verification runs ended `FAIL` and had `DESIGN_LINT.REVIEW` as a blocking
  finding; `passive-signal-reference` also lacks an independently authored
  native component/net contract. These training examples have no owner disposition
  for the lint coverage questions, so this replay is neither a clean-pass
  corpus nor a false-positive or missed-fault measurement. It found no design
  defect and provides no basis to promote or suppress a rule.
- **Local evidence:** Full source maps, exact raw and parsed netlist hashes,
  reports, and native command receipts remain at
  `build/ci/acceptance-template-5ca79bed/build/design-lint-public-template-5ca79bed/`
  in the Tooling checkout. This local result is development evidence from a
  dirty source tree, not a release benchmark. Repeat on a clean Tooling
  revision and add owner-reviewed, non-proprietary examples before measuring
  field precision or reviewer effort.

### Source recheck: ThomsonLint KiCad exporter

- **Source:** The public
  [KiCad review guide](https://github.com/holla2040/ThomsonLint/blob/main/docs/KiCad_Review_Guide.md)
  and repository README were read on 2026-09-30. The inspected `main`
  revision was not pinned; no candidate code, example, or project export was
  copied.
- **Observed workflow:** The guide documents a standalone KiCad 9/10 exporter
  and says its export step has no external Python dependencies. It emits
  schematic and board JSON with classifications and precomputed summaries
  such as decoupling proximity, widths, trace lengths, and plane layers. Its
  findings step is AI-assisted and uses those exports together with images or
  PDFs; the guide describes this as the review workflow rather than a
  deterministic command-line lint result. The repository declares MIT, while
  the broader reporting workflow lists separate JSON-schema and AI-driver
  requirements.
- **Incremental disposition:** This is useful as engineering-rule and export
  coverage input, but it does not demonstrate an independently reproducible
  lint finding. The relevant deterministic metrics already have source-bound
  local checks or project-authored contracts in LINT-020 through LINT-025.
  Do not add an analyzer dependency or treat an AI finding as a verification
  gate. The bounded exporter-only trial below checks metric extraction and
  repeatability separately from lint detection.
- **Boundary:** The trial covers only synthetic KiCad 10 board fixtures. It is
  not a general parser conformance or maintenance-cost benchmark, and no
  project data was supplied.

### Recorded trial: ThomsonLint board metrics export (2026-10-03)

- **Candidate and install:** Public `main` was pinned at commit
  [`8e9099a6cd88d05b1e1723038b1e22a5cc4592e1`](https://github.com/holla2040/ThomsonLint/commit/8e9099a6cd88d05b1e1723038b1e22a5cc4592e1);
  its standalone exporter reports version `1.0`, and
  `tools/kicad-export.py` SHA-256 is
  `39ad24da80d76c063bce23f9e619e3496e6292a86e5d132a818aa4c6333a9d09`.
  The candidate declares MIT in `LICENSE` (SHA-256
  `ede2d1df7b44ba6fe6e49c445404e5a1f650c2ad8b3396a2a363da5df4b54fe1`).
  The trial used a shallow Git checkout and the system Python standard library;
  it installed no package or additional dependency. No candidate source was
  copied into Tooling.
- **Method:** Ran the candidate's documented CLI twice per fixture over the
  seven Tooling-owned boards in
  [`differential-pair`](../tests/fixtures/design_lint/differential-pair/README.md):
  `python3 tools/kicad-export.py <case>.kicad_pro --output <output-dir>`.
  Temporary projects contained only the selected `.kicad_pcb` plus a generated
  empty `.kicad_pro`; receipts are under ignored
  `build/research/lint031-thomsonlint-v1.0/`. After removing only the volatile
  top-level `export_date`, both runs produced identical JSON for all seven
  boards. Output hashes below are SHA-256 of compact, sorted-key JSON after
  removing only that field; source hashes cover the original fixture bytes.
  The candidate parsed the fixture's KiCad 10 board format. To reproduce the
  candidate checkout, clone
  `https://github.com/holla2040/ThomsonLint.git` at depth 1 and detach at the
  recorded commit, then run the stated CLI once per case and compare two
  exports using that normalization.
- **Observed extraction:** The control exported `USB_D_P` and `USB_D_N` at
  20.0 mm each and 0.3 mm width. The width fault exported 0.1 mm minimum and
  maximum width for both nets. The skew fault exported 20.0 mm and 20.5 mm;
  the uncoupled and gap cases retained the expected per-net lengths and widths.
  The `no-rules-skew` and `no-rules-gap` exports were semantically identical to
  their corresponding physical boards because the candidate consumes the PCB
  file and does not read the project's `.kicad_dru` rules.
- **Fixture and output digests:**

  | Case              | Fixture source SHA-256                                             | Normalized output SHA-256                                          |
  | ----------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
  | `control`         | `aa2ead4fa9c9f707db2e82ecf0cd05e43ab0f37a09535122f1803065a9b95f72` | `70f3f33b1440eec75e685c77e6bd2a36c0ee4c8315c2c97816acec6671d63993` |
  | `fault-width`     | `18156288673b79532e0576b656b22ee0c56e79fe836ee8a41d3300a16a954146` | `b0bf8bc57158166f6eb0f554113035bae5fe6823dffe7e3c78c03f8ca91988fd` |
  | `fault-gap`       | `461d70ff5412252500d42f07bb87cc21e895453a9e1ffbe0e10eb1a8f03567d1` | `488f8c24b4a12cb43c687a9cce383ad32988fbe05b791b5acbb9c780dc0cd79f` |
  | `fault-skew`      | `96e696451b3f795830f20672c1223acdae1f3c54289e6d12da71f9706e912709` | `8cd4e82da7291f5400851179b16876be8d579a479f3565336727f96909d1347d` |
  | `fault-uncoupled` | `7ef76bbe9000cfdd29cf473e34a5f784d0db7356a48d3180f36cd08cf1afeb64` | `118abe67319b7bcf80ef1fb1d43187594fc2a84cbb9dbc526da27af0f917c3ea` |
  | `no-rules-skew`   | `96e696451b3f795830f20672c1223acdae1f3c54289e6d12da71f9706e912709` | `8cd4e82da7291f5400851179b16876be8d579a479f3565336727f96909d1347d` |
  | `no-rules-gap`    | `461d70ff5412252500d42f07bb87cc21e895453a9e1ffbe0e10eb1a8f03567d1` | `488f8c24b4a12cb43c687a9cce383ad32988fbe05b791b5acbb9c780dc0cd79f` |

- **Incremental value:** The exporter made the seeded width and skew values
  visible, but emitted no lint findings or rule severities. It does not compare
  pair spacing or uncoupled length, and it cannot distinguish a board with an
  authored design-rule limit from the same geometry without one. The existing
  pinned native DRC fixture lane reports the authored width/skew violations
  directly; this exporter-only trial did not run native DRC. Unique
  deterministic findings: zero. Duplicate lint findings: zero. False-positive
  rate and reviewer effort: not measured because the exporter emitted no
  findings.
- **Disposition and limit:** Do not adopt this exporter as a lint engine or
  runtime dependency. It can serve as a basic geometry-export example, but this
  fixture trial demonstrates no detection or review gain over the existing
  native evidence. The seven-case extraction replay is not broad parser
  conformance, and no general maintenance-cost estimate was made.

### Source recheck: kicad-happy EMC decoupling metrics

- **Source:** The public
  [EMC pre-compliance guide](https://github.com/aklofas/kicad-happy/blob/main/emc-precompliance.md)
  was read on 2026-09-30. The inspected `main` revision was not pinned; the
  detector implementation was not benchmarked in this recheck.
- **Observed concept:** The guide groups DC-001 through DC-003 under PCB
  decoupling and describes capacitor-to-via distance as a connection-inductance
  review signal. It lists PCB evidence as required, but does not establish a
  project-independent distance limit.
- **Incremental disposition:** Extend LINT-020 with an optional project-owned
  capacitor-return-pad to native-connected-via distance limit. Synthetic cases
  distinguish connected and unconnected nearby vias, and pinned KiCad 10.0.0/
  10.0.5 fixture lanes validate a boundary control and moved-via fault. The
  local rule reports geometry only and does not claim an inductance estimate.
- **Boundary:** This is a concept review, not a runtime comparison against the
  cohort analyzer. No candidate code, report, board, threshold, or project
  fixture was copied. No cohort dependency was added.

### Source recheck: kicad-happy v2.2.1 CAN and determinism notes

- **Source:** The public
  [v2.2.1 release](https://github.com/aklofas/kicad-happy/releases/tag/v2.2.1)
  and matching changelog were read on 2026-10-01. The release notes identify
  protocol checks for CAN and a hash-order audit that compares repeated
  analyzer outputs with varied Python hash seeds.
- **Observed scope:** The CAN protocol family checks protocol-specific
  electrical parameters; the release note does not describe the local
  cross-peer net-assignment predicate. The hash-order audit is a consistency
  guard, not an independent correctness oracle.
- **Incremental disposition:** LINT-067 adds a first-party review prompt for
  complete source-bound CANH/CANL peer pairs that share one side but split the
  other. Synthetic fault/control netlists establish the bounded behavior, and
  native repeated KiCad 10.0.0/10.0.5 exports with zero ERC errors and known
  isolated-library warnings establish its evidence boundary. No candidate
  source or fixture was copied; the cohort was not installed or
  runtime-benchmarked for this finding.
- **Boundary:** Release notes are source inspection, not a trial of the
  candidate CAN detector. The local prompt cannot infer bus intent, electrical
  correctness, or physical continuity.

### Source recheck: kicad-happy v2.3.0/v2.3.1 determinism update (2026-10-07)

- **Source:** The public
  [changelog][happy-changelog] now lists v2.3.1, released 2026-10-06. Its
  v2.3.0 entry records hash-seed-dependent output fixes and a three-seed
  determinism gate over each analyzer.
- **Incremental value:** This adds a reusable verification method, not an
  electrical finding. LINT-080 applies it to complete synthetic DB9 fault and
  common-return reports, same-net diode fault and distinct-net control
  reports, and generic peer-pin outlier fault/common-net control reports under
  three independent Python hash secrets. The same
  v2.3.0 entry adds `SP-001` for same-net two-pin passives or diodes. LINT-051
  covers resistor, capacitor, and inductor families; its diode family was a
  specific coverage gap. LINT-081 adds only exact `Device:D` family support as
  a local review rule; no candidate code or fixture was copied and no runtime
  dependency was added.
- **Boundary:** This was source inspection only. No kicad-happy version was
  installed or run for this update; no cohort code, fixture, or project design
  was copied. LINT-080 is first-party test code; its present matrix covers
  synthetic connector-return, peer-pin assignment, and same-net diode reports.

### Recorded trial: kicad-happy v2.2.1 CAN output on peer fixtures

- **Candidate:** The public kicad-happy v2.2.1 archive declares MIT. The
  extracted archive has no Git metadata; its SHA-256 is
  `dc770679619e3dc90b7cc97cf27342500a21ddd148119605f3a9db1576f0c5b6`.
  Tested analyzer files are pinned by SHA-256: `analyze_schematic.py`
  `beea21348a0794bd3ce02ea85cb537ff8efe7e63bad70bc7773d7bbe4e484315`,
  `validation_detectors.py`
  `b4f0b0deb0ce4bd5c598840f3cdc1eaceced883fc2929d7e7a1a9c0a27acbfc9`,
  `detector_helpers.py`
  `68fdc890755b53be1e25f5a7d07f72a2a8ca30dc5b0b67f4e2dfafebbe4ebc63`,
  and `kicad_types.py`
  `2e12971ba2bff4ff5b221697dbf79400b27e3aef8c3896be64e9497c27814c44`.
- **Inputs and data boundary:** Used only the Tooling-owned synthetic
  `tests/fixtures/design_lint/can-peer-native/peer-control.kicad_sch` and
  `peer-fault.kicad_sch`. Candidate-only scratch copies replace the three
  transceiver `Value` strings with `SN65HVD230` so its CAN device keyword
  matcher recognizes them; the source fixtures remain unchanged. Scratch
  schematic hashes are control
  `1a47ddbd4605e549c73a1c9bfd876a4b5891e89d39233bcdecce2d73d74113bd` and
  fault `37e3184d9e461140db306fa264e97f3cd607ecebe7fbdedc14380615a87c7fb8`.
  Both include direct 120R termination across their assigned CANH/CANL pairs.
  All candidate inputs and output reports stayed under `/private/tmp`; no
  project source or candidate code was copied into this repository.
- **Invocation:** Ran the candidate's deterministic schematic script directly
  without installation or lifecycle/network checks:

  ```sh
  python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
    "$FIXTURES/control.kicad_sch" --no-hierarchy --only-deterministic \
    --output "$OUT/control.json"
  python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
    "$FIXTURES/fault.kicad_sch" --no-hierarchy --only-deterministic \
    --output "$OUT/fault.json"
  ```

- **Observed result:** Both candidate outputs repeated byte-for-byte on a
  second run. Control output SHA-256 was
  `c01fbfcebe833c89b5ef0c01671b5bc091b44470581b0aadb412f83afe3752e5`; fault
  output SHA-256 was
  `2c4ab6cecb32d904cba1cc1b72ca9adc102e1a697cbb1e8a4afda32a5b990375`.
  Neither JSON report exports the documented `PR-003` validation findings.
  Instead, `protocol_compliance.findings` reports the same CAN “missing 120Ω”
  issue for both cases with `nets: ["", ""]`, `has_termination: false`, and
  `termination_ohms: null`. The general finding list contains only `DS-001`,
  `SS-001`, and `LC-007`. The protocol message therefore does not distinguish
  the valid control from the peer-assignment fault and misstates the visible
  termination evidence.
- **Incremental-value result:** No useful CAN detection or localization was
  demonstrated through the candidate's JSON interface. The output is a
  reproducible false positive on the control, not an independent confirmation
  of LINT-067. Retain no candidate dependency for this capability; the local
  `bus.can_peer_assignment_divergence` rule remains the deterministic
  review-localization check, with bus intent and physical continuity left to
  project requirements and PCB evidence.
- **Limit:** This is one synthetic symbol-library representation and one
  deterministic CLI mode. Other symbol libraries, analyzer modes, termination
  topologies, and reviewer effort remain unmeasured. No claim is made about
  field false-positive rates or all kicad-happy protocol checks.

### Recorded trial: kicad-happy EMC protection-via heuristic

- **Candidate:** The local read-only kicad-happy archive reports v2.2.1 in its
  [changelog](https://github.com/aklofas/kicad-happy/blob/main/CHANGELOG.md).
  Its extracted source has no Git metadata, so the exact tested
  scripts are pinned by SHA-256: `analyze_pcb.py`
  `546acfa4218716c1db41d5bda66ab1a2ee7aeac4f723e188bc64b382b7bc7674`,
  `analyze_emc.py`
  `b79b5f6f27b0e62c42f1f158521a3242fa581b3658b68ceab1e7b683b4404203`,
  `emc_rules.py`
  `5389056387238a9d2aed224ec54f40b4eb7b2e3dbe1d766975fb2adff1aea3a8`,
  and `finding_schema.py`
  `0b3ecaf9d647d4e69ff31c321d314d0fcd49fadceb6d6ad718cd46d3c29ece49`.
- **Invocation and data boundary:** Ran the direct Python 3.11 PCB and EMC
  analyzer scripts without installing a package or adding a runtime
  dependency. The input was the tooling-owned
  `pcb-protection-entry-path.kicad_pcb` fixture plus a minimal synthetic
  protection-device finding; outputs and the disconnected-via mutation stayed
  under `/private/tmp`. The control board SHA-256 is
  `64d0393d7951420eb6cadaf4c4b7c788cbadc1f7d39a3b6fb071f7a56ab8115c`; the
  moved-via fault board SHA-256 is
  `35146571c21782790cc147f05d97a5a38bfcbda9491620692bafe77063ae9970`.
- **Observed result:** The candidate emitted the same `ES-002` info finding
  (“Single ground via near ESD device D1”) for both boards. Its heuristic
  counts a net-name-classified ground via inside 3 mm of the TVS footprint
  origin; it does not verify that the via shares copper with the mapped
  reference pad. The fault via is 1.5 mm from the exact D1.2 pad and 2.5 mm
  from the D1 footprint origin, so it remains inside both geometric radii but
  is disconnected from D1.2. This is the published
  [ES-001/ES-002 category](https://github.com/aklofas/kicad-happy/blob/main/emc-precompliance.md)
  exercised with a mapped synthetic fault. The candidate emitted no `ES-001`
  finding for the 0.65 mm connector/protector placement.
- **Local comparison:** The project-authored map reports one native-connected
  reference via and `COMPLETE` on the control. On the moved-via fault, the
  KiCad 10.0.0 and 10.0.5 native lanes report zero connected reference vias
  within the authored 2 mm pad-centered radius and `INCOMPLETE`; the fault
  snapshot is repeated and source/version/image bound. Repeated candidate EMC
  runs produced identical ES-001/ES-002 summaries for each input.
- **Incremental-value result:** The candidate adds no unique detection. Its
  single-via advisory duplicates an intentionally configured minimum of one
  on the valid control, while it misses the nearby-but-disconnected-via fault
  that the local map catches. Retain the bounded hypothesis and native
  regression; do not adopt the analyzer or its universal 3 mm threshold.

### Recorded trial: kicad-happy schematic analyzer

- **Candidate:** `aklofas/kicad-happy`, commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT license.
- **Invocation:** Ran its `skills/kicad/scripts/analyze_schematic.py` directly
  with Python 3.11 and `--output` into `/private/tmp`. No package install or
  analyzer dependency install was needed for this path. The checkout and all
  generated reports stayed outside this repository; no cohort code or board
  data was copied into Tooling.
- **Inputs:** Six existing synthetic `.kicad_sch` fixtures from
  `tests/fixtures/design_lint`: pin-line near-miss fault/control, pin tip on
  wire interior with/without a junction, and unmarked/marked orthogonal wire
  crossings. All six invocations completed and emitted parseable JSON.
- **Observed output:** Every fixture produced five total analyzer findings,
  including two generic `NT-001` single-pin-net findings. Those same two
  connectivity findings appeared on both fault and control fixtures, so they
  did not distinguish the tested geometry regressions. The unmarked-crossing
  and junction-marked-crossing cases had identical connectivity findings; no
  crossing-specific finding was emitted. For the pin-line and pin-interior
  fault cases, the parser represented the nearby named label as a named net
  with zero pins, while the controls had that label on the pin net. This is
  reviewable raw extraction evidence, but the analyzer did not turn that
  difference into a localized near-miss diagnostic. Datasheet-coverage,
  sourcing, and lifecycle messages were unrelated to these electrical
  fixtures and were excluded from the comparison.
- **Incremental-value result:** No unique actionable lint detection was
  demonstrated on this fixture set. Raw net extraction may help a reviewer,
  but reviewer effort was not measured and the existing source-bound
  geometry rules already provide more specific coordinates and wire IDs.
  This trial does not justify adopting the analyzer or adding it as a runtime
  dependency. It does not evaluate PCB checks, hierarchical sheets, or
  connector-ground distribution.
- **Still unmeasured:** Full install workflow, supported KiCad version matrix,
  output stability across releases, reviewer effort, maintenance cost, and
  broader connector/power-pin behavior. One synthetic generic two-peer
  connector fault/control pair is measured in the follow-up below; keep the
  remaining fields open rather than extrapolating from these direct script
  runs.

### Follow-up trial: kicad-happy generic connector single-pin findings (2026-10-03)

- **Candidate and install:** Public `aklofas/kicad-happy` was checked out from
  GitHub at commit
  [`a6bba1add1e18b89e3aa0824b9769ed1d9d79174`](https://github.com/aklofas/kicad-happy/tree/a6bba1add1e18b89e3aa0824b9769ed1d9d79174);
  its repository declares MIT. The tested
  `skills/kicad/scripts/analyze_schematic.py` SHA-256 is
  `beea21348a0794bd3ce02ea85cb537ff8efe7e63bad70bc7773d7bbe4e484315` and
  `LICENSE` SHA-256 is
  `f542344efc2d21d18c81507e8168ab256c32ece6e7acb1bc8bde71950c9b6bb5`.
  This used a direct GitHub checkout and the active Python 3.11 interpreter;
  no package or runtime dependency was installed. The checkout and reports
  stayed under `/private/tmp`, and no cohort code was copied into Tooling.
- **Inputs and invocation:** Ran twice per input with
  `analyze_schematic.py <fixture> --no-hierarchy --only-deterministic
  --compact --output <report.json>`. The inputs are the tooling-owned
  `two-peer-open-fault.kicad_sch` and
  `two-peer-common-control.kicad_sch`; their SHA-256 values are recorded in
  the [fixture notes](../tests/fixtures/design_lint/generic-peer-pin-assignment-native/README.md).
  The four JSON reports parsed successfully and each same-input pair was
  byte-identical: fault output SHA-256
  `8ae9bcf67b9620b3a8acbc6419b164dcd1216e8b1a2f517d69d777fc93df4f12`,
  control output SHA-256
  `9b9144d1f91f0557a2866e9de27ce296003abd9240675a9135fb7ee1e12ecce1`.
- **Observed result:** On the open-contact fault, deterministic rule `NT-001`
  emitted INFO findings for `J2.1` on `__unnamed_0` and for `J1.1` on the
  single-pin `+5V` net. The common-net control emitted neither `NT-001`
  finding. Unrelated datasheet, ESD, rail-source, sourcing, and lifecycle
  findings were excluded. The reports contained seven total findings on the
  fault and four on the control; the count difference came from the two
  connectivity findings and one topology-dependent ESD audit.
- **Source review:** At this pinned revision, `NT-001` skips nets marked
  `no_connect` and pins whose native type is `no_connect`, `free`,
  `unspecified`, or `unconnected`. The explicit-marker path has the synthetic
  follow-up below; the native pin-type exclusions still lack fault/control
  coverage.
- **Explicit no-connect control (2026-10-03):** A temporary derivative of
  `two-peer-open-fault.kicad_sch` placed a native no-connect marker at `J2.1`
  (`106.68, 104.14` mm); the derived source SHA-256 is
  `0ffbf3d600e64d5b4bf7b8caab9039553314ee829fd136b30aa2e9bed6bdf77e`. The
  same pinned analyzer and deterministic-only command ran twice. Both reports
  had SHA-256
  `c826cf174aecb54934e067fa163bf20f797803b3f485d6ca52e06c2712614615`, emitted
  no finding for `J2.1`, and retained only the `NT-001` prompt for `J1.1` on
  `+5V`. This confirms the candidate's explicit-no-connect exclusion for this
  synthetic input; it is not a KiCad-native export or proof that the remaining
  singleton prompt is useful. The direct candidate invocation had no project
  interface or off-board source map.
- **Local comparison and disposition:** The tooling-owned fixture specification
  expects `J2.1` to produce `connector.peer_pin_assignment_outlier` with REVIEW
  and the common-net control to clear that rule. The focused local regression
  `test_two_peer_open_generic_contact_prompts_and_supports_exact_ignore`
  passed (1 test). Therefore `J2.1` is a corroborating duplicate, not a new
  detection. `J1.1` is a possible coverage prompt for a singleton external
  endpoint, but the pair does not establish whether it should connect to a
  local source. The candidate's explicit no-connect derivative suppresses its
  `J2.1` prompt while retaining the `J1.1` singleton prompt. The local
  `NetlistContract` records assigned and unconnected pins but has no native
  no-connect-marker field, so its current peer rule cannot distinguish an
  explicitly marked open contact from a wire-open contact. The source-bound
  native marker case is now part of the fixture lane and keeps the REVIEW
  finding on both pinned versions. A marker alone does not resolve peer intent,
  so keep that conservative prompt. The off-board serial and repeated-child
  sheet comparisons below add no unique detection beyond authored interface
  coverage, native ERC, and the local source-bound geometry check. Do not adopt
  a general singleton-net REVIEW rule from this candidate. Additional singleton
  trials need a named scenario where current source-bound checks miss a defect.
  The open test-point result is recorded below and duplicates native ERC. Do not
  adopt candidate code, its wording/severity, or a runtime dependency from this
  trial.
- **Valid off-board endpoint control (2026-10-03):** Added the synthetic
  `single-offboard-port-control.kicad_sch` fixture (SHA-256
  `ceaa7038e372ec74a00f7e7c2cb5311377df01624760ab555adb413c4e02d8e9`). Its
  independent interface record declares J1.1 as an external 5 V input and
  J1.2 as its off-board return. At the pinned kicad-happy commit and script hash
  above, two `--no-hierarchy --only-deterministic --compact` runs were
  byte-identical (report SHA-256
  `d661679b9fa63ae336062b8b2ef135e0fef0a5e7b06a846fbeabcf1e8aeead2e`):
  `NT-001` emitted INFO for both J1.1 (`+5V`) and J1.2 (`GND`) because the
  candidate has no project interface or external-source mapping.
- **Source-bound local result:** The same schematic was exported twice using
  digest-pinned KiCad 10.0.0 and 10.0.5. Parsed normalized contracts were
  repeatable and cross-version identical (SHA-256
  `453a8f7b74958209e704257212a1e96d651c5df107ec6d8c2bef08d21ce3dfbc`). A
  synthetic interface catalog and complete connector-inventory review produced
  `coverage_status=COMPLETE`; local design lint returned PASS with no findings
  on both versions. The 10.0.0 raw XML differed between repeat exports, while
  the typed normalized contract remained identical. Native lane evidence and
  the fixture remain tooling-owned; no candidate code or project data was
  copied. The machine-readable run summary is retained under ignored
  `build/ci/cohort-singleton-net-lint/trial-evidence.json`.
- **Connected UART peer comparison (2026-10-03):** Ran the same pinned analyzer
  twice on synthetic `serial-peer-native/endpoints.kicad_sch`
  (SHA-256 `7f3e44ba24ba70b382939fa6504ff635b6bb56292b5bcbc36dee307166378060`).
  Both reports were byte-identical (SHA-256
  `f786d703847396e99c385d1ccc60a47f8884aa170c287f04ce51aa83b0908c60`) and
  emitted no `NT-001` findings because each TX/RX net has two connected pins.
  The existing source-bound native serial lane passed on KiCad 10.0.0/10.0.5:
  its undeclared and partial peer maps return REVIEW, while the complete authored
  map passes. This connected-endpoint sample adds no singleton-net detection;
  it does not cover an off-board serial port whose signals are singleton nets.
- **Open test-point/connector comparison (2026-10-03):** On the synthetic
  connector-inventory control, `NT-001` reported U8.1 on `__unnamed_0`; on the
  open connector fault it reported U7.1, U7.2, and U8.1. Two analyzer runs per
  fixture were byte-identical. Pinned KiCad 10.0.0 and 10.0.5 ERC reports for
  the same sources contain `pin_not_connected` errors for exactly those pins.
  The normalized violation content repeats across runs after excluding the
  report date. The source-bound connector-inventory lane passes on both exact
  versions: it marks the connector fault UNDECLARED and the test-point-only
  control COMPLETE, since standard test points are intentionally outside
  connector inventory. This cohort result duplicates native ERC and adds no
  unique detection. Synthetic library-configuration warnings are excluded from
  the pin comparison. Full inputs, hashes, tool images, and normalized ERC
  receipts are in ignored `build/ci/cohort-singleton-net-lint/trial-evidence.json`.
- **Repeated-child-sheet hierarchy comparison (2026-10-03):** Ran the pinned
  analyzer twice with hierarchy discovery enabled and deterministic rules only
  on the tooling-owned repeated-sheet fault and junction-marked control. The
  four source hashes are recorded in ignored
  `build/ci/cohort-singleton-net-lint/trial-evidence.json`; fault and control
  reports were byte-identical across repeats (SHA-256
  `d61c88cc8f79cf93504784335e5e2732dfcd6f54b1b9f360ae3c086cfee809b7` and
  `674c9e1b072858292bdd82236afe3f50ef28dacbb4e815855f2d4189f6fcc7f2`). On the
  fault, `NT-001` reports R1.1/R1.2 and R2.1/R2.2 as singleton nets. Native
  KiCad 10.0.5 and 10.0.6 repeated-sheet regressions confirm that R1.2/R2.2
  are the two open instance pins, while R1.1/R2.1 sit on separate instance
  `CONTROL_NET` nets. The source-bound geometry scanner reports both missing
  T-junctions and native ERC identifies the shared open source pin; both
  controls are already localized without a generic singleton warning. The
  candidate is quiet under `NT-001` on the marked control, where its separate
  `SP-001` findings describe the fixture's deliberately joined resistor pins.
  This is an analysis fixture, not a product circuit. The trial adds no unique
  singleton-net detection and leaves the relevance of the label-only singleton
  prompts dependent on independently stated intent.
- **Off-board UART singleton (2026-10-03):**

  Added synthetic `offboard-endpoints.kicad_sch` and an independently authored serial map that
  declares J1/J2 as direct peers and J3/J4 as external peers. At the pinned kicad-happy commit, two
  deterministic-only runs were byte-identical (report SHA-256
  `4bbbf30c8269cae0341440403413d71711dc4afd67303f2c19145817c604ac6c`) and `NT-001` reported
  J3.1/J3.2/J4.1/J4.2 on their four singleton TX/RX nets. Repeated native KiCad 10.0.0 and 10.0.5
  exports preserve those one-pin nets and the direct J1/J2 pairings; their normalized pin-to-net
  digest is `84d802852f07682498bcd80c690f158f70f1324a412facc3b144979f9d4272f4`. ERC reports four
  `isolated_pin_label` warnings on exactly those labels and no `pin_not_connected` items; remaining
  ERC findings are synthetic symbol, footprint, and grid issues. The new local regression loads the
  authored external map and confirms `bus.serial_unmapped_peer` suppresses J3/J4 only; it runs on a
  synthetic typed netlist, while the separate native exports bind the schematic pin functions and
  net assignments. The singleton candidate adds no unique detection. This fixture has no reference
  pins and says nothing about whether either external serial port must share board ground. Source
  and map digests, exact images, repeat hashes, and native results are recorded in ignored
  `build/ci/cohort-singleton-net-lint/trial-evidence.json`; fixture details are in the
  [serial-peer README](../tests/fixtures/design_lint/serial-peer-native/README.md).
- **Incremental-value decision:** This is a valid false-positive control for a
  general singleton-net warning: both contacts are documented external
  endpoints, yet the cohort rule still prompts. The source-bound local path
  reports connector coverage UNDECLARED and lint REVIEW when the project map is
  absent; with the complete map, coverage is COMPLETE and no local electrical
  finding is warranted. The connected UART sample is quiet, the open
  test-point/connector and off-board serial findings duplicate native ERC, and
  the repeated-sheet fault is already localized by source-bound geometry and
  native ERC. Do not add a general singleton-net rule based on these trials.
  Broader hierarchy styles remain unmeasured; any further singleton trial must
  name a defect class that current source-bound connector, serial roster,
  geometry, and ERC checks do not cover.
- **Boundary:** This is one synthetic fault/control pair at one candidate
  commit. It measures one repeated-child-sheet case, not all singleton
  topologies or hierarchy styles. Reviewer effort, field precision, and
  maintenance burden remain unmeasured; the findings do not justify treating a
  singleton net as an electrical defect.

### Recorded trial: kicad-happy VM-001 voltage-domain heuristic

- **Candidate and provenance:** `aklofas/kicad-happy`, commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, v2.2.1 changelog, declared MIT. The extracted archive
  had no Git metadata. The exact tested `validation_detectors.py` and `LICENSE` hashes, plus both
  fixture hashes, are recorded in the
  [synthetic fixture notes](../tests/fixtures/design_lint/cohort-peer-voltage/README.md).
- **Invocation:** Ran `skills/kicad/scripts/analyze_schematic.py` directly
  with Python 3.11 isolated mode and `--no-hierarchy --only-deterministic
  --compact`. No package was installed. The detector's datasheet lookup helper
  was unavailable in the isolated interpreter; no cached device facts affected
  the result. Reports remain under ignored `build/ci`.
- **Inputs and output:** On the synthetic U1 `+5V` to U2 `+3V3` SPI case,
  VM-001 emitted four findings, one each for `SPI_CS`, `SPI_MISO`, `SPI_MOSI`,
  and `SPI_SCK`; all were severity `error`. The same-rail control emitted no
  VM-001 finding. Full reports contained 13 and 6 candidate findings,
  respectively, including unrelated rules. Each full report was byte-identical
  across runs with `PYTHONHASHSEED=1` and `73`.
- **Incremental-value result:** The candidate demonstrates a possible
  coverage prompt when no project-authored LINT-061 map names a cross-rail
  digital peer. Its rail-name estimate, generic voltage thresholds, error
  severity, and level-shifter recommendation do not establish actual pin
  direction or receiver tolerance. Retain the idea only as a possible local
  REVIEW prompt under LINT-066; do not adopt candidate code, thresholds, or an
  installation dependency.
- **Boundary and open evidence:** This trial used only the candidate's
  schematic parser on synthetic source. No `kicad-cli` was on PATH during the
  trial, so there was no native export or ERC comparison. An app-bundled
  KiCad 10.0.6 CLI was found on 2026-10-07 and used for separate fixture and
  public-project probes; this cohort trial has not been rerun with native KiCad.
  A same-rail negative control does not measure false positives on 5 V-tolerant
  or mixed-supply parts. Reviewer effort, false-positive rate, performance,
  and behavior on approved non-proprietary projects remain unmeasured.
- **Follow-up source recheck (2026-10-11):** The public
  [kicad-happy v2.3.1 release](https://github.com/aklofas/kicad-happy/releases/tag/v2.3.1)
  reports a correct 3.3 V GPIO-to-regulator-EN connection that VM-001 had
  flagged when extracted device data lacked the EN threshold. Local LINT-066
  only evaluates explicit SPI and UART/USART peers, so GPIO/EN is outside its
  predicate. A synthetic MCU-to-regulator case now asserts zero protocol
  candidates and `NO_SUPPORTED_ENDPOINTS` coverage for both rules. This is a
  source-informed boundary control, not a runtime comparison or a voltage
  compatibility approval; no candidate code or project source was copied.

### Recorded trial: kicad-happy USB-C CC topology check

- **Candidate:** `aklofas/kicad-happy` v2.1.0, commit
  `f765dc0916e9752fe2639ca5bad4bda2d5161b8f`, declared MIT. The bounded source
  review covered its USB-C role classifier and `UC-003` finding text.
- **Invocation:** Ran only the deterministic analyzer directly with Python
  3.11, `--no-hierarchy`, and `--only-deterministic`. No package install or
  hosted review service was needed. Repeated runs had identical focused
  `usb_compliance` and `UC-*` results for each fixture. Checkout and reports
  stayed under `/private/tmp`; candidate code and output were not copied into
  this repository.
- **Inputs and result:** Three synthetic CC1/CC2 schematics were tested. The
  unconfigured connector had no CC attachments; the source control used two
  56 kΩ resistors to `+5V`; the sink control used two 5.1 kΩ resistors to
  `GND`. The candidate marked the source and sink controls as expected and
  emitted no `UC-003` findings for them. On the unconfigured pair it reported
  two sink-specific missing-pull-down findings while its role field was
  `unknown`.
- **Incremental-value result:** No unique actionable coverage was demonstrated.
  Evaluating LINT-053 on the same three parsed native contracts produced the
  `J1` role-map prompt for each one, including the valid source and sink
  controls, because none had a project role record. LINT-012 checks the
  project-declared CC requirements after the role is recorded. The candidate's
  sink assumption can be inapplicable to a source, dual-role, or
  controller-managed port, and the analyzer has no project-authored role map
  to resolve that question. Do not add it as a dependency or treat `UC-003` as
  proof of a missing required resistor.
- **Native evidence:** Each fixture was exported twice with digest-pinned
  KiCad 10.0.0 and 10.0.5 and parsed with the local native netlist parser.
  Parsed normalized contracts match across repeats and versions. Raw XML also
  matched across repeats in 10.0.0; in 10.0.5 the source and unconfigured raw
  XML differed, while their normalized parsed contracts remained identical.
  Source hashes, normalized netlist digests, image pins, and reproduction
  boundaries are recorded in the
  [synthetic fixture notes](../tests/fixtures/design_lint/cohort-usb-c-roles/README.md).
- **Boundary:** This is a parser-level comparison on synthetic schematics. It
  does not run ERC, verify USB compliance, prove the required role, inspect PCB
  copper, or assess real hardware.

### Recorded trial: kicad-sch-lint schematic geometry checks

- **Candidate:** `rashuky/kicad-sch-lint`, commit
  `97218e396de9a93d52de49a6710d4dcc0c1131c8`, version `0.1.0`, declared MIT
  license. Its package declares no runtime dependencies for linting; PDF
  rendering is optional.
- **Invocation:** Built and installed the local checkout into a disposable
  Python 3.11 virtual environment with `--no-build-isolation --no-deps`, then
  ran the installed `python -B -I -m kschlint lint <fixture> --severity info
  --codes wire-end-on-pin-line,pin-on-wire-middle,missing-junction,
  four-way-junction,dangling-wire,label-floating --json`. Pure schematic lint
  did not require `kicad-cli`. The candidate checkout, wheel, environment, and
  output remained under `/private/tmp`; no source or project data was copied
  into this repository.
- **Inputs:** The same six synthetic `.kicad_sch` files recorded in the
  kicad-happy trial. All six invocations completed and emitted valid JSON.
- **Observed output:** The pin-line fault reported `wire-end-on-pin-line` and
  `dangling-wire` at the same coordinate; its connected control reported no
  findings. The existing Tooling rule already identifies that fault using the
  native-unconnected pin and retains the wire UUID, so the second warning is a
  duplicate with less source identity. The pin-tip-on-wire-interior fault and
  its junction-marked control both emitted the same `pin-on-wire-middle` and
  `dangling-wire` warnings. The candidate did not distinguish the two
  connectivity states; its warning text says the pin connects in both cases.
  For the unmarked crossing it reported four dangling endpoints and no
  crossing finding. The marked control reported those same four endpoints
  plus `four-way-junction`; no `missing-junction` finding appeared on this
  fixture pair. The four-way warning on the marked control is a review hint,
  not evidence of an electrical fault. Native ERC was not part of this initial
  candidate run; the later KiCad 10.0.6 comparison is recorded under LINT-024
  and shows generic dangling-wire diagnostics in both crossing cases.
- **Incremental-value result:** The six geometry cases in this trial did not
  demonstrate a unique actionable finding beyond current near-miss localization. It showed useful
  comparison cases for control sensitivity and reinforces that schematic
  geometry must not declare electrical connectivity without native evidence.
  Do not adopt its analyzer or mutation workflow as a verification dependency.
- **Still unmeasured:** Repeatability across the candidate's claimed KiCad
  version range, reviewer effort, and performance on larger hierarchical
  designs. The exact-version comparison found no unique electrical finding;
  any review-time advantage from the candidate's generic dangling-wire output
  remains unmeasured.

### Recorded follow-up trial: kicad-sch-lint free-text overlap

- **Candidate:** The same MIT `rashuky/kicad-sch-lint` commit and disposable
  Python 3.11 installation recorded above. Only its read-only `text-overlap`
  check ran; candidate fixes and other checks were not invoked.
- **Inputs:** Synthetic copies of the tooling-owned
  `connected-pin-control.kicad_sch` fixture under `/private/tmp`, each with two
  standard 1.27 mm free-text objects. The fault places `LONG_LABEL_ALPHA` at
  `(25.4, 25.4)` and `LONG_LABEL_BETA` at `(29.0, 25.4)`; the control moves the
  second anchor to `(50.8, 25.4)`. No board or project source was imported.
- **Observed output:** The candidate reported one `text-overlap` on the fault
  with source UUIDs and approximate overlap box
  `[20.498, 24.403, 34.328, 26.149]`; the separated control had no finding.
  The pre-existing Tooling geometry scan had no candidate in either case
  because the source anchors were distinct. This is a new graphical review
  signal, not an electrical detection.
- **Native validation:** Exact KiCad 10.0.6 from the digest-pinned
  `kicad/kicad:10.0.6` image
  (`sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec`)
  exported both schematics to SVG and ERC. The fault's 89 and 95 text stroke
  segments have a zero minimum centerline distance, below the native 0.1524 mm
  stroke width. The control's minimum is 8.2247 mm. Both schematics have the
  same native netlist and identical three baseline ERC violations; the overlap
  itself changes neither connectivity nor ERC.
- **Decision:** Add a first-party, opt-in `schematic.free_text_overlap` rule
  using a native-render-calibrated standard-font envelope. Keep its default
  `off`; a project's explicit `review`, `block`, `off`, and exact-ignore policy
  controls disposition. Do not adopt the candidate package or its `error`
  severity. The local rule identifies the pair and overlap box and explains
  that rendered review is required.
- **Still unmeasured:** Reviewer time saved, false-positive rate on public
  real-world schematics, larger hierarchical typography coverage, and any
  advantage over direct KiCad rendering. Rotation, custom faces, explicit
  justification, non-ASCII, formatted, and bold/italic/thick cases are
  currently unsupported rather than inferred.

### Recorded follow-up trial: kicad-sch-lint text-over-wire

- **Candidate:** `rashuky/kicad-sch-lint`, commit
  `97218e396de9a93d52de49a6710d4dcc0c1131c8`, version `0.1.0`, declared MIT.
  The candidate checkout and outputs stayed in `/private/tmp`; the analyzer
  was read-only and no candidate code or project source was copied into
  Tooling.
- **Inputs:** Synthetic fault and control copies of the tooling-owned
  `connected-pin-control.kicad_sch`. The fault places `WIRE CROSSING FAULT`
  over the horizontal wire at y=71.12 mm; the control places `WIRE CLEAR
  CONTROL` 8.89 mm below it. No proprietary board or schematic was used.
- **Candidate result:** Its `text-over-wire` code reported the fault and
  returned no finding for the control. The SVG path comparison with exact
  KiCad 10.0.6 measured 0.000000 mm minimum text-stroke-to-wire distance in
  the fault and 7.9495 mm in the control. ERC violation signatures match
  between the pair. Native netlist nets match, and component/pin assignments
  match after excluding the project-specific `Sheetfile` property.
- **Decision:** Implement a separate deterministic
  `schematic.free_text_over_wire` geometry rule using the existing native-SVG
  calibrated text metrics, a fixed edge guard, and a minimum clipped wire
  length. Keep it `off` by default, review-only unless a project explicitly
  raises its mode, and subject to exact fingerprint ignores. Do not add the
  candidate dependency or infer required electrical connectivity from text
  placement.
- **Limit:** This is graphical evidence only. Standard-font axis-aligned
  envelopes can flag intentional annotation over a wire and do not test buses,
  labels, symbol fields, pin labels, or rendered symbol graphics. Broader
  typography and false-positive rates remain unmeasured.

### Recorded follow-up trial: kicad-sch-lint wire-through-body

- **Candidate:** `rashuky/kicad-sch-lint`, commit
  `97218e396de9a93d52de49a6710d4dcc0c1131c8`, version `0.1.0`, declared MIT.
  Its temporary checkout and environment remained under `/private/tmp`; no
  candidate code or project source was copied into Tooling.
- **Inputs:** Synthetic fault and control copies of the tooling-owned
  `connected-pin-control.kicad_sch`. Both include the same extra wire; the
  fault places it through the `Lint:R` body at y=76.2 mm, while the control
  moves it below the body. No proprietary board or schematic was used.
- **Candidate result:** `wire-through-body` reported one finding on the fault
  and none on the control, with an approximately 2.1 mm body overlap.
- **Native validation:** Exact KiCad 10.0.6 from the digest-pinned
  `kicad/kicad:10.0.6` image
  (`sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec`)
  exported both synthetic sources to netlist and ERC. Component/pin
  assignments and nets match after excluding the project-specific `Sheetfile`
  property; all six ERC violation signatures match. The geometry change does
  not affect connectivity or native ERC.
- **Decision:** Add a first-party, source-bound
  `schematic.wire_through_symbol_body` review rule using supported embedded
  symbol graphics and an explicit guard and minimum length. Keep it default-off.
  Do not add the candidate dependency or infer electrical intent from
  graphical overlap.
- **Limit:** The candidate measurement and first-party predicate use an
  axis-aligned envelope. Disjoint primitives and non-rectangular bodies may
  create false positives; reviewer time saved and public-project false-positive
  rates remain unmeasured.

### Recorded follow-up trial: kicad-sch-lint text-over-body

- **Candidate:** `rashuky/kicad-sch-lint`, commit
  `97218e396de9a93d52de49a6710d4dcc0c1131c8`, version `0.1.0`, declared MIT.
  The temporary candidate installation, synthetic copies, and outputs remained
  under `/private/tmp`; no proprietary board or project file was used.
- **Inputs:** Two copies of the tooling-owned
  `connected-pin-control.kicad_sch` with the same top-level `BODY NOTE` text.
  The fault places its anchor at `(76.2, 76.2)` over the R1 body; the control
  moves it to `(88.9, 76.2)`. The body outline is x=74.93..77.47 mm and
  y=73.66..78.74 mm.
- **Candidate result:** `text-over-body` reported one finding for the fault,
  identifying the note UUID and R1, and no finding for the control.
- **Native validation:** Digest-pinned KiCad 10.0.6 exports both synthetic
  schematics to netlist, ERC, and SVG. Native text-stroke bounds are
  x=71.1502..81.3103 mm for the fault and x=83.8502..94.0103 mm for the
  control, with the same y bounds; only the fault overlaps the body region.
  Component/pin assignments and nets match after excluding `Sheetfile`
  metadata, and all three ERC violation signatures match.
- **Decision:** Add a separate source-bound
  `schematic.free_text_over_symbol_body` rule using supported standard-font
  text and symbol envelopes. Keep it default-off with independent project
  review/block/off and exact-ignore dispositions. Do not adopt the candidate
  dependency or auto-move text.
- **Limit:** Axis-aligned glyph and body bounds can include empty space.
  Intentional annotation inside a symbol outline remains a review candidate;
  reviewer effort and false-positive rates on public projects are unmeasured.

### Recorded trial: pcb-inspector deterministic PCB heuristics

- **Candidate:** `takzen/pcb-inspector`, commit
  `d29e1208d4cdcd07ebac7f8632c9554cbd18121b`, package version `0.1.0`,
  declared MIT license. Its isolated installation resolved the candidate's
  runtime stack, including `mcp 2.2.0`, `pydantic 2.13.5`, and `shapely 2.1.2`;
  all installation artifacts stayed in `/private/tmp`.
- **Invocation:** In the disposable Python 3.11 environment, ran
  `pcb-inspector analyze <synthetic-board.kicad_pcb> --output <report.json>
  --format json --config /private/tmp/pcb-inspector-trial/rules.yaml`.
  Only Layer 2 heuristics ran; native DRC, vision, MCP, live editing, and
  automatic fixes were not invoked. The candidate checkout, environment, and
  reports remained under `/private/tmp`.
- **Inputs and native comparison:** Synthetic differential-pair fixtures in
  `tests/fixtures/design_lint/differential-pair/`, plus local synthetic PCB
  geometry fixtures. Native DRC ran separately in the cached
  `kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec`
  image, with source mounts read-only and receipts under `/private/tmp`.
  Configured pair rules produced `skew_out_of_range` on `fault-skew`; the
  same fault without its `.kicad_dru` rules produced only two unrelated
  dangling-track warnings and no pair finding. The compliant control produced
  no pair finding.
- **Observed candidate output:** With its default `max_diff_pair_skew_mm` of
  0.15 mm, pcb-inspector reported the synthetic 0.50 mm skew while the
  compliant control reported none. This demonstrates a unique review signal
  when project DRC constraints are absent, but the candidate's default limit
  is not an independently approved requirement for arbitrary interfaces.
  Equal-length `fault-gap` and `fault-uncoupled` cases produced no skew finding;
  the candidate does not replace native pair-gap or uncoupled-length rules.
  Its generic 0.25 mm VDD trace-width hint on the decoupling fixture did not
  match a project-authored width/current requirement and is not counted as a
  confirmed defect. Candidate-provided golden boards were not treated as
  independent evidence.
- **Incremental-value result:** Keep no runtime dependency. Adopt the bounded
  idea that recognized complementary net names without a reviewed pair map
  deserve a configurable REVIEW prompt. Local rule
  `signal.named_pair_without_reviewed_requirement` asks the project to review
  applicability and author limits; it intentionally does not copy the
  candidate's global 0.15 mm threshold or claim geometric adequacy. Native
  DRC remains the exact geometry check after a project-authored constraint is
  added.
- **Still unmeasured:** Results across the candidate's supported-version
  range, performance on larger boards, reviewer localization effort, and
  false-positive rates across real interface naming conventions. No private
  design was inspected.

### Follow-up trial: pcb-inspector HEUR-GND-001 narrow-void pair (2026-10-08)

- **Candidate and provenance:** `takzen/pcb-inspector` at pinned commit
  [`d29e120`](https://github.com/takzen/pcb-inspector/tree/d29e1208d4cdcd07ebac7f8632c9554cbd18121b),
  package version `0.1.0`, declared MIT. The pinned `LICENSE` SHA-256 is
  `3eae2a63788fe64ea502c55590fd655b9193bee63180c3ee55b7836fad7b1cda`; the
  selected `return_paths.py` SHA-256 is
  `1ba2f3d991ef50c59ed3a1458342b93c6bd4b0e326d6d16725a5264fd8db9ef2`.
  The disposable Python 3.11 install resolved `mcp 2.2.0`, `pydantic 2.13.5`,
  and `shapely 2.1.2` along with the candidate's other declared dependencies.
  Checkout, environment, configuration, and reports stayed under
  `/private/tmp`; no candidate code was copied into Tooling.
- **Invocation:** Ran `pcb-inspector analyze <board.kicad_pcb> --format json
  --output <report.json> --config <rules.yaml>` twice for each fixture. The
  temporary config disabled native DRC/ERC and vision, enabled heuristics,
  and set `HEUR-GND-001.min_track_length_mm: 0.1` plus
  `min_referenced_fraction: 0.65`. These values include this 2 mm test route
  and separate its measured fault from its control; they are not product-board
  defaults or project requirements.
- **Inputs:** The same tooling-owned two-layer synthetic boards used by
  LINT-058: a 2 mm F.Cu `DATA` segment over a B.Cu `GND` fill with one endpoint
  through-via clearance; the fault adds a 0.2 mm midpoint notch. Source hashes
  are `2ac9f1f5680219ee04e3a27ac398922dbeede4abfd41a478a6b35eb035cc6113`
  (control) and `4d1a2f44dcc8f4eb8605d0668d3bb1556c94d49c849308b88082f31a2252a7fc`
  (fault). No external board or project expectation was used.
- **Observed result:** Both runs of the control passed with no findings. Both
  runs of the fault emitted one `HEUR-GND-001` warning on `DATA`, locating the
  segment midpoint at `(11, 13)` mm. Its report describes the full `2.0 mm`
  segment as affected and recommends expanding the ground pour; it does not
  report the exact uncovered interval or assign the notch to a physical cause.
  The candidate reads the filled copper contours from the PCB source directly
  and measures the route against them. Full report bytes include timestamps;
  after normalizing the timestamp and runtime, repeat reports matched with
  SHA-256 `a03e9ca10e19dc2649cdc50e57eb69f8b86405056d58d4cfe2fc94e3c0f3058d`
  (control) and
  `77e8b39c90c206bfcc4a4fe6a433ce4e3fcc7d9db46f52495129a38194dca6d8`
  (fault).
- **First-party comparison and disposition:** LINT-058 measures the same
  source-bound fixture pair at `2799/4000` for the control and `2399/4000` for
  the fault; with the same 0.65 review threshold, it passes the control and
  reports the fault. This candidate trial corroborates the narrow-void
  regression, but adds no distinct defect detection beyond LINT-058. Keep the
  first-party gate and its exact native evidence; do not add a runtime
  dependency. The candidate's segment-level output is less specific than the
  source-bound covered fractions and via-hole context already reported here.
  Like LINT-058, its result is a geometric review hint, not proof of actual
  return-current continuity or an electrical defect.
- **Still unmeasured:** Broader-board false-positive and false-negative rates,
  reviewer effort, and performance on large pours. The focused hosted repeat
  of the split LINT-058 suite passed on pinned KiCad 10.0.0 and 10.0.5 in
  `v0.5.0rc193` (GitHub Actions run `38308617935`).

### Recorded trial: KiDiff schematic revision comparison

- **Candidate:** [INTI-CMNB/KiDiff](https://github.com/INTI-CMNB/KiDiff), v2.6.0;
  commit `d77f103ca7c3580e28584eed209753818640d2b9`, GPL-2.0.
  The published `kicad10_auto:1.9.0` image was pinned to digest
  `sha256:493666a06d900ed3352c50b0f75a76ccdfe194999c097d455021cab9e3c723fa`;
  runtime reported KiCad/Pcbnew 10.0.4 and KiDiff 2.6.0. This is a
  cross-version research run: the fixture's original native contract evidence
  was generated with KiCad 10.0.6.
- **Installation and boundary:** Upstream documents a root-level `make install`
  that copies commands into `/usr/local/bin`; its Python package depends on
  KiAuto and still requires KiCad/Pcbnew, wxWidgets, ImageMagick, and PDF
  conversion tools. The host lacked several native dependencies, so the trial
  used the published Linux image. Only the synthetic fixture directory was
  mounted read-only; rendered files went to a separate temporary output
  directory. No cohort implementation or private design data was copied into
  this repository.
- **Reproduction:** From this repository root, set `IMAGE` to the digest above,
  `FIXTURES=tests/fixtures/design_lint/cohort-connector-ground-domains`, and
  `OUT` to a disposable directory, then run:

  ```sh
  mkdir -p "$OUT"
  docker run --rm --platform linux/amd64 \
    --mount type=bind,src="$PWD/$FIXTURES",dst=/trial/input,readonly \
    --mount type=bind,src="$OUT",dst=/trial/output \
    --entrypoint "" "$IMAGE" \
    kicad-diff.py /trial/input/control.kicad_sch /trial/input/fault.kicad_sch \
    --all_pages --no_reader --resolution 96 \
    --output_dir /trial/output --output_name split-returns
  ```

- **Inputs and observed output:** The public synthetic pair keeps both
  six-contact connectors and their four data contacts fixed while changing
  return labels from common `GND` to separate `GND1` and `GND2`. KiDiff emitted
  a one-page red/green PDF highlighting the changed labels at J1/J2 pins 1/2.
  Comparing the control with itself produced no colored changes. Each run
  exited successfully and emitted three non-fatal Pcbnew enum assertion
  messages on stderr. The full-page result makes the change visible, though
  the labels need zoom for comfortable reading.
- **Incremental-value result:** This is review visualization, not an electrical
  finding. The split-return fault already produces a Tooling `REVIEW` while the
  common-return control passes; KiDiff adds no unique detection and does not
  explain whether the split is intentional. A valid text-only or graphical
  edit would also be highlighted. Reviewer effort and general false-positive
  rates were not measured. Do not add a runtime dependency or use the visual
  diff as verification evidence; retain it as an optional human review aid.
- **Still unmeasured:** Other page layouts, larger schematics, unchanged
  geometry with text-only edits, reviewer localization time, and KiCad 10.0.6
  behavior. No auto-apply or source mutation was used.

### Recorded trial: kicad-happy repeated-connector return domains

- **Candidate:** `aklofas/kicad-happy`, commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT license. This is a
  second fixture batch for the same analyzer, not a second candidate tool.
- **Inputs:** The public synthetic fault/control pair in
  `tests/fixtures/design_lint/cohort-connector-ground-domains/`. Each of two
  identical six-contact connectors has four shared data functions and two
  `GND` pin functions. The fault assigns connector returns to `GND1` and
  `GND2`; the control assigns all four return contacts to `GND`. No proprietary board
  files or project-specific source were used. See the
  [fixture notes](../tests/fixtures/design_lint/cohort-connector-ground-domains/README.md)
  for the exact native and candidate analyzer observations.
- **Native evidence:** Exported both fixtures and ran ERC with KiCad CLI
  10.0.6. The netlists preserve the intended split-versus-common return
  topology. ERC emitted the same two synthetic-library warnings on each
  fixture and no connectivity violation; it does not infer the intended
  relationship. Tooling's `read_netlist` plus default `design_lint` policy
  returned `REVIEW` on the fault with `connector.repeated_pin_function` and
  `net.numbered_returns`, including the J1/J2 pin and net evidence. The
  control returned `PASS`.
- **Invocation:** Direct Python 3.11 script invocation, with no package
  installation, network lifecycle audit, or source copied from the candidate:

  ```sh
  python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
    "$FIXTURES/fault.kicad_sch" --no-hierarchy --only-deterministic \
    --output "$OUT/fault.json"
  python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
    "$FIXTURES/control.kicad_sch" --no-hierarchy --only-deterministic \
    --output "$OUT/control.json"
  ```

  Here `HAPPY` names the checkout at the commit above, `FIXTURES` names the
  fixture directory, and `OUT` is a scratch report directory outside source
  control. The native source checks were run serially to avoid concurrent
  KiCad CLI instance-lock cleanup.
- **Observed candidate output:** Both runs completed and returned five general
  findings; none identified the split return domains. The structured
  `ground_domains` output classified `GND1` and `GND2` as `signal` domains and
  reported `multiple_domains: false` for the fault. It likewise classified
  the shared `GND` net as `signal` and reported `multiple_domains: false` for
  the control. The connector ground-distribution audit emitted no actionable
  finding. Its documented `>4` signal-to-ground ratio is not a contract for
  whether matching returns on separate connectors share a net; even if this
  fixture's two return contacts are counted, its 4:2 allocation is below that
  threshold.
- **Incremental-value result:** No unique connector-return detection or useful
  review evidence was demonstrated. The analyzer did parse the connector pin
  maps, but did not surface the fault. The current Tooling check distinguished
  the pair using connector pin functions plus the numbered-return net names.
  Keep no runtime dependency and do not treat the candidate's ground-domain
  summary as evidence that numbered return nets are common.
- **Still unmeasured:** Candidate behavior on alternate ground naming,
  explicit intent/ground-domain configuration, other connector families, and
  reviewer localization time. Native ERC cannot establish the copper return
  path; PCB connectivity remains a separate verification lane.

### Recorded follow-up trial: kicad-happy mapped generic supply contacts

- **Candidate:** The same `aklofas/kicad-happy` commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`. Its deterministic `NT-001`
  implementation reports singleton nets; see the pinned
  [analyzer source](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/analyze_schematic.py#L3695-L3755).
- **Inputs and execution:** The synthetic split-supply fault and common-net
  control in
  `tests/fixtures/design_lint/cohort-mapped-connector-supplies/` were analyzed
  twice each with `--no-hierarchy --only-deterministic`. Source hashes,
  commands, raw-report hashes, and stable projection hashes are recorded in the
  [fixture notes](../tests/fixtures/design_lint/cohort-mapped-connector-supplies/README.md).
  No board or candidate report was copied into Tooling.
- **Observed output:** The fault reports `NT-001` INFO findings for singleton
  `SUPPLY_ALPHA` on J1.1 and `SUPPLY_BETA` on J2.9; the common-net control has
  neither. Both reports say `ground_domains.multiple_domains: false`. A
  singleton `CHASSIS` prompt appears in both, while generic ESD, datasheet,
  sourcing, and lifecycle observations are outside this comparison. Raw JSON
  differs on repeat only because `inputs.run_id` and
  `capability_mode_ref.run_id` change; the canonical projection of ground
  domains and `NT-001` evidence is stable.
- **Local comparison and disposition:** Native-only Tooling lint has no
  repeated-role candidate for these generic pins. A complete source-matched
  map adds one `connector.repeated_pin_function` REVIEW with both `supply`
  roles and their exact shared `external-5v` domain; the common-net control and
  different-domain control pass. `NT-001` therefore adds a broad singleton-net
  review clue over the native-only baseline but does not identify a required
  relationship or establish a defect. The same candidate warning can apply to
  valid off-board power contacts, as recorded in the earlier connector trial.
  Treat this as review context, not a confirmed detection or a reason to add a
  second local rule. The source-matched local finding is more specific; no
  candidate dependency is justified.
- **Still unmeasured:** Reviewer time saved, field false-positive rate, and
  prevalence of this topology in non-confidential designs. Same-domain
  singleton rails may be intentional; project-authored connectivity remains
  the requirement that can make a mismatch blocking.

### Recorded trial: kicad-happy IC power-pin DC-path audit

- **Candidate:** `aklofas/kicad-happy`, commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT. Its `PP-001`
  detector walks from each `power_in` pin across selected low-resistance
  components and rejects capacitor edges; its documented implementation also
  skips named rails and connector-bearing nets. See the pinned
  [detector source](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/signal_detectors.py#L4443-L4629).
- **Inputs:** Tooling-owned synthetic `fault.kicad_sch` and `control.kicad_sch`
  under `tests/fixtures/design_lint/cohort-power-pin-dc/`. The fault puts a
  `power_in` pin and a decoupling capacitor on generic `LOCAL_A`; the control
  changes only that net name to `+3V3`. The latter is only a detector
  non-finding control: neither file shows a source component. No proprietary material
  was used. The
  [fixture README](../tests/fixtures/design_lint/cohort-power-pin-dc/README.md)
  retains the source hashes and reproduction command.
- **Invocation:** Reused the pinned temporary cohort checkout and ran its
  script directly with the repository's Python 3.11 environment, `-B -I`,
  `--no-hierarchy`, and `--only-deterministic`. JSON reports stayed under
  `/private/tmp`. Both fault and control returned the same `PP-001` / `RS-001`
  result sets on a second run. Then exported the same synthetic fault and
  name-only control through digest-pinned KiCad 10.0.0 and 10.0.5, adding a
  source-backed `power_out` control. Each netlist and ERC report was generated
  twice in a network-disabled container with read-only fixture mount and
  reports under `/private/tmp`; normalized netlist contracts and normalized
  ERC violation details matched on repeat. Source hashes and reproduction
  commands are in the fixture README.
- **Observed output:** The fault produced heuristic `PP-001` (“no DC path to a
  power rail”) and `RS-001` (“no declared source”). The `+3V3` control omitted
  `PP-001` but still produced `RS-001`; it does not establish that naming a
  net is a valid source. The equivalent synthetic `NetlistContract` passed
  Tooling's current `design_lint.evaluate` with no candidate because no
  project-authored power-connectivity map was supplied. Native ERC reported
  `power_pin_not_driven` as an error on `U1.1` for both the `LOCAL_A` fault and
  the name-only `+3V3` control in KiCad 10.0.0 and 10.0.5. The source-backed
  control put `U1.1`, `U2.1` (`power_out`), and `C1.1` on `+3V3`; both native
  versions omitted `power_pin_not_driven`. Other library-table and isolated
  label warnings came from the minimal synthetic fixture and are not counted
  as source-path evidence.
- **Disposition:** Do not adopt `PP-001` as an additional detector for this
  case. It adds no finding beyond native ERC: KiCad already flags the
  undriven `power_in` pin whether its net is called `LOCAL_A` or `+3V3`, and
  clears that violation when a same-net `power_out` source is present. The
  cohort's more specific “no DC path to a power rail” wording may help
  localization, but reviewer effort was not measured. Keep source-backed
  power maps as the deterministic project-authored requirement; evaluate a
  broader path heuristic only against resistor, ferrite, fuse, jumper, and
  DNP controls where ERC behavior is measured separately. The candidate's
  error severity is not a local policy recommendation.
- **Not measured:** External connector sources, regulator-output and
  multi-stage paths, filters, ferrites, fuses, solder jumpers, DNP parts,
  internal rails, false-positive rate, and reviewer effort. The new control is
  synthetic ERC evidence only; it is not a power-source design recommendation
  or an electrical approval.
- **Follow-up source recheck (2026-10-11):** The
  [kicad-happy v2.3.0 changelog](https://github.com/aklofas/kicad-happy/blob/v2.3.0/CHANGELOG.md)
  records a PP-001 false fuse classification for an `F1`-referenced 74LS32.
  A matched synthetic LINT-056 pair confirms an `F1`/`74xx:74LS32` is not a
  supported path, while an `F1`/`Device:Fuse` remains one. An additional
  LINT-084 case confirms a real `Device:Fuse` remains detectable when its
  reference is `U1`. This is a source-informed local regression set, not a
  runtime comparison or a new native export. No candidate code or project
  source was copied.

### PP-001 bootstrap exception source audit (2026-10-23)

- **Pinned source and report:** The current kicad-happy `PP-001` change is at
  commit
  [`4701c26eba7b9788874a0bf9b45c0a3e81db1628`](https://github.com/aklofas/kicad-happy/commit/4701c26eba7b9788874a0bf9b45c0a3e81db1628).
  Upstream [issue #55](https://github.com/aklofas/kicad-happy/issues/55)
  describes a valid buck-controller bootstrap pin (`BST`) with a fitted
  capacitor to its `SW` pin. The audited commit skips pin functions containing
  `BST`, `BOOT`, `BOOTSTRAP`, or `CBST` tokens. Its MIT license is present at
  the audited commit. This was a source audit; the candidate analyzer was not
  run again.
- **Local boundary result:** A tooling-owned synthetic `power_in` case with
  `CBOOT` between `BST` and `SW` produces no LINT-056 source-path prompt
  because the local rule requires capacitor-to-return evidence. A paired
  `BOOT_EN` case with only a fitted capacitor to `GND` remains a REVIEW
  candidate. The source token `BOOT` also matches `BOOT_EN`, so the local
  predicate stays tied to topology instead of adding a pin-name-only
  exemption. These are typed-netlist regressions, not a new native KiCad run
  or a claim that the `BOOT_EN` case is defective.
- **Incremental-value decision:** Do not add or adopt a second PP-001 rule.
  The existing local rule stays quiet on the reported bootstrap topology; the
  name-token exception has no demonstrated unique coverage and could suppress
  unrelated `BOOT`-named inputs. Reviewer effort, runtime behavior of the new
  candidate revision, and field false-positive rates are unmeasured. No
  candidate code, board, or issue fixture was copied.

### Follow-up trial: kicad-happy decoupling-presence detector

- **Candidate and source:** The same pinned kicad-happy checkout produced a
  distinct `DO-DET` observation for a fitted IC whose recognized positive rail
  had no capacitor symbol anywhere on that schematic net. The upstream
  detector is in the pinned
  [signal detector source](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/signal_detectors.py#L3480-L3510).
- **Inputs and result:** The synthetic `no-cap.kicad_sch` fault is derived
  from the capacitor-bearing `+3V3` control in the preceding trial by removing
  its capacitor symbol and power pin connection. The candidate emits
  “IC U1 missing decoupling on +3V3” for the fault and “Decoupling coverage on
  +3V3” for the capacitor-bearing control. The result distinguishes capacitor
  symbol presence; it does not establish a datasheet requirement, value,
  placement, or physical return path.
- **Source-backed incremental-value follow-up:** Added a no-cap fixture with
  `U1.1` (`power_in`) and `U2.1` (`power_out`) connected to the same `+3V3`
  net, removing missing-source ambiguity. Repeated netlist and ERC runs on
  digest-pinned KiCad 10.0.0 and 10.0.5 show the expected two pin types on the
  same rail and no `power_pin_not_driven` violation; the normalized native
  reports match. LINT-046 emits its default `REVIEW` prompt for this fault,
  while the source-backed capacitor control passes without a prompt. The pinned
  kicad-happy analyzer was then run twice on each source-backed fixture. Its
  `DO-DET` findings distinguish the no-cap source-backed fault (U1 and U2
  reported missing decoupling) from the capacitor control (coverage reported
  for C1, no missing-decoupling finding). Both pairs of raw JSON reports were
  byte-identical on repeat. The extra U2 finding shows broader applicability
  than LINT-046's `power_in` target and is not counted as a confirmed defect.
  This corroborates review coverage over native ERC, not unique detection over
  the local heuristic. Fixture hashes, report hashes, reproduction command,
  and exact image digests are recorded in the
  [synthetic fixture notes](../tests/fixtures/design_lint/cohort-power-pin-dc/README.md).
- **PP-001 source-backed recheck (2026-09-30):** Repeated the pinned analyzer
  run on all four source-less and source-backed fixtures. Reports were
  byte-identical on repeat. `PP-001` remains limited to the `LOCAL_A` fault;
  it does not report on the source-backed no-cap case or capacitor control.
  On the name-only `+3V3` control, `PP-001` is absent while separate `RS-001`
  still reports that the rail has no source. This confirms no unique
  source-path coverage from `PP-001` for the source-backed pair. The same
  reports show `DO-DET` distinguishing capacitor presence, including a prompt
  on source component `U2`; applicability to U2 is not proof that it needs a
  capacitor. Full focused findings, candidate-source hashes, report hashes,
  and the command are recorded in the linked fixture notes.
- **PP-001 wrong-rail follow-up (2026-09-30):** Ran the same pinned analyzer
  twice on the native ferrite-path control and assigned-wrong-net fault. The
  fault produced `PP-001` for `U2.1`; the valid control produced none. Full
  report SHA-256 values repeated exactly: control
  `b65723f226bc985e3b46c5c760712f2f262fa414cc99ce00bb34e67efdc9c168`, fault
  `1d8b308e0baa0b252b1cae2f72835ce9b368db98ece7a015b36a0966cfd8d5a7`. The
  native fixture has zero ERC errors and identical violation types for control
  and fault. The authored LINT-055 map already catches the fault when supplied;
  without a map, the old local baseline returned no finding. LINT-056 adopts
  only a bounded default-`REVIEW` fallback for that uncovered configuration.
  It does not copy PP-001's “likely AC-coupled” claim or `error` severity. The
  pinned candidate source and fixture boundaries are recorded in the
  [power-path fixture notes](../tests/fixtures/design_lint/power-path-native/README.md).
- **Baseline and disposition:** The local schematic design-lint baseline had
  no equivalent prompt when no project-authored decoupling map was supplied.
  The existing `pcb.decoupling_proximity` rule is a separate opt-in PCB
  measurement requiring an authored pad map and threshold. Adopt the bounded
  presence prompt as LINT-046 with default `review`, based on its incremental
  review coverage and deterministic synthetic fault/control behavior. Keep it
  separate from mapped PCB placement checks and native ERC: ERC does not
  diagnose the absence of a capacitor symbol in this source-backed control.
- **Validation boundary:** Cohort runtime evidence covers source-less and
  source-backed synthetic no-cap fault/control pairs; the local source-backed
  fixtures are also native-validated on KiCad 10.0.0 and 10.0.5. Neither the
  cohort nor this heuristic determines
  whether a capacitor is required, its value, placement, or physical return
  performance. Internal, external, or off-board decoupling and uncommon
  capacitor or rail naming remain unmeasured.

### Recorded trial: kicad-happy LED current-limiter prompt

- **Candidate:** [aklofas/kicad-happy](https://github.com/aklofas/kicad-happy)
  at commit `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT. Its
  `validate_led_resistors` LR-001 detector uses component classification,
  assigned schematic nets, and conventional resistor topology; its source
  also estimates forward voltage and current from assumed color/default
  values. The direct inspection was limited to the pinned
  [LR-001 source](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/validation_detectors.py#L1085-L1245).
- **Inputs and invocation:** Three tooling-owned KiCad schematic fixtures in
  `tests/fixtures/design_lint/cohort-led-resistor/` were parsed by the pinned
  candidate using Python 3.11, `-B -I`, `--no-hierarchy`, and
  `--only-deterministic`. The direct-rail LED fault emitted one LR-001 finding;
  the fitted series-resistor control emitted none; and the direct-rail fault
  with a parallel resistor also emitted none. The
  [fixture README](../tests/fixtures/design_lint/cohort-led-resistor/README.md)
  records all source hashes, commands, and candidate outputs. Repeating all three runs
  produced the same filtered LR-001 summaries. Reports stayed in ignored
  `build/`; no cohort implementation or project data was copied.
- **Baseline and disposition:** Before this local rule, Tooling's native
  netlist heuristic baseline had no LED current-limiting candidate. The trial
  supports a review prompt for the direct rail-to-return pattern and the
  series-resistor control. It also exposes a candidate miss: an across-rails
  parallel resistor is accepted as if it were in series. LINT-048 therefore
  keeps only a narrower direct-assignment predicate, which still reports this
  case. It does not import the candidate's guessed values, sizing, fixes,
  severity, or install flow.
- **Validation boundary:** These synthetic sources were accepted by the
  candidate parser but were not exported or checked by native KiCad in this
  environment. The cohort output and local candidate are review evidence only;
  they do not establish current, source limiting, resistor suitability,
  forward polarity, physical connectivity, or that every LED needs an external
  resistor. False-positive rate, reviewer effort, and the native ERC
  comparison remain unmeasured.

### Recorded trial: kilint I2C address-map coverage

- Candidate: [romkey/kilint](https://github.com/romkey/kilint) at commit
  923320614b25ec0e5d2bc40d835b32233ad71f0c, version 0.5.1, declared MIT
  license. The cohort checkout and trial environment stayed under
  /private/tmp; no candidate code, project data, or fixture was copied into
  Tooling.
- Installation: Installed the local checkout into a disposable Python 3.11
  virtual environment. The global interpreter lacked PyYAML and hatchling;
  pip resolved kilint 0.5.1 and PyYAML 6.0.3 in the isolated environment.
  This requires Python packaging and a source checkout, but no native KiCad
  executable or GUI setup for this rule.
- Invocation: The isolated kilint CLI ran lint on each synthetic directory
  with a temporary config enabling only rule 20, i2c-address-declared, and
  JSON output. Each run used --fail-on error so the default INFO finding
  remained visible without making it an error gate.
- Inputs: Four independently constructed, minimal synthetic PCB S-expression
  files under /private/tmp/kilint-synthetic-trial: U1 on I2C1 SDA/SCL without
  an address property; the same IC with address 0x44; a connector-only
  control; and a U1 attached to SDA and SCL names that identify different
  buses. These files were parsed by kilint; native KiCad import/ERC was not
  run, so they test the candidate predicate and report, not KiCad file
  validity or copper connectivity.
- Observed output: The undeclared U1 produced one INFO finding naming U1 and
  both I2C nets. The declared-address, connector-only, and cross-bus controls
  produced no findings. The rule uses board pad-net names and U references by
  default; its address declaration is a kilint-specific property.
- Baseline comparison: Before the local rule, Tooling returned
  i2c_address_coverage status NOT_REQUESTED when the project omitted its map
  and emitted no missing-responder candidate. Its address comparison only
  covered responders already named by the project map. The candidate thus
  demonstrated unique review coverage on one synthetic fault, not new
  electrical detection or an address-collision check. False positives were
  zero on three controls; reviewer time and performance were not measured.
- Disposition: Keep no kilint runtime dependency. Implement the concept
  independently as bus.i2c_unmapped_responder: it uses native exported symbol
  pin functions and assigned nets, accepts U and IC reference prefixes,
  compares against the project address map, and participates in the existing
  review/block/off and exact-ignore lifecycle. This covers the missing-map
  case without importing kilint's parser, property convention, examples, or
  configuration format.
- Boundary: The local rule is still only a heuristic. Incorrect symbol
  function metadata and other reference prefixes can evade it; bridges or
  other intentionally unaddressed ICs can be review candidates. The project
  can list static or dynamic responders, turn the rule off, or record a
  reasoned exact ignore. No proprietary board or project-specific file was
  inspected.

### Recorded trial: kilint I2C pull-up series-chain coverage

- **Candidate:** `romkey/kilint`, commit
  `923320614b25ec0e5d2bc40d835b32233ad71f0c`, version 0.5.1, declared MIT.
  Reused the disposable Python 3.11 environment recorded above. The tested
  `kilint/rules/i2c.py` SHA-256 is
  `c9b57c0b465066299c6833228ced91419aff8f14313f023fd047ade0313c4513`.
- **Predicate and data boundary:** Rule 18 (`i2c-pullups`) recognizes a
  configured `R`/`RN` component only when one board pad net is an I2C line and
  another pad net on that same component is a power net. It reads PCB pad-net
  assignments; it does not trace intermediate resistor nets or use component
  values. Two independently authored synthetic `.kicad_pcb` net-assignment
  fixtures stayed under `/private/tmp`: direct control hash
  `0831b5afbd2c1809c0e1739c60c01a6a959b75d623d602fbdad281f022a112e3` and
  two-resistor SDA chain hash
  `b79660dc39db6ae8ce390e2ceeaa0f84fdce8b558bfe95b9a8234fd49ce3180c`.
  They contain no copper geometry and were not imported or checked by native
  KiCad.
- **Invocation:** The prior isolated install supplied the `kilint` entry point;
  a temporary configuration enabled only rule 18. The config SHA-256 is
  `618dc3ffd9db29a76590a54d37e673944ad1ed704b4c39e94aa7419ae84fe5b3`.

  ```sh
  "$KILINT" lint "$FIXTURES/control" --config "$FIXTURES/kilint.yml" \
    --format json --fail-on error
  "$KILINT" lint "$FIXTURES/series" --config "$FIXTURES/kilint.yml" \
    --format json --fail-on error
  ```

- **Observed result:** The direct control produced no findings. The series
  fixture produced one rule-18 warning on `I2C1_SDA`; `I2C1_SCL` remained quiet
  because it had a direct resistor. Repeated output hashes matched exactly:
  control `ebda66d4aea6426d8f4bd751555878cba2e908780963c70975af842a55f65622`,
  series `3c6433ecc35b47db0db28471d7887ac8071a5538b922dce2054fec2fef5d6f64`.
- **Local comparison and disposition:** Tooling's bounded heuristic accepts
  the equivalent source-bound two-leg topology; the existing synthetic
  `2.2 kΩ + 2.2 kΩ` case totals 4.4 kΩ and passes. The focused tests for valid
  series paths and low-equivalent series paths passed (`2 passed`). The cohort
  rule therefore adds no unique finding for this fixture and misses a valid
  series-path alternative. Keep no kilint runtime dependency and retain the
  first-party series-chain behavior.
- **Limit:** This is a pad-net parser comparison, not a KiCad-native import,
  electrical simulation, or PCB-copper check. Resistor population state,
  branching, resistor arrays, internal pull-ups, field false positives, and
  reviewer effort were not measured in this candidate run.

### Recorded trial: kicad-happy USB series-resistor prompt

- **Candidate:** [aklofas/kicad-happy](https://github.com/aklofas/kicad-happy)
  at commit `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT. The
  `validate_usb_bus` PR-004 detector source is pinned at
  [validation_detectors.py](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/validation_detectors.py#L894-L945).
- **Inputs and invocation:** Two tooling-owned synthetic schematic-parser
  fixtures in `tests/fixtures/design_lint/cohort-usb-series/` were analyzed
  with Python 3.11, `-B -I`, `--no-hierarchy`, and
  `--only-deterministic`. The candidate no-external-resistor fixture emitted
  one PR-004 prompt per data pin; the visible 22R-per-line control emitted
  none. Repeated runs produced identical filtered findings. The fixture README
  records hashes and commands. Reports stayed in ignored `build/`; no
  candidate code or product design was copied. No package installation or full
  candidate workflow was measured.
- **Baseline and disposition:** Before the source-backed project map was added, Tooling emitted the
  broader `signal.named_pair_without_reviewed_requirement` prompt on `USB_D+`/`USB_D−` for both the
  no-resistor candidate and resistor control. That prompt asks whether the names indicate a physical
  pair; it does not review resistor topology. The exact alias baseline is covered by
  `tests.test_design_lint_named_pairs.test_named_complementary_nets_prompt_for_reviewed_pair_requirements`.
  The candidate detector remains unadopted because its generic 15–33 Ω assumption prompts on a
  documented integrated-PHY direct path. The local exact map adds component topology coverage only
  when a project supplies its reviewed decision.
- **Validation boundary:** The fixtures test only candidate parser behavior
  on a two-pin named data pair. The no-external-resistor case is a candidate
  prompt, not a confirmed electrical fault. They do not model a complete
  connector, a documented PHY, USB-C, USB 3.x, resistor branches, or PCB
  routing. This candidate trial was parser-only and did not import/export with
  KiCad or compare ERC. Separate local LINT-049 native regressions, recorded in
  the source-backed PHY trial below, exercise synthetic direct, series, and
  bypass fixtures on pinned KiCad 10.0.0 and 10.0.5. Native ERC, electrical
  applicability, false-positive rate, and reviewer effort remain unmeasured.

### Recorded source-backed USB PHY applicability trial

- **Candidate:** The same pinned kicad-happy checkout and `validate_usb_bus`
  PR-004 detector described above.
- **Manufacturer evidence:** ST AN4879 Rev 12 (June 2026), FAQ lines 914–918, says STM32 internal
  USB PHY pads include matching output impedance and need no external resistors. Its implementation
  table identifies STM32F103 as full-speed with an integrated PHY. TI's TUSB2036 Rev I datasheet
  (March 2017), Section 9.2, says USB DP/DM pairs require approximately 27 Ω series resistors.
  Links:
  [ST AN4879](https://www.st.com/resource/en/application_note/an4879-usb-hardware-and-pcb-guidelines-using-stm32-mcus-stmicroelectronics.pdf),
  [TI TUSB2036](https://www.ti.com/lit/ds/symlink/tusb2036.pdf).
- **Inputs and outcome:** `integrated-stm32-fs-direct` and
  `external-hub-no-series-resistors` each produced two PR-004 prompts;
  `external-hub-control-27r-series` produced none. Two repeated
  `--only-deterministic` runs per fixture had identical filtered output. The
  candidate distinguishes a visible 27R pair from no parts, but gives a false
  prompt for the source-backed direct integrated-PHY control.
- **Local comparison:** The project-authored `usb_data_path_map` accepts both
  the direct integrated-PHY control and the TUSB2036 27R control. Removing
  required R1 from the TUSB2036 synthetic native-netlist model produces one
  `bus.usb_data_path_mismatch` finding on D+. Existing named-pair review alone
  does not inspect that series component topology. DNP, wrong value, wrong
  endpoints, exact ignore, override, and disable paths are also regression
  tested.
- **Limits:** The cohort candidate run was a parser-only trial over synthetic
  schematic source, not native KiCad import. The separate LINT-049 native lane
  exports the direct, series, and bypass fixtures on pinned KiCad 10.0.0 and
  10.0.5 and checks the local rule against those parsed netlists. Native ERC,
  electrical qualification, the selected resistor range, false-positive
  rates, and reviewer effort remain open.

### Recorded trial: kicad-happy singleton warnings on USB reference pins (2026-10-07)

- **Candidate:** The public `aklofas/kicad-happy` checkout at commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT. The analyzer
  script and license hashes, invocation, fixture hashes, and repeat report
  hashes are recorded in the
  [USB peer-reference fixture record](../tests/fixtures/design_lint/usb-peer-reference-native/README.md).
- **Inputs and repeatability:** Ran the candidate's schematic analyzer twice
  on the tooling-owned direct-USB split-reference fault and common-reference
  control. Each same-input pair produced byte-identical full JSON reports.
  The candidate emitted the same two `NT-001` singleton-pin prompts for
  J1.4 `GND` and U1.3 `AGND` on both inputs; the complete candidate finding
  arrays were identical and contained ten findings each.
- **Incremental-value result:** The candidate did not distinguish the split
  reference from the common-reference control and added no unique
  reference-domain finding. The local typed heuristic does distinguish this
  synthetic pair, with a REVIEW on the split case and no peer-reference
  finding on the common case. The local KiCad-native export lane has not run
  on this host, so this is not a direct comparison on native-exported input.
  Keep the generic singleton analyzer unadopted for this use case.
- **Boundary:** This was a parser-only run of a direct script from the pinned
  checkout; its full installation workflow, native import/ERC behavior,
  reviewer effort, and field precision were not measured. No cohort code or
  external project source was copied into Tooling; the reports remained under
  `/private/tmp`.

### Recorded trial: kicad-happy SPI chip-select pull-up prompt

- **Candidate:** [aklofas/kicad-happy](https://github.com/aklofas/kicad-happy)
  at commit `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT. Its
  `validate_spi_bus` PR-002 source is pinned at
  [validation_detectors.py](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/validation_detectors.py#L822-L844).
- **Inputs and invocation:** Four tooling-owned schematic-parser fixtures in
  `tests/fixtures/design_lint/cohort-spi-bias/` were analyzed with Python 3.11,
  `-B -I`, `--no-hierarchy`, and `--only-deterministic`. The no-pull-up case
  emitted one PR-002 prompt; a fitted 10k control emitted none. DNP 10k and 0R
  anti-controls also emitted none. Repeated runs produced identical filtered
  findings. The [fixture README](../tests/fixtures/design_lint/cohort-spi-bias/README.md)
  records hashes and commands; output stayed in ignored `build/`. No package
  installation or full candidate workflow was measured.
- **Baseline and disposition:** Tooling's existing LINT-045 rule reports the no-pull-up case,
  accepts the fitted 10k control, and still prompts for the DNP and 0R cases. Those controls are
  covered by
  `tests.test_design_lint_spi.test_spi_active_low_select_bias_hint_is_review_only_and_configurable`
  and
  `tests.test_design_lint_spi.test_spi_select_bias_reports_unusable_pullup_paths`.
  Valid controls are checked by
  `tests.test_design_lint_spi.test_spi_select_bias_recognizes_pullup_paths` and
  `tests.test_design_lint_spi.test_spi_select_bias_ignores_valid_controls`.
  PR-002 adds no new detection on this fixture set and misses two deliberately invalid paths by
  treating DNP and zero-ohm components as pull-ups. Keep no cohort dependency; the local rule
  already applies a fitted-state and resistance window and requires an explicit active-low input.
- **Applicability and boundary:** The synthetic pin belongs to a W25Q80BV-style flash device.
  Winbond's
  [W25Q80BV datasheet, section 4.1](https://www.winbond.com/upload/technical-support/f0f72951-b845-42ea-9010-faaeab26872f.pdf#page=7)
  says `/CS` must track VCC at power-up and describes a pull-up for cases where it is needed. This
  does not state that every board needs an external part; host reset-time drive must be reviewed.
  The fixture tests parser behavior, not a complete flash circuit or power sequence. Native KiCad
  import, ERC, and netlist comparison remain unavailable.

### Recorded trial: kicad-happy PS-001 power-sequence cycle

- **Candidate and provenance:** `aklofas/kicad-happy`, commit
  `3cf837b2d6577d1369a45a36d5e9bac0e06ff5b6`, declares MIT in its
  [pinned license file](https://github.com/aklofas/kicad-happy/blob/3cf837b2d6577d1369a45a36d5e9bac0e06ff5b6/LICENSE).
  The pinned `validation_detectors.py` SHA-256 is
  `c62fd47cbafb506c730a34bcd6e07c36f8e550c50a0dd913402c326d8b996868`; the
  pinned `detector_helpers.py` SHA-256 is
  `68fdc890755b53be1e25f5a7d07f72a2a8ca30dc5b0b67f4e2dfafebbe4ebc63`.
- **Trial boundary:** Executed the source's `validate_power_sequencing`,
  `_get_pin_net`, and `match_ic_keywords` functions with a small synthetic
  `AnalysisContext` and an explicitly supplied regulator inventory. No package
  was installed, no candidate source was added to this repository, and no
  project design data was used. The candidate parser and regulator-discovery
  pipeline were not exercised.
- **Observed result:** The mutual-enable synthetic fault produced two `PS-001`
  cycle findings for the same two-stage cycle, one from each start node. The
  acyclic control produced no finding; repeated calls with the same input order
  returned the same summaries. No field precision, reviewer effort, or
  installation cost was measured.
- **Incremental disposition:** The detector's inferred regulator-output to
  enable-edge idea is useful when a project maps its exact stage endpoints but
  omits a dependency edge. LINT-062 adopts only this bounded prompt within the
  existing project-authored map: exact matching mapped endpoints form an
  output-to-enable cycle, and the local rule reports one `REVIEW`. It does not
  discover regulators from device names or create project requirements. The
  local prompt now passes a synthetic three-stage native export on pinned
  KiCad 10.0.0 and 10.0.5. The candidate's duplicate cycle emission and `error`
  severity are not adopted.
- **Remaining limits:** With no `power_sequence_map`, this remains an explicit
  coverage question. The local check cannot find unmapped stages and does not
  establish enable polarity, alternative control paths, startup state, timing,
  or physical behavior. One synthetic control does not estimate false-positive
  rate.

### Recorded trial: kicad_skills `analog.no_dc_path`

- **Candidate and provenance:** `sabas0ba/kicad_skills`, commit
  `53d1af8bc550f60415b4b8e51a6d2d5924ada03f`, package version `0.1.0`, declared
  Apache-2.0. The pinned
  [rule source](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/src/eda_toolkit/kicad/sch_review.py)
  has SHA-256
  `fd7427eb29ee099e3cb8868869be8e8b75ed7d72aeba07ad1b4fa5a8e8597d54`; the
  pinned license file has SHA-256
  `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`.
- **Installation and supported versions:** The current upstream README
  documents a Docker/Bash wrapper, a first-use image build of about five
  minutes, no network inside the container, and KiCad 9.0.9/10.0.4 image tags.
  The official container workflow was not built or run in this trial. Instead,
  the source package was built and installed without dependencies into an
  isolated Python 3.11 environment under `/private/tmp`, using the exact
  setuptools 83.0.0 build-backend pin from the candidate source. This measured
  only the `--no-cli` geometry-fallback path; the candidate's KiCad version
  compatibility remains untested.
- **Invocation and data boundary:** Ran
  `python -I -m eda_toolkit.cli sch review --no-cli --json --output <report> <fixture>`
  with the isolated interpreter against the three tooling-owned fixtures below.
  Their source hashes and native reproduction evidence are in the
  [fixture record](../tests/fixtures/design_lint/net-dc-reference/README.md).
  The checkout, environment, reports, and temporary files stayed under
  `/private/tmp`. No project design data, candidate source, fixture, or runtime
  dependency was added to this repository.
- **Observed results:** `analog.no_dc_path` appeared on the fitted-capacitor
  fault, stayed quiet on the output-driver control, and also appeared on the
  DNP-capacitor control. The DNP result is an overbroad warning against the
  local fitted-component predicate: the candidate groups `C`/`J`/`P` reference
  prefixes, requires a capacitor-prefixed pin, and does not inspect DNP state
  or exact symbol identity. The local rule reports the same fitted fault and
  excludes the DNP part. Local native KiCad 10.0.0/10.0.5 runs independently
  confirm the DNP control retains `C1`'s DNP flag and remains quiet; both
  candidate and local results remain heuristic prompts, not proof that a
  physical interface needs bias.
- **Incremental-value result:** No unique detection was demonstrated. The candidate duplicates the
  local finding on the fault and adds a DNP warning that the local fitted-part predicate
  intentionally suppresses. Its reports are pinned here for the fault
  (`73db4f5604b60adaaedc21ea807946669721cb3a27c433836a9c2ac302af6d29`), output-driver control
  (`6656ec89a49d24b69ce7d319a2709f1c3c59f22410449a9831c3162d3908d4b0`), and DNP control
  (`0406e85fcb7a8c4e82aba8d164864fa94cecdde80e4e4bdc63ef81da3127a702`). Do not adopt a runtime
  dependency for this rule.
- **Still unmeasured:** The official container build and invocation, native
  candidate netlist export, reviewer effort, behavior across the advertised
  KiCad matrix, and results on approved non-proprietary project data. The local
  native fixture result is not a field false-positive estimate.

### Recorded trial: kicad_skills `analog.missing_decoupling`

- **Candidate and provenance:** `sabas0ba/kicad_skills`, commit
  `53d1af8bc550f60415b4b8e51a6d2d5924ada03f`, package version `0.1.0`, declared
  Apache-2.0. The pinned implementation is in the same
  [rule source](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/src/eda_toolkit/kicad/sch_review.py)
  as the `analog.no_dc_path` trial and has SHA-256
  `fd7427eb29ee099e3cb8868869be8e8b75ed7d72aeba07ad1b4fa5a8e8597d54`.
- **Installation and invocation:** Installed into the same isolated temporary
  Python 3.11 environment with `--no-build-isolation --no-deps`. The direct
  `python -I -m eda_toolkit.cli sch review --no-cli --json --output <report>
  <fixture>` invocation uses geometry fallback; it does not exercise the
  candidate Docker wrapper, KiCad CLI export, or native ERC. Reports were
  repeated and were byte-identical. Candidate source, environment, and reports
  remained outside this repository.
- **Inputs and results:** Six tooling-owned schematics in
  `tests/fixtures/design_lint/cohort-power-pin-dc/` cover no-cap and fitted-cap
  controls, an unrecognized-rail case, a source-backed fault/control pair, and
  a source-backed DNP-capacitor case. The candidate flags both fitted no-cap
  rails, stays quiet on fitted-cap controls and unrecognized `LOCAL_A`, and
  also stays quiet when the only capacitor is DNP. The two no-cap commands exit
  2 because an unrelated `power.no_ground` finding is an error; their JSON
  still contains the targeted warning. Report hashes and per-fixture outcomes
  are in the [fixture record](../tests/fixtures/design_lint/cohort-power-pin-dc/README.md).
- **Incremental-value result:** No unique detection over LINT-046 was shown.
  The fitted source-backed fault/control results duplicate the local
  review/control behavior. The DNP case exposes a candidate blind spot: its
  capacitor-prefix heuristic does not account for population state. Native
  KiCad 10.0.0 and 10.0.5 exports retain the DNP flag; LINT-046 still emits a
  rail-level review because no fitted capacitor connects the supply to return.
  This is synthetic regression evidence, not proof that a real board requires
  decoupling. Do not add a runtime dependency.
- **Still unmeasured:** The documented Docker workflow, native candidate
  export, advertised KiCad version matrix, reviewer effort, and behavior on
  approved non-proprietary project data. The fallback trial does not measure
  field precision.

### Recorded trial: kicad_skills `analog.clock_no_series_resistor`

- **Candidate and provenance:** `sabas0ba/kicad_skills`, commit
  `53d1af8bc550f60415b4b8e51a6d2d5924ada03f`, package version `0.1.0`, declared
  Apache-2.0. The rule source and license hashes match the earlier
  `analog.no_dc_path` trial. Its implementation selects `X` references or
  `Oscillator:` library symbols, then judges only output-net component
  membership; it does not read a project-authored path map, DNP state, or
  resistor value.
- **Installation and version boundary:** Reused the isolated Python 3.11.16
  environment at `/private/tmp/eda-cohort-trial-venv` from the previous
  `kicad_skills` trial, built with its setuptools 83.0.0 pin and installed with
  `--no-build-isolation --no-deps`. Ran
  `python -I -m eda_toolkit.cli sch review --no-cli --json`; KiCad CLI was not
  available, so the result used geometry fallback without ERC or native
  netlist evidence. The Docker API socket returned permission denied, so the
  documented container workflow and advertised KiCad versions were not
  exercised.
- **Inputs and repeatability:** Seven tooling-authored schematics in
  `tests/fixtures/design_lint/cohort-clock-series/` cover direct output,
  direct output with a shunt pull, a fitted series-resistor control, a
  trial-designated direct-drive alternative, a DNP series component,
  a 1 MOhm series component, and a passive crystal. Every JSON report was
  byte-identical across two runs. Exact source and report hashes are in the
  [fixture record](../tests/fixtures/design_lint/cohort-clock-series/README.md).
- **Observed result:** The rule reported both direct-load fixtures, including
  the synthetic direct-drive alternative that the trial setup permits. It
  correctly reported that a shunt pull was not a series element,
  stayed quiet for the fitted series control and crystal control, and missed
  the DNP and 1 MOhm series-component cases. This is a fixture-relative
  over-prompt and two bounded predicate gaps, not a field false-positive rate
  or an electrical determination that any specific series value is required.
- **Incremental disposition:** The candidate supplies an understandable
  discovery hint, but does not compare a source-bound project expectation and
  cannot honor per-part direct-drive applicability. The synthetic run does not
  justify a generic first-party rule or a runtime dependency. A project-owned
  map could still compare exact output/load pins, direct-versus-series choice,
  part identity, DNP state, and a reviewed value range; design that separately
  only if a project has a reviewed clock-output requirement.
- **Still unmeasured:** Native KiCad netlist/ERC behavior, the documented
  candidate container workflow, reviewer effort, applicability on exact parts,
  and results on approved non-proprietary designs. No product or proprietary source
  was used.

### Expanded native synthetic recheck (2026-10-09)

- **Pinned runtime:** Rechecked the same public commit and package in a fresh
  Python 3.11.16 environment under `/private/tmp`, using setuptools 83.0.0 and
  `--no-build-isolation --no-deps`. The selected analyzer was invoked through
  the installed package's `ReviewContext` with host KiCad CLI 10.0.6. The
  candidate source and its Apache-2.0 license hashes match the pinned values
  above. This does not exercise its full dependency installation or Docker
  wrapper.
- **Synthetic inputs:** The 11 schematics under
  [`tests/fixtures/design_lint/cohort-clock-series-native/`](../tests/fixtures/design_lint/cohort-clock-series-native/README.md)
  are rendered from
  `tests/design_lint_fixtures/clock_series_trial.py`. The new
  `test_design_lint_clock_series_trial.py` checks that the committed sources
  match the generator. Its native cases compare every exported pin-to-net
  assignment with the authored synthetic topology and require zero ERC errors.
  All 11 exports matched and all 11 ERC reports had zero errors; only
  `Synthetic` library registration warnings remain.
- **Candidate result:** The targeted heuristic was run twice per case using
  native netlists; all 11 results were repeatable. It prompted on direct load,
  direct load with a test point, a shunt pull, a resistor on an unrelated net,
  and a bypassed series resistor. It also prompted on the fixture-authorized
  direct-drive control. It stayed quiet on the fitted series controls, but
  missed the bead mislabeled with an `R` reference, the DNP resistor, and the
  1 MOhm resistor. The allowed-direct result is a fixture-relative over-prompt;
  the three quiet fault cases are candidate predicate gaps.
- **Prior fixture issue:** Native ERC also found two undriven power-input
  errors in the historical `series-x-control.kicad_sch`. Its `+3V3` local label
  is on the same wire as X1's output and VDD pin, with a multiple-net-name
  warning. The earlier hash-pinned no-CLI record remains unchanged; all new
  cases were authored separately.
- **Reproducibility record:** The target-only report was identical over two
  independent native evaluations of every case. Per-source hashes, findings,
  ERC counts, and the aggregate output digest are in the expanded fixture
  README. Generated JSON stays under ignored `build/`.
- **Disposition:** No general clock-series rule or runtime dependency is
  adopted. Tooling has no existing clock-series map to compare, and the
  candidate itself cannot distinguish a part-approved direct path or verify
  fitted part identity, DNP state, or value. Exact part applicability, reviewer
  effort, full installation cost, and behavior on approved external designs
  remain open.

### Recorded trial: kicad-happy `GP-001` narrow reference-plane void

- **Candidate and provenance:** `aklofas/kicad-happy` tag `v2.3.1`, commit
  `06840467ad0f5d76af45f64449b1f5ecb10f052f`, declared MIT; the pinned
  `LICENSE` SHA-256 is
  `f542344efc2d21d18c81507e8168ab256c32ece6e7acb1bc8bde71950c9b6bb5`.
  The trial analyzed `skills/kicad/scripts/analyze_pcb.py` (SHA-256
  `943ae5f9c2db2f394b3965d13f68ae0e9e2f246c7773a725f9b9aa6116f878cd`)
  and `skills/emc/scripts/emc_rules.py` (SHA-256
  `9d77a407d6a8687f0e21b989e5dec18ed4e3f2c9f962da355a4338836deae2d1`).
  Its README documents PCB analysis for KiCad 6 through 10. The candidate says
  its analysis scripts need Python 3.10+ and no required packages; the trial
  cloned the repository under `/private/tmp` and invoked the selected scripts
  directly, without installing or copying candidate code into Tooling.
- **Inputs and invocation:** Two synthetic two-layer boards use a
  2 mm F.Cu `DATA` segment, a B.Cu `GND` zone, and the same endpoint through-via
  clearance. The control has continuous copper apart from that expected
  clearance. The fault adds a 0.2 mm notch across the route midpoint. Input
  board SHA-256 values are `2ac9f1f5680219ee04e3a27ac398922dbeede4abfd41a478a6b35eb035cc6113`
  (control) and `4d1a2f44dcc8f4eb8605d0668d3bb1556c94d49c849308b88082f31a2252a7fc`
  (fault). The selected analyzer was run with `python3.11 -I
  skills/kicad/scripts/analyze_pcb.py --full --only-deterministic
  --gp001-debug <board>` and its EMC consumer was run separately. Candidate
  The two candidate JSON output hashes repeated byte-for-byte. Control:
  `7bb3046edbde5db9ff20898ca92e1fef37d000b58d9af20c79f5386d071b85fb`;
  fault: `6d67504f9ce78180c283d9808fc373b44f4cc3319e03cfc2e87b00ee005d38da`.
  The original output receipts remain in temporary storage; only
  hashes and synthetic fixture identities are retained here.
- **Observed result:** GP-001 samples at a fixed 2 mm interval. On this 2 mm
  route it inspected only the two endpoints: the first sample was credited to
  the via's antipad, and the second found plane copper. It emitted no GP-001
  finding for either input, missing the narrow midpoint void. The EMC consumer
  also emitted “Return path analysis data not available” for both no-finding
  reports because the producer omits the empty analysis section; this is
  inconclusive evidence status, not a second electrical finding. Candidate
  outputs were deterministic across repeated runs.
- **First-party comparison:** LINT-058 measured the same native source-bound
  geometry with exact polygon/centerline intersection. With a fixture-only
  0.65 threshold, the intact control measured `2799/4000` and passed; the
  notched fault measured `2399/4000` and remained `REVIEW`. Both reports retain
  the endpoint via-hole context while counting its clearance as uncovered.
  Board hashes match the fixtures
  `kicad_tooling/hwrepo/fixtures/pcb-reference-narrow-void-control.kicad_pcb`
  and `...-fault.kicad_pcb`. The native probe snapshots repeated exactly on
  the installed KiCad 10.0.6 compatibility environment, with hashes
  `0e181b461e407af820a73335ea092d42488868231a58ed9bffef62dffb3fdbc0`
  (control) and `469f8970fe5e699172071d9771712b3e9b2e5a2cbb51e4d67b681d55a161bce9`
  (fault). A hosted repeat lane now runs the fault/control pair on the pinned
  KiCad 10.0.0 and 10.0.5 images. The first-party LINT-058 native lane passed
  in tag `v0.5.0rc193` (GitHub Actions run `38308617935`); the tag resolved to
  `pcb.reference_plane_coverage` and enabled native PCB fixtures. Its tests
  repeated the via-antipad and narrow-void native fault/control cases on both
  pinned versions. This closes source-to-native repeatability for our mapped
  geometry check. The kicad-happy GP-001 runtime trial itself remains the
  separately recorded v2.3.1 run; it was not rerun on those KiCad images.
- **Disposition and limits:** The selected cohort heuristic misses this
  deliberately narrow defect; this comparison justifies retaining the
  first-party exact-geometry rule and regression pair. It does not establish a
  field miss rate, endorse the fixture's threshold for product boards, or
  prove return-current continuity. No cohort implementation, source board,
  proprietary project, or product expectation was adopted. Reviewer effort and
  long-term maintenance cost remain unmeasured.

### Recorded runtime trial: STM32-KiCad-Pin-Checker parser (2026-10-20)

- **Pinned source:** `jbmata/STM32-KiCad-Pin-Checker` commit
  [`f0018b5b4334caa5eeb619f9c0059dd7ae4363eb`](https://github.com/jbmata/STM32-KiCad-Pin-Checker/tree/f0018b5b4334caa5eeb619f9c0059dd7ae4363eb).
  The upstream README declares MIT; this revision has no separately tracked
  license file. Only `ioc.py` and `compare.py` were loaded from an external
  checkout after SHA-256 verification. The trial did not install the GUI,
  execute its netlist parser, invoke KiCad, or read project data.
- **Synthetic cases:** The candidate parser receives two order-reversed
  assignments whose suffixes identify the same physical PA13 pin but give
  conflicting signals, and one CubeMX escaped-space key for PH0. The local
  LINT-050 parser is run on the same fixture bytes.
- **Observed result:** Candidate `compare` reports `WARNING` for the first
  order and `OK` for the reversed order because a later assignment replaces
  the earlier normalized pin value. The local parser reports the collision
  for both orders. The candidate returns an empty pin map for the escaped PH0
  key; the local parser recognizes PH0. The opt-in trial passed twice, with
  two tests passing on each run.
- **Disposition and limits:** No incremental detection gain or adoption value
  was demonstrated. Keep the first-party LINT-050 parser and its order-stable
  collision coverage; do not add an external dependency. The trial establishes
  behavior only for these parser inputs, not GUI usability, full application
  correctness, reviewer effort, or applicability across external projects.
  Source hashes and invocation are in the
  [trial fixture record](../tests/fixtures/design_lint/cohort-stm32-pin-checker/README.md).

The shipped `kicad_tooling/hwrepo/design-lint-rules.json` catalog currently
contains 224 active rules. Each entry has a deterministic predicate, evidence
adapter, exact supported KiCad profile boundary, maturity, limitations,
implementation references, and named synthetic fault and valid-control tests.
Of the 224 active rules, 176 default to `review`, 47 to `off`, and
`pcb.required_fitted_reference` to `block`. Off-by-default checks include
schematic geometry, generic peer assignment, selected component topology
reviews such as the BJT base-bias and base/collector same-net prompts, and
board-only footprint review; the
catalog is authoritative for each rule's default.
The report carries this catalog and a SHA-256 digest of its packaged bytes.
Tests assert that catalog IDs match the closed policy type, each active rule is
reachable from a synthetic fault case, and every named fixture still exists and
runs. `synthetic_validated` means regression-tested against authored fixtures;
it does not claim field validation or effectiveness against private boards.

## Source links

[antmicro-cm4]: https://github.com/antmicro/cm4-baseboard/tree/d248c2921e8e7f4c9b30c96ea5f376d9b2780f1e
[calcumaker-design]: https://github.com/calcumaker/calcumaker/blob/113a283/DESIGN.md
[calcumaker-display-floorplan]: <https://github.com/calcumaker/calcumaker/blob/113a283/hardware/calcumaker-display/FLOORPLAN.md>
[calcumaker-hardware]: https://github.com/calcumaker/calcumaker/tree/113a283/hardware
[calcumaker-license]: https://github.com/calcumaker/calcumaker/blob/113a283/hardware/LICENSE
[calcumaker-revision]: https://github.com/calcumaker/calcumaker/commit/113a283
[calcumaker-wiring-review]: <https://github.com/calcumaker/calcumaker/blob/113a283/hardware/WIRING_REVIEW.md>
[happy-changelog]: https://github.com/aklofas/kicad-happy/blob/main/CHANGELOG.md
[happy-cp003-commit]: https://github.com/aklofas/kicad-happy/commit/06840467ad0f5d76af45f64449b1f5ecb10f052f
[happy-cp003-license]: <https://github.com/aklofas/kicad-happy/blob/06840467ad0f5d76af45f64449b1f5ecb10f052f/LICENSE>
[happy-cp003-release]: https://github.com/aklofas/kicad-happy/releases/tag/v2.3.1
[happy-cp003-source]: <https://github.com/aklofas/kicad-happy/blob/06840467ad0f5d76af45f64449b1f5ecb10f052f/skills/kicad/scripts/analyze_pcb.py#L5796-L6103>

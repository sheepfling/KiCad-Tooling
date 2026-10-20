# STM32-KiCad-Pin-Checker parser trial

This opt-in LINT-031 comparison executes two upstream parser modules against
the synthetic `.ioc` inputs in
[`stm32-pin-map`](../stm32-pin-map/README.md). No upstream source, project
example, GUI, or dependency is stored in this repository.

## Pinned candidate and boundaries

- Repository: [jbmata/STM32-KiCad-Pin-Checker](https://github.com/jbmata/STM32-KiCad-Pin-Checker)
- Revision: `f0018b5b4334caa5eeb619f9c0059dd7ae4363eb` in the
  [upstream repository](https://github.com/jbmata/STM32-KiCad-Pin-Checker).
- Upstream README declares MIT; this revision has no separately tracked license file.
- Only `ioc.py` and `compare.py` are loaded, after the test verifies their hashes.
- The trial does not install or launch the GUI, execute `netlist.py`, run KiCad,
  or inspect any project checkout.

## Pinned source hashes

- `ioc.py`: `6926aa6a34f20576fd433898cc8e4fdfb9da5dd06aee3ff307decc5b22013c84`
- `compare.py`: `24f10fc5e494c9ec5671dae1b1ea4341712ad0111ac020ab314e7cbb73574a15`

## Observed behavior

The two PA13 fixtures assign conflicting signals through `PA13-JTMS` and
`PA13-SWDIO`. With a synthetic hardware map of `PA13` to `SYS_JTMS-SWDIO`, the
candidate comparison returns `WARNING` for one line order and `OK` for the
reverse order. Its parser retains whichever normalized pin assignment appears
last. The local LINT-050 parser reports a conflicting-assignment issue for
both orders.

The escaped PH0 fixture is ignored by the candidate parser, which returns an
empty map. The local parser recognizes PH0 and reports no parse issue.

The opt-in runtime tests passed twice (`2 passed` per run). They are source
behavior probes, not an evaluation of the complete desktop application. They
show no incremental detection gain over LINT-050 and do not measure reviewer
effort or project applicability.

## Reproduce

Set the environment variable to an external checkout of the exact pinned
revision. The test fails if either loaded source hash differs and skips when
the variable is unset.

    KICAD_STM32_PIN_CHECKER_ROOT=/path/to/pinned/checkout \
      .venv/bin/python -I -B -m pytest -q -m cohort_trial \
      tests/test_design_lint_cohort_stm32_candidate.py

"""Electrical charts use actual simulator vectors and keep derived AC phase explicit."""

from __future__ import annotations

import importlib.util
import math
import tempfile
import unittest
from itertools import pairwise
from pathlib import Path

from kicad_tooling.hwrepo.electrical_plot import _complex_phase, _panels, render_case
from kicad_tooling.hwrepo.models import FrequencyAnalysis, SimulationMeasure, TransientAnalysis
from kicad_tooling.hwrepo.waveform_data import WaveformData, WaveformSeries

_HASH = "0" * 64
_SOURCE = {"projects/demo/kicad/demo.kicad_sch": _HASH}
_MODELS = {"projects/demo/tests/electrical/model.cir": _HASH}
_DECK = next(iter(_MODELS))


def _measure(expression: str, unit: str, start: float, stop: float) -> SimulationMeasure:
    return SimulationMeasure(
        id="response",
        expression=expression,
        statistic="max",
        unit=unit,
        start=start,
        stop=stop,
        minimum=-1,
        maximum=2,
    )


def _transient(unit: str = "A") -> TransientAnalysis:
    return TransientAnalysis(
        id="startup",
        basis="Synthetic test circuit",
        deck=_DECK,
        source_sha256=_SOURCE,
        model_sha256=_MODELS,
        step_s=0.1,
        stop_s=1.0,
        measures=(_measure("-i(vrail)", unit, 0, 1),),
    )


def _frequency(expression: str = "db(v(out)/v(in))", unit: str = "dB") -> FrequencyAnalysis:
    return FrequencyAnalysis(
        id="response",
        basis="Synthetic transfer function",
        deck=_DECK,
        source_sha256=_SOURCE,
        model_sha256=_MODELS,
        start_hz=1,
        stop_hz=100,
        measures=(_measure(expression, unit, 1, 100),),
    )


class ElectricalPlotTests(unittest.TestCase):
    def test_transient_uses_indexed_waveform_not_scalar_measurement(self) -> None:
        data = WaveformData(
            axis_name="time",
            axis=(0.0, 0.5, 1.0),
            series=(
                WaveformSeries(name="check0", unit="notype", values=(100 + 0j, 0j, 0j)),
                WaveformSeries(name="i(value0)", unit="current", values=(0j, 2 + 0j, 1 + 0j)),
            ),
        )
        (panel,) = _panels(data, _transient())
        self.assertEqual(panel.values, (0.0, 2.0, 1.0))
        self.assertTrue(panel.comparable_limits)
        self.assertIsNone(panel.phase)

    def test_ac_gain_has_explicit_derived_transfer_phase(self) -> None:
        data = WaveformData(
            axis_name="frequency",
            axis=(1.0, 10.0, 100.0),
            series=(
                WaveformSeries(name="value0", unit="decibel", values=(0j, -3 + 0j, -6 + 0j)),
                WaveformSeries(name="v(in)", unit="voltage", values=(1 + 0j,) * 3),
                WaveformSeries(name="v(out)", unit="voltage", values=(1 + 0j, 1 - 1j, 0 - 1j)),
            ),
        )
        (panel,) = _panels(data, _frequency())
        self.assertEqual(panel.values, (0.0, -3.0, -6.0))
        self.assertTrue(panel.comparable_limits)
        self.assertEqual(panel.phase_label, "Derived phase of v(out)/v(in) (rad)")
        self.assertIsNotNone(panel.phase)
        assert panel.phase is not None
        self.assertAlmostEqual(panel.phase[0], 0)
        self.assertAlmostEqual(panel.phase[1], -math.pi / 4)
        self.assertAlmostEqual(panel.phase[2], -math.pi / 2)

    def test_complex_ac_trace_is_derived_without_mislabeling_limits(self) -> None:
        data = WaveformData(
            axis_name="frequency",
            axis=(1.0, 10.0, 100.0),
            series=(
                WaveformSeries(name="value0", unit="notype", values=(1 + 0j, 0.7 - 0.7j, 0 - 1j)),
            ),
        )
        (panel,) = _panels(data, _frequency("v(out)/v(in)", "ratio"))
        self.assertEqual(panel.values, (1.0, math.hypot(0.7, 0.7), 1.0))
        self.assertFalse(panel.comparable_limits)
        self.assertEqual(panel.phase_label, "Derived phase of value0 (rad)")

    def test_rejects_missing_or_inconsistent_waveform_instead_of_charting_check(self) -> None:
        case = _transient()
        for data, message in (
            (
                WaveformData(
                    axis_name="time",
                    axis=(0.0, 0.5, 1.0),
                    series=(WaveformSeries(name="check0", unit="notype", values=(1 + 0j,) * 3),),
                ),
                "Expected exactly one waveform",
            ),
            (
                WaveformData(
                    axis_name="time",
                    axis=(0.0, 0.5, 1.0),
                    series=(
                        WaveformSeries(name="i(value0)", unit="voltage", values=(1 + 0j,) * 3),
                    ),
                ),
                "native unit",
            ),
            (
                WaveformData(
                    axis_name="time",
                    axis=(0.0, 0.5, 1.0),
                    series=(
                        WaveformSeries(name="i(value0)", unit="current", values=(1 + 0j,) * 2),
                    ),
                ),
                "sample count",
            ),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                _panels(data, case)

    def test_rejects_complex_decibel_trace(self) -> None:
        data = WaveformData(
            axis_name="frequency",
            axis=(1.0, 10.0, 100.0),
            series=(WaveformSeries(name="value0", unit="decibel", values=(0j, 1 + 1j, 2 + 2j)),),
        )
        with self.assertRaisesRegex(ValueError, "scalar ngspice expression"):
            _panels(data, _frequency("db(v(out))", "dB"))

    def test_phase_unwrap_keeps_a_continuous_frequency_response(self) -> None:
        degrees = (170, 179, -179, -170)
        values = tuple(
            complex(math.cos(math.radians(angle)), math.sin(math.radians(angle)))
            for angle in degrees
        )
        phases = _complex_phase(values)
        self.assertEqual(len(phases), 4)
        self.assertTrue(all(right > left for left, right in pairwise(phases)))
        self.assertAlmostEqual(phases[-1], math.radians(190))

    @unittest.skipUnless(
        importlib.util.find_spec("matplotlib"), "optional Matplotlib not installed"
    )
    def test_headless_png_and_svg_show_limits_and_derived_phase(self) -> None:
        data = WaveformData(
            axis_name="frequency",
            axis=(1.0, 10.0, 100.0),
            series=(
                WaveformSeries(name="value0", unit="decibel", values=(0j, -3 + 0j, -6 + 0j)),
                WaveformSeries(name="v(in)", unit="voltage", values=(1 + 0j,) * 3),
                WaveformSeries(name="v(out)", unit="voltage", values=(1 + 0j, 1 - 1j, 0 - 1j)),
            ),
        )
        with tempfile.TemporaryDirectory(prefix="electrical-charts-") as directory:
            png, svg = Path(directory) / "chart.png", Path(directory) / "chart.svg"
            render_case(data, _frequency(), png, svg)
            self.assertEqual(png.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            content = svg.read_text(encoding="utf-8")
            for label in (
                "max lower limit -1 dB",
                "max upper limit 2 dB",
                "Derived phase",
                "Frequency (Hz)",
            ):
                self.assertIn(label, content)
            second = Path(directory) / "second.svg"
            render_case(data, _frequency(), Path(directory) / "second.png", second)
            self.assertEqual(svg.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()

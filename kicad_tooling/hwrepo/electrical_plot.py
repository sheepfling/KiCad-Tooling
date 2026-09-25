"""Headless charts for reviewed electrical simulation waveforms.

This module imports Matplotlib only when a chart is requested. The charts show
simulator output and the authored measurement windows; they do not certify a
physical board or recompute the acceptance result in the receipt.
"""
from __future__ import annotations

import math
import re
import textwrap
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from .electrical import SimulationCase
from .models import FrequencyAnalysis, SimulationMeasure, TransientAnalysis
from .waveform_data import WaveformData, WaveformSeries


@dataclass(frozen=True)
class _ChartPanel:
    measure: SimulationMeasure
    values: tuple[float, ...]
    label: str
    unit: str
    comparable_limits: bool
    phase: tuple[float, ...] | None = None
    phase_label: str | None = None


_NATIVE_UNITS: dict[str, set[str]] = {
    "V": {"voltage", "v"},
    "A": {"current", "a"},
    "W": {"power", "w"},
    "dB": {"decibel", "db"},
    "rad": {"phase", "radian", "radians", "rad", "notype"},
    "ratio": {"ratio", "dimensionless", "notype"},
}
_VECTOR = r"[vi]\([A-Za-z0-9_.]+\)"
_DB_RATIO = re.compile(rf"^db\(({_VECTOR})/({_VECTOR})\)$", re.IGNORECASE)
_DB_SINGLE = re.compile(rf"^db\(({_VECTOR})\)$", re.IGNORECASE)


def _indexed_trace(data: WaveformData, index: int) -> WaveformSeries:
    names = {f"value{index}", f"v(value{index})", f"i(value{index})"}
    matches = tuple(series for series in data.series if series.name.casefold() in names)
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one waveform for measurement {index}: "
            f"value{index}, v(value{index}), or i(value{index}); found {len(matches)}."
        )
    return matches[0]


def _complex_phase(values: tuple[complex, ...]) -> tuple[float, ...]:
    """Unwrap phase in radians without adding NumPy as a direct dependency."""
    phases = [math.atan2(value.imag, value.real) for value in values]
    if not phases:
        return ()
    result = [phases[0]]
    for previous, current in pairwise(phases):
        difference = current - previous
        while difference > math.pi:
            difference -= 2 * math.pi
        while difference < -math.pi:
            difference += 2 * math.pi
        result.append(result[-1] + difference)
    return tuple(result)


def _trace(data: WaveformData, name: str) -> WaveformSeries:
    matches = tuple(series for series in data.series if series.name.casefold() == name.casefold())
    if len(matches) != 1:
        raise ValueError(f"Cannot derive phase: missing or ambiguous waveform {name}.")
    return matches[0]


def _phase_from_expression(data: WaveformData, expression: str) -> tuple[tuple[float, ...], str] | None:
    compact = re.sub(r"\s+", "", expression)
    ratio = _DB_RATIO.fullmatch(compact)
    single = _DB_SINGLE.fullmatch(compact)
    match = ratio if ratio is not None else single
    if match is None:
        return None
    numerator_name = match.group(1)
    numerator = _trace(data, numerator_name)
    if ratio is None:
        return _complex_phase(numerator.values), f"Derived phase of {numerator_name} (rad)"
    denominator_name = ratio.group(2)
    denominator = _trace(data, denominator_name)
    values: list[complex] = []
    for top, bottom in zip(numerator.values, denominator.values, strict=True):
        if bottom == 0:
            raise ValueError(f"Cannot derive phase of {expression}: zero {denominator_name} sample.")
        values.append(top / bottom)
    return _complex_phase(tuple(values)), f"Derived phase of {numerator_name}/{denominator_name} (rad)"


def _is_real(value: complex) -> bool:
    return abs(value.imag) <= 1e-12 * max(1.0, abs(value.real))


def _panels(data: WaveformData, case: SimulationCase) -> tuple[_ChartPanel, ...]:
    expected = "time" if isinstance(case, TransientAnalysis) else "frequency"
    if data.axis_name != expected or len(data.axis) < 2:
        raise ValueError(f"Expected at least two {expected} samples for {case.id}.")
    if any(not math.isfinite(value) for value in data.axis):
        raise ValueError("Waveform axis contains a non-finite value.")
    if any(right <= left for left, right in pairwise(data.axis)):
        raise ValueError("Waveform axis must be strictly increasing.")
    if isinstance(case, FrequencyAnalysis) and data.axis[0] <= 0:
        raise ValueError("Frequency chart requires positive frequencies.")

    panels: list[_ChartPanel] = []
    for index, measure in enumerate(case.measures):
        series = _indexed_trace(data, index)
        if len(series.values) != len(data.axis):
            raise ValueError(f"Waveform {series.name} has a different sample count from its axis.")
        if any(not math.isfinite(value.real) or not math.isfinite(value.imag)
               for value in series.values):
            raise ValueError(f"Waveform {series.name} contains a non-finite value.")
        unit_tokens = series.unit.split()
        native_unit = unit_tokens[0].casefold() if unit_tokens else ""
        if native_unit not in _NATIVE_UNITS[measure.unit]:
            raise ValueError(
                f"Waveform {series.name} has native unit {series.unit!r}, "
                f"but measurement {measure.id} declares {measure.unit}."
            )
        tolerance = max(abs(measure.stop), 1e-15) * 1e-8
        if not (data.axis[0] <= measure.start + tolerance
                and data.axis[-1] >= measure.stop - tolerance
                and sum(measure.start - tolerance <= point <= measure.stop + tolerance
                        for point in data.axis) >= 2):
            raise ValueError(f"Waveform does not cover the {measure.id} measurement window.")

        complex_trace = any(not _is_real(value) for value in series.values)
        if isinstance(case, TransientAnalysis) and complex_trace:
            raise ValueError(f"Transient measurement {measure.id} has complex samples.")
        if complex_trace and measure.unit in {"dB", "rad"}:
            raise ValueError(
                f"Measurement {measure.id} uses {measure.unit} but has complex samples; "
                "author a scalar ngspice expression before charting it."
            )
        if complex_trace:
            panels.append(_ChartPanel(
                measure=measure, values=tuple(abs(value) for value in series.values),
                label=f"Derived magnitude of {series.name}", unit=measure.unit,
                comparable_limits=False, phase=_complex_phase(series.values),
                phase_label=f"Derived phase of {series.name} (rad)",
            ))
        else:
            derived = (_phase_from_expression(data, measure.expression)
                       if isinstance(case, FrequencyAnalysis) else None)
            panels.append(_ChartPanel(
                measure=measure, values=tuple(value.real for value in series.values),
                label=f"{series.name}: {measure.expression}", unit=measure.unit,
                comparable_limits=True,
                phase=derived[0] if derived else None,
                phase_label=derived[1] if derived else None,
            ))
    return tuple(panels)


def render_case(data: WaveformData, case: SimulationCase, png: Path, svg: Path) -> None:
    """Save PNG and SVG from a validated ngspice waveform and authored case.

    Each indexed ``valueN`` vector is plotted against the original axis. For a
    scalar result, authored limits are overlaid in the measure's own unit.
    Complex values show derived magnitude and phase; their scalar acceptance
    limits are not drawn on a quantity whose equivalence is unknown.
    """
    panels = _panels(data, case)
    try:
        from matplotlib import rc_context  # pyright: ignore[reportUnknownVariableType]
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except ImportError as exc:
        raise ValueError(
            "Charts require Matplotlib; install the optional charts extra with "
            "python -m pip install -e '.[charts]'."
        ) from exc

    count = sum(1 + (panel.phase is not None) for panel in panels)
    figure = Figure(figsize=(10, 2.8 * count + 0.9), layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots(count, 1, sharex=True, squeeze=False)
    x = data.axis
    # Average/RMS thresholds describe a measured interval, while an inrush
    # excursion can be orders of magnitude larger. Plot that interval in detail;
    # the complete sampled series remains available in the CSV export.
    detail_window = isinstance(case, TransientAnalysis) and any(
        measure.statistic in {"avg", "rms"} for measure in case.measures
    )
    if detail_window:
        first = min(measure.start for measure in case.measures)
        last = max(measure.stop for measure in case.measures)
        margin = (last - first) * 0.03
        visible = tuple(index for index, value in enumerate(x)
                        if first - margin <= value <= last + margin)
    else:
        visible = tuple(range(len(x)))
    shown_x = tuple(x[index] for index in visible)
    axis_label = "Time (s)" if isinstance(case, TransientAnalysis) else "Frequency (Hz)"
    position = 0
    for panel in panels:
        chart = axes[position, 0]
        position += 1
        chart.plot(shown_x, tuple(panel.values[index] for index in visible),
                   color="#155a85", linewidth=1.2, label=panel.label)
        chart.axvspan(panel.measure.start, panel.measure.stop, alpha=0.12,
                      color="#d39d27", label="Measured window")
        if panel.comparable_limits:
            if panel.measure.statistic == "pp":
                chart.text(0.99, 0.98,
                           (f"pp limits [{panel.measure.minimum}, {panel.measure.maximum}] "
                            f"{panel.unit} over shaded window"),
                           transform=chart.transAxes, horizontalalignment="right",
                           verticalalignment="top", fontsize=8)
            else:
                for label, limit, color in (("lower limit", panel.measure.minimum, "#247046"),
                                            ("upper limit", panel.measure.maximum, "#af3939")):
                    if limit is not None:
                        chart.hlines(limit, panel.measure.start, panel.measure.stop,
                                     color=color, linestyle="--", linewidth=1,
                                     label=(f"{panel.measure.statistic} {label} "
                                            f"{limit:g} {panel.unit}"))
        else:
            chart.text(0.99, 0.98, "Derived magnitude; limits apply to ngspice measure",
                       transform=chart.transAxes, horizontalalignment="right",
                       verticalalignment="top", fontsize=8)
        chart.set_ylabel(f"{panel.measure.id} ({panel.unit})")
        chart.grid(True, alpha=0.25)
        chart.legend(loc="best", fontsize=8)
        if panel.phase is not None:
            phase_chart = axes[position, 0]
            position += 1
            phase_chart.plot(shown_x, tuple(panel.phase[index] for index in visible),
                             color="#7d5596", linewidth=1.2, label=panel.phase_label)
            phase_chart.axvspan(panel.measure.start, panel.measure.stop,
                                alpha=0.12, color="#d39d27")
            phase_chart.set_ylabel("Phase (rad)")
            phase_chart.grid(True, alpha=0.25)
            phase_chart.legend(loc="best", fontsize=8)

    if isinstance(case, FrequencyAnalysis):
        for chart in axes[:, 0]:
            chart.set_xscale("log")
    axes[-1, 0].set_xlabel(axis_label)
    # Matplotlib leaves these keyword argument signatures partially untyped.
    subtitle = ("ngspice model output; measurement window detail, full samples in CSV"
                if detail_window else "ngspice model output")
    figure.suptitle(  # pyright: ignore[reportUnknownMemberType]
        textwrap.fill(f"{case.id}: {case.basis}", 105) + f"\n{subtitle}", fontsize=11,
    )
    png.parent.mkdir(parents=True, exist_ok=True)
    svg.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(png, dpi=160)  # pyright: ignore[reportUnknownMemberType]
    # Keep SVG internal IDs and metadata stable within a pinned Matplotlib version.
    with rc_context({"svg.hashsalt": f"electrical-{case.id}"}):
        figure.savefig(svg, metadata={"Date": None})  # pyright: ignore[reportUnknownMemberType]
    figure.clear()

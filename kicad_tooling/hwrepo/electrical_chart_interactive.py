"""Self-contained, bounded waveform explorer for retained simulation samples."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from html import escape
from itertools import pairwise
from typing import Literal

from .electrical_chart_models import ElectricalChartCase
from .electrical_plot import ChartPanel, plot_panels
from .electrical_simulation_models import FrequencyAnalysis, TransientAnalysis
from .waveform_data import WaveformData

DISPLAY_LIMIT = 4000


@dataclass(frozen=True, slots=True)
class InteractiveTrace:
    id: str
    label: str
    unit: str
    x: tuple[float, ...]
    y: tuple[float, ...]
    phase_deg: tuple[float, ...] | None
    window_start: float
    window_stop: float
    statistic: str
    minimum: float | None
    maximum: float | None


def display_indices(
    axis: tuple[float, ...], values: tuple[tuple[float, ...], ...], limit: int = DISPLAY_LIMIT
) -> tuple[int, ...]:
    """Keep endpoints and each selected quantity's extrema without exceeding a cap."""
    if len(axis) < 2 or not values or limit < 2 + 2 * len(values):
        raise ValueError("Display needs samples and room for every quantity's extrema")
    if any(len(item) != len(axis) for item in values):
        raise ValueError("Display quantities have different sample counts")
    if any(not math.isfinite(x) for x in axis) or any(
        right <= left for left, right in pairwise(axis)
    ):
        raise ValueError("Display axis must be finite and strictly increasing")
    if any(not math.isfinite(y) for item in values for y in item):
        raise ValueError("Display quantities must be finite")
    if len(axis) <= limit:
        return tuple(range(len(axis)))
    buckets = max(1, (limit - 2) // (2 * len(values)))
    step = math.ceil((len(axis) - 2) / buckets)
    selected = {0, len(axis) - 1}
    for start in range(1, len(axis) - 1, step):
        stop = min(start + step, len(axis) - 1)
        for quantity in values:
            selected.add(min(range(start, stop), key=quantity.__getitem__))
            selected.add(max(range(start, stop), key=quantity.__getitem__))
    return tuple(sorted(selected))


def interactive_trace(
    axis: tuple[float, ...], panel: ChartPanel, *, id: str, label: str
) -> InteractiveTrace:
    phase = tuple(math.degrees(value) for value in panel.phase) if panel.phase else None
    quantities = (panel.values, phase) if phase is not None else (panel.values,)
    indices = display_indices(axis, quantities)
    return InteractiveTrace(
        id=id,
        label=label,
        unit=panel.unit,
        x=tuple(axis[index] for index in indices),
        y=tuple(panel.values[index] for index in indices),
        phase_deg=tuple(phase[index] for index in indices) if phase is not None else None,
        window_start=panel.measure.start,
        window_stop=panel.measure.stop,
        statistic=panel.measure.statistic,
        minimum=panel.measure.minimum,
        maximum=panel.measure.maximum,
    )


def case_traces(
    data: WaveformData, case: TransientAnalysis | FrequencyAnalysis
) -> tuple[InteractiveTrace, ...]:
    return tuple(
        interactive_trace(data.axis, panel, id=panel.measure.id, label=panel.measure.id)
        for panel in plot_panels(data, case)
    )


def render_chart_index(
    project_id: str, source_sha256: str, cases: tuple[ElectricalChartCase, ...]
) -> str:
    rows = "".join(
        "<tr><th>"
        + escape(item.id)
        + "</th><td>"
        + item.status
        + "</td><td>"
        + (
            f'<a href="{escape(item.html, quote=True)}">Interactive view</a>'
            if item.html
            else escape(item.detail)
        )
        + "</td></tr>"
        for item in cases
    )
    listing = (
        f"<table><thead><tr><th>Case</th><th>Chart status</th><th>Review</th></tr></thead><tbody>{rows}</tbody></table>"
        if cases
        else "<p>No transient or AC cases were configured in this saved contract.</p>"
    )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Simulation waveform review</title><style>"
        "body{font:16px/1.5 system-ui;color:#193247;background:#f3f6f8;margin:0}"
        "main{max-width:1050px;margin:auto;padding:1.5rem}table{width:100%;border-collapse:collapse}"
        "th,td{text-align:left;border-bottom:1px solid #cedbe3;padding:.7rem}"
        "a{color:#075d76}code{overflow-wrap:anywhere}</style><main>"
        f"<h1>Simulation waveforms · {escape(project_id)}</h1>"
        "<p>Saved ngspice model output. The interactive views use bounded display points; "
        "the CSV exports retain every sample. Neither is physical validation.</p>"
        f"<p>Analysis receipt SHA-256: <code>{escape(source_sha256)}</code></p>"
        + listing
        + '<p><a href="charts.json">Structured chart receipt</a></p></main></html>'
    )


def render_interactive_chart(
    title: str,
    axis: Literal["time", "frequency"],
    traces: tuple[InteractiveTrace, ...],
    evidence: tuple[tuple[str, str], ...],
    downloads: tuple[tuple[str, str], ...],
) -> str:
    """Render one offline plot with trace selection, linked cursors, and x zoom."""
    if not traces or any(len(trace.x) < 2 for trace in traces):
        raise ValueError("Interactive chart needs at least one displayable trace")
    if len({trace.id for trace in traces}) != len(traces):
        raise ValueError("Interactive trace IDs must be unique")
    if axis == "frequency" and any(trace.x[0] <= 0 for trace in traces):
        raise ValueError("AC chart requires positive frequency")
    payload = (
        json.dumps(
            {"axis": axis, "traces": [asdict(trace) for trace in traces]},
            allow_nan=False,
            separators=(",", ":"),
        )
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    details = "".join(
        f"<tr><th>{escape(label)}</th><td><code>{escape(value)}</code></td></tr>"
        for label, value in evidence
    )
    links = " · ".join(
        f'<a href="{escape(href, quote=True)}">{escape(label)}</a>' for label, href in downloads
    )
    html = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
body{{font:15px/1.5 system-ui;color:#193247;background:#f3f6f8;margin:0}}
main{{max-width:1200px;margin:auto;padding:1.3rem}}
section{{background:#fff;border-radius:.6rem;padding:1rem;margin:1rem 0}}
svg{{display:block;width:100%;height:auto;background:#fff;touch-action:none;border:1px solid #d2dfe7}}
svg:focus{{outline:3px solid #1c7892}}.muted{{color:#536878}}
.controls{{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center}}
label{{display:inline-flex;gap:.3rem;align-items:center}}
#trace-controls{{display:flex;flex-wrap:wrap;gap:.9rem}}
.swatch{{display:inline-block;width:.7rem;height:.7rem;border-radius:50%}}
button,select{{font:inherit;padding:.25rem .5rem}}button:focus,input:focus,select:focus{{outline:2px solid #1c7892}}
table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid #dce5ea;padding:.45rem;text-align:left}}
code{{overflow-wrap:anywhere}}a{{color:#075d76}}
</style><main><h1>{escape(title)}</h1>
<p>Saved ngspice model output. The chart uses bounded display points; the CSV keeps every sample.
Cursor values are nearest displayed samples. No interpolation or physical validation is implied.</p>
<section><div class="controls"><label>Quantity <select id="unit"></select></label>
<span id="trace-controls" role="group" aria-label="Visible traces"></span>
<button id="reset" type="button">Reset zoom</button></div>
<p class="muted">Drag horizontally to zoom. Use the arrow keys on a plot to move the linked cursor.
Frequency uses a logarithmic axis; phase is unwrapped and shown in degrees.</p>
<p id="trace-info" class="muted"></p>
<h2>Magnitude or value</h2><svg id="value-plot" viewBox="0 0 1000 320" tabindex="0"
role="img" aria-label="Interactive waveform value plot"></svg>
<div id="phase-section"><h2>Phase (degrees)</h2><svg id="phase-plot" viewBox="0 0 1000 320"
tabindex="0" role="img" aria-label="Linked phase plot"></svg></div>
<p id="cursor-readout" aria-live="polite">Move over a plot to inspect saved display samples.</p></section>
<section><h2>Source and exports</h2><table><tbody>{details}</tbody></table>
<p>{links}</p></section>
<script type="application/json" id="plot-data">{payload}</script><script>"""
    return html + _INTERACTION + "</script></main></html>"


_INTERACTION = r"""
const data=JSON.parse(document.getElementById('plot-data').textContent);
const NS='http://www.w3.org/2000/svg', L=74, R=980, T=20, B=282;
const valuePlot=document.getElementById('value-plot'), phasePlot=document.getElementById('phase-plot');
const unitSelect=document.getElementById('unit'), controls=document.getElementById('trace-controls');
const readout=document.getElementById('cursor-readout');
const traceInfo=document.getElementById('trace-info');
const colors=['#146b9a','#c1532d','#6d50a0','#217c56','#a53b65','#7b661e'];
const units=[...new Set(data.traces.map(t=>t.unit))];
for(const unit of units){const option=document.createElement('option');option.value=unit;option.textContent=unit;unitSelect.append(option);}
let selected=new Set(), range=null, cursor=null, dragging=null;
function sx(x){return data.axis==='frequency'?Math.log10(x):x;}
function ux(x){return data.axis==='frequency'?10**x:x;}
function shown(){return data.traces.filter(t=>t.unit===unitSelect.value&&selected.has(t.id));}
function extent(){const traces=shown();if(!traces.length)return null;
 const lo=Math.min(...traces.map(t=>sx(t.x[0]))),hi=Math.max(...traces.map(t=>sx(t.x.at(-1))));
 return range||[lo,hi];}
function svg(tag,attrs,text){const node=document.createElementNS(NS,tag);
 for(const [key,value] of Object.entries(attrs))node.setAttribute(key,String(value));
 if(text!==undefined)node.textContent=text;return node;}
function mapx(x,domain){return L+(sx(x)-domain[0])/(domain[1]-domain[0])*(R-L);}
function sampleNear(t,x){let lo=0,hi=t.x.length-1;while(lo<hi){const mid=(lo+hi)>>1;
 if(t.x[mid]<x)lo=mid+1;else hi=mid;}if(lo>0&&Math.abs(sx(t.x[lo-1])-sx(x))<Math.abs(sx(t.x[lo])-sx(x)))lo--;return lo;}
function visibleValues(traces,field,domain){const values=[];for(const t of traces){const series=t[field];if(!series)continue;
 for(let i=0;i<t.x.length;i++)if(sx(t.x[i])>=domain[0]&&sx(t.x[i])<=domain[1])values.push(series[i]);}
 return values;}
function draw(plot,field,domain,traces){plot.replaceChildren();const values=visibleValues(traces,field,domain);
 if(!values.length){plot.append(svg('text',{x:500,y:160,'text-anchor':'middle'},'No displayed samples in this range'));return;}
 let ymin=Math.min(...values),ymax=Math.max(...values);if(ymin===ymax){const pad=Math.max(1,Math.abs(ymin)*.05);ymin-=pad;ymax+=pad;}
 const margin=(ymax-ymin)*.06;ymin-=margin;ymax+=margin;
 const py=y=>B-(y-ymin)/(ymax-ymin)*(B-T);
 if(traces.every(t=>t.window_start===traces[0].window_start&&t.window_stop===traces[0].window_stop)){
  const start=Math.max(domain[0],sx(traces[0].window_start)),stop=Math.min(domain[1],sx(traces[0].window_stop));
  if(stop>start)plot.append(svg('rect',{x:L+(start-domain[0])/(domain[1]-domain[0])*(R-L),
   y:T,width:(stop-start)/(domain[1]-domain[0])*(R-L),height:B-T,fill:'#d6ad36','fill-opacity':'.09'}));}
 for(let tick=0;tick<=4;tick++){const yy=T+(B-T)*tick/4,xx=L+(R-L)*tick/4;
  plot.append(svg('line',{x1:L,y1:yy,x2:R,y2:yy,stroke:'#dce5eb'}));
  plot.append(svg('text',{x:L-8,y:yy+4,'text-anchor':'end',fill:'#536878','font-size':12},(ymax-(ymax-ymin)*tick/4).toPrecision(4)));
  plot.append(svg('line',{x1:xx,y1:T,x2:xx,y2:B,stroke:'#e7edf1'}));
  plot.append(svg('text',{x:xx,y:B+23,'text-anchor':'middle',fill:'#536878','font-size':12},ux(domain[0]+(domain[1]-domain[0])*tick/4).toPrecision(4)));}
 const label=data.axis==='frequency'?'Frequency (Hz)':'Time (s)';
 plot.append(svg('text',{x:525,y:313,'text-anchor':'middle',fill:'#193247','font-size':13},label));
 plot.append(svg('text',{x:19,y:156,transform:'rotate(-90 19 156)','text-anchor':'middle',
  fill:'#193247','font-size':13},field==='phase_deg'?'Phase (°)':unitSelect.value));
 traces.forEach(t=>{const series=t[field];if(!series)return;
  const colorIndex=data.traces.filter(item=>item.unit===unitSelect.value).findIndex(item=>item.id===t.id);
  const points=[];for(let i=0;i<t.x.length;i++){const x=sx(t.x[i]);if(x>=domain[0]&&x<=domain[1])points.push([mapx(t.x[i],domain),py(series[i])]);}
  if(!points.length)return;const d=points.map((p,i)=>(i?'L':'M')+p[0].toFixed(2)+','+p[1].toFixed(2)).join(' ');
  plot.append(svg('path',{d,fill:'none',stroke:colors[colorIndex%colors.length],'stroke-width':2,'vector-effect':'non-scaling-stroke'}));});
 if(cursor!==null&&sx(cursor)>=domain[0]&&sx(cursor)<=domain[1])plot.append(svg('line',
  {x1:mapx(cursor,domain),y1:T,x2:mapx(cursor,domain),y2:B,stroke:'#333','stroke-dasharray':'5 4','pointer-events':'none'}));
}
function render(){const traces=shown(),domain=extent();if(!domain){valuePlot.replaceChildren();phasePlot.replaceChildren();
 document.getElementById('phase-section').hidden=true;traceInfo.textContent='Select a trace to plot.';
 readout.textContent='Select a trace to inspect saved display samples.';return;}
 traceInfo.textContent=traces.map(t=>t.label+': '+t.statistic+' window '+t.window_start+'–'+t.window_stop+
 (data.axis==='frequency'?' Hz':' s')+'; authored limits ['+(t.minimum??'none')+', '+(t.maximum??'none')+'] '+t.unit).join(' | ');
 draw(valuePlot,'y',domain,traces);const hasPhase=traces.some(t=>t.phase_deg!==null);
 document.getElementById('phase-section').hidden=!hasPhase;if(hasPhase)draw(phasePlot,'phase_deg',domain,traces);
 if(cursor!==null){const labels=traces.map(t=>{const i=sampleNear(t,cursor);
  return t.label+': '+t.y[i].toPrecision(7)+' '+t.unit+' at '+t.x[i].toPrecision(7)+
  (data.axis==='frequency'?' Hz':' s')+(t.phase_deg?' · '+t.phase_deg[i].toPrecision(6)+'°':'');});
 readout.textContent='Nearest displayed samples — '+labels.join(' | ');}}
function chooseUnit(){selected=new Set(data.traces.filter(t=>t.unit===unitSelect.value).map(t=>t.id));range=null;cursor=null;
 controls.replaceChildren();for(const [index,t] of data.traces.filter(t=>t.unit===unitSelect.value).entries()){
  const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=true;
  check.addEventListener('change',()=>{if(check.checked)selected.add(t.id);else selected.delete(t.id);range=null;render();});
  const swatch=document.createElement('span');swatch.className='swatch';swatch.style.background=colors[index%colors.length];
  label.append(check,swatch,document.createTextNode(t.label));controls.append(label);}render();}
unitSelect.addEventListener('change',chooseUnit);document.getElementById('reset').addEventListener('click',()=>{range=null;render();});
function fromPointer(event,plot){const rect=plot.getBoundingClientRect(),domain=extent();if(!domain)return null;
 const px=(event.clientX-rect.left)/rect.width*1000;const fraction=Math.max(0,Math.min(1,(px-L)/(R-L)));
 return ux(domain[0]+fraction*(domain[1]-domain[0]));}
for(const plot of [valuePlot,phasePlot]){
 plot.addEventListener('pointermove',event=>{if(dragging)return;const x=fromPointer(event,plot);if(x===null)return;cursor=x;render();});
 plot.addEventListener('pointerdown',event=>{dragging={plot,start:fromPointer(event,plot)};plot.setPointerCapture(event.pointerId);});
 plot.addEventListener('pointerup',event=>{if(!dragging||dragging.plot!==plot)return;
  const end=fromPointer(event,plot),start=dragging.start;dragging=null;
  if(start!==null&&end!==null&&Math.abs(sx(end)-sx(start))>1e-9){const a=Math.min(sx(start),sx(end)),b=Math.max(sx(start),sx(end));
   if((b-a)/(extent()[1]-extent()[0])>.01){range=[a,b];cursor=null;render();}}});
 plot.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  const trace=shown()[0];if(!trace)return;event.preventDefault();let i=cursor===null?0:sampleNear(trace,cursor);
  if(event.key==='Home')i=0;else if(event.key==='End')i=trace.x.length-1;
  else i=Math.max(0,Math.min(trace.x.length-1,i+(event.key==='ArrowRight'?1:-1)));
  cursor=trace.x[i];render();});}
chooseUnit();
"""

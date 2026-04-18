"""
Solar Tracker - Flask Web Server
Serves the dashboard and JSON API endpoint.
Run with: python app.py
"""
 
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, jsonify, render_template_string
 
DB_PATH = Path(__file__).parent / "solar.db"
MAX_DAYS = 7
SUNLIGHT_THRESHOLD_V = 1.0
POLL_INTERVAL = 30 # seconds — used to compute sun hours
 
app = Flask(__name__)
 
 
# ── Database helpers ───────────────────────────────────────────────────────────
 
def query_db(sql: str, params=()):
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
 
 
def get_readings(days: int = MAX_DAYS):
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return query_db(
        "SELECT timestamp, voltage_v, current_ma, power_mw FROM readings "
        "WHERE date(timestamp) >= ? ORDER BY timestamp ASC",
        (cutoff,),
    )
 
 
def compute_daily_sun(readings):
    """Return {date_str: sun_hours} for each day in readings."""
    daily = {}
    for r in readings:
        day = r["timestamp"][:10]
        if day not in daily:
            daily[day] = 0
        if r["voltage_v"] >= SUNLIGHT_THRESHOLD_V:
            daily[day] += POLL_INTERVAL # seconds
    return {d: round(s / 3600, 4) for d, s in daily.items()}
 
 
# ── API Routes ─────────────────────────────────────────────────────────────────
 
@app.route("/data")
def data():
    """Return last 7 days of raw readings as JSON."""
    readings = get_readings()
    daily_sun = compute_daily_sun(readings)
    return jsonify({
        "readings": readings,
        "daily_sun_hours": daily_sun,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
 
 
@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)
 
 
# ── Dashboard HTML ─────────────────────────────────────────────────────────────
 
DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Solar Tracker Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet" />
<style>
:root {
--bg: #0b0f14;
--surface: #131820;
--border: #1f2936;
--accent: #f5a623;
--accent2: #e8673c;
--text: #e8e4d9;
--muted: #6b7585;
--sun: #ffd166;
--card-glow: 0 0 40px rgba(245,166,35,0.08);
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
 
body {
background: var(--bg);
color: var(--text);
font-family: 'Syne', sans-serif;
min-height: 100vh;
overflow-x: hidden;
}
 
/* ── Noise texture overlay ── */
body::before {
content: '';
position: fixed; inset: 0; z-index: 0; pointer-events: none;
background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E");
opacity: 0.5;
}
 
.wrap { position: relative; z-index: 1; max-width: 1280px; margin: 0 auto; padding: 0 2rem; }
 
/* ── Header ── */
header {
border-bottom: 1px solid var(--border);
padding: 1.5rem 0;
display: flex; align-items: center; justify-content: space-between;
}
.logo {
display: flex; align-items: center; gap: 0.75rem;
}
.logo-icon {
width: 36px; height: 36px;
background: radial-gradient(circle, var(--sun) 0%, var(--accent2) 100%);
border-radius: 50%;
box-shadow: 0 0 20px rgba(255,209,102,0.4);
animation: pulse 3s ease-in-out infinite;
}
@keyframes pulse {
0%,100% { box-shadow: 0 0 20px rgba(255,209,102,0.4); }
50% { box-shadow: 0 0 36px rgba(255,209,102,0.75); }
}
.logo h1 { font-size: 1.25rem; font-weight: 800; letter-spacing: -0.01em; }
.logo h1 span { color: var(--accent); }
 
#status-badge {
font-family: 'Space Mono', monospace;
font-size: 0.72rem;
padding: 0.3rem 0.8rem;
border-radius: 999px;
background: var(--surface);
border: 1px solid var(--border);
color: var(--muted);
transition: all 0.4s;
}
#status-badge.live {
border-color: #2ecc71;
color: #2ecc71;
background: rgba(46,204,113,0.08);
}
 
/* ── Stat cards ── */
.cards {
display: grid;
grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
gap: 1rem;
margin: 2rem 0;
}
.card {
background: var(--surface);
border: 1px solid var(--border);
border-radius: 12px;
padding: 1.25rem 1.5rem;
box-shadow: var(--card-glow);
transition: transform 0.2s, border-color 0.2s;
}
.card:hover { transform: translateY(-2px); border-color: var(--accent); }
.card-label {
font-family: 'Space Mono', monospace;
font-size: 0.65rem;
text-transform: uppercase;
letter-spacing: 0.12em;
color: var(--muted);
margin-bottom: 0.4rem;
}
.card-value {
font-size: 1.75rem;
font-weight: 800;
color: var(--accent);
line-height: 1;
}
.card-unit {
font-size: 0.9rem;
font-weight: 400;
color: var(--muted);
margin-left: 0.2rem;
}
 
/* ── Charts ── */
.chart-grid {
display: grid;
grid-template-columns: 1fr;
gap: 1.5rem;
margin-bottom: 2rem;
}
.chart-card {
background: var(--surface);
border: 1px solid var(--border);
border-radius: 14px;
padding: 1.5rem;
box-shadow: var(--card-glow);
}
.chart-title {
font-size: 0.8rem;
font-family: 'Space Mono', monospace;
text-transform: uppercase;
letter-spacing: 0.1em;
color: var(--muted);
margin-bottom: 1rem;
}
.chart-title span { color: var(--accent); }
 
.plotly-graph-div { border-radius: 8px; overflow: hidden; }
 
/* ── Timestamp row ── */
#last-updated {
font-family: 'Space Mono', monospace;
font-size: 0.7rem;
color: var(--muted);
text-align: right;
padding: 0.5rem 0 2rem;
}
 
/* ── Empty state ── */
.empty {
text-align: center;
padding: 4rem 2rem;
color: var(--muted);
font-family: 'Space Mono', monospace;
font-size: 0.85rem;
}
</style>
</head>
<body>
<div class="wrap">
 
<!-- Header -->
<header>
<div class="logo">
<div class="logo-icon"></div>
<h1>Solar <span>Tracker</span></h1>
</div>
<div id="status-badge">● connecting…</div>
</header>
 
<!-- Stat cards -->
<div class="cards">
<div class="card">
<div class="card-label">Latest Voltage</div>
<div class="card-value" id="c-voltage">—<span class="card-unit">V</span></div>
</div>
<div class="card">
<div class="card-label">Latest Current</div>
<div class="card-value" id="c-current">—<span class="card-unit">mA</span></div>
</div>
<div class="card">
<div class="card-label">Latest Power</div>
<div class="card-value" id="c-power">—<span class="card-unit">mW</span></div>
</div>
<div class="card">
<div class="card-label">Today's Sun Time</div>
<div class="card-value" id="c-suntime">—</div>
</div>
<div class="card">
<div class="card-label">Total Readings</div>
<div class="card-value" id="c-count">—</div>
</div>
</div>
 
<!-- Charts -->
<div class="chart-grid">
<div class="chart-card">
<div class="chart-title">Voltage over time — <span>last 7 days</span></div>
<div id="chart-voltage" style="height:340px;"></div>
</div>
<div class="chart-card">
<div class="chart-title">Daily sun hours — <span>bar comparison</span></div>
<div id="chart-sunhours" style="height:280px;"></div>
</div>
</div>
 
<div id="last-updated">Awaiting first poll…</div>
</div><!-- /wrap -->
 
<script>
const POLL_MS = 30_000;
const THRESHOLD = 1.0;
 
const PLOTLY_LAYOUT_BASE = {
paper_bgcolor: 'rgba(0,0,0,0)',
plot_bgcolor: 'rgba(0,0,0,0)',
font: { family: "'Space Mono', monospace", color: '#6b7585', size: 11 },
margin: { t: 10, r: 20, b: 50, l: 60 },
xaxis: { gridcolor: '#1f2936', linecolor: '#1f2936', tickfont: { size: 10 } },
yaxis: { gridcolor: '#1f2936', linecolor: '#1f2936', tickfont: { size: 10 } },
hoverlabel: {
bgcolor: '#131820',
bordercolor: '#f5a623',
font: { color: '#e8e4d9', size: 12 }
},
legend: { bgcolor: 'rgba(0,0,0,0)', font: { color: '#6b7585' } },
};
const PLOTLY_CONFIG = { displayModeBar: false, responsive: true };
 
function fmtSun(hours) {
const h = Math.floor(hours);
const m = Math.floor((hours - h) * 60);
return h > 0 ? `${h}h ${m}m` : `${m}m`;
}
 
function updateCards(readings, dailySun) {
if (!readings.length) return;
const last = readings[readings.length - 1];
setText('c-voltage', last.voltage_v.toFixed(3) + '<span class="card-unit">V</span>');
setText('c-current', last.current_ma.toFixed(2) + '<span class="card-unit">mA</span>');
setText('c-power', last.power_mw.toFixed(2) + '<span class="card-unit">mW</span>');
setText('c-count', readings.length);
 
const today = last.timestamp.slice(0, 10);
const todaySun = dailySun[today] || 0;
setText('c-suntime', fmtSun(todaySun));
}
 
function setText(id, html) {
document.getElementById(id).innerHTML = html;
}
 
function renderVoltageChart(readings) {
if (!readings.length) {
document.getElementById('chart-voltage').innerHTML = '<div class="empty">No readings yet.</div>';
return;
}
 
// Group by date for coloured traces
const byDay = {};
readings.forEach(r => {
const day = r.timestamp.slice(0, 10);
if (!byDay[day]) byDay[day] = { x: [], y: [], text: [], sunlight: [] };
byDay[day].x.push(r.timestamp);
byDay[day].y.push(r.voltage_v);
byDay[day].sunlight.push(r.voltage_v >= THRESHOLD);
byDay[day].text.push(
`<b>${r.timestamp}</b><br>` +
`Voltage: ${r.voltage_v.toFixed(4)} V<br>` +
`Current: ${r.current_ma.toFixed(4)} mA<br>` +
`Power: ${r.power_mw.toFixed(4)} mW<br>` +
`Sunlight: ${r.voltage_v >= THRESHOLD ? '☀ Yes' : '🌑 No'}`
);
});
 
const palette = ['#f5a623','#e8673c','#ffd166','#06d6a0','#118ab2','#ef476f','#7b2d8b'];
const traces = Object.entries(byDay).map(([day, d], i) => ({
type: 'scatter',
mode: 'lines+markers',
name: day,
x: d.x, y: d.y,
text: d.text,
hovertemplate: '%{text}<extra></extra>',
line: { color: palette[i % palette.length], width: 2 },
marker: {
color: d.sunlight.map(s => s ? palette[i % palette.length] : '#1f2936'),
size: 5, line: { color: palette[i % palette.length], width: 1 }
},
}));
 
// Sunlight threshold line
traces.push({
type: 'scatter', mode: 'lines', name: '1V threshold',
x: [readings[0].timestamp, readings[readings.length-1].timestamp],
y: [THRESHOLD, THRESHOLD],
line: { color: 'rgba(255,255,255,0.15)', dash: 'dash', width: 1 },
hoverinfo: 'skip',
});
 
Plotly.react('chart-voltage', traces, {
...PLOTLY_LAYOUT_BASE,
yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, title: 'Voltage (V)', rangemode: 'tozero' },
xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, title: 'Timestamp', type: 'date' },
}, PLOTLY_CONFIG);
}
 
function renderSunChart(dailySun) {
const days = Object.keys(dailySun).sort();
const hours = days.map(d => dailySun[d]);
 
if (!days.length) {
document.getElementById('chart-sunhours').innerHTML = '<div class="empty">No daily data yet.</div>';
return;
}
 
const trace = {
type: 'bar',
x: days, y: hours,
text: hours.map(h => fmtSun(h)),
textposition: 'outside',
hovertemplate: '<b>%{x}</b><br>Sun hours: %{y:.2f} h<extra></extra>',
marker: {
color: hours.map(h => h >= 6 ? '#f5a623' : h >= 3 ? '#e8673c' : '#6b7585'),
line: { color: 'rgba(0,0,0,0)', width: 0 },
},
};
 
Plotly.react('chart-sunhours', [trace], {
...PLOTLY_LAYOUT_BASE,
margin: { t: 30, r: 20, b: 50, l: 60 },
yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, title: 'Hours', rangemode: 'tozero' },
xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, title: 'Date' },
}, PLOTLY_CONFIG);
}
 
async function fetchAndRender() {
try {
const res = await fetch('/data');
if (!res.ok) throw new Error(`HTTP ${res.status}`);
const data = await res.json();
 
updateCards(data.readings, data.daily_sun_hours);
renderVoltageChart(data.readings);
renderSunChart(data.daily_sun_hours);
 
const badge = document.getElementById('status-badge');
badge.textContent = '● live';
badge.classList.add('live');
document.getElementById('last-updated').textContent =
'Last updated: ' + data.generated_at;
} catch (err) {
console.error('Poll error:', err);
const badge = document.getElementById('status-badge');
badge.textContent = '● offline';
badge.classList.remove('live');
}
}
 
// Initial fetch + periodic polling
fetchAndRender();
setInterval(fetchAndRender, POLL_MS);
</script>
</body>
</html>
"""
 
if __name__ == "__main__":
    # Run on all interfaces so you can reach it from another device on the LAN
    app.run(host="0.0.0.0", port=5000, debug=False)

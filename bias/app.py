#!/usr/bin/env python3
"""Bias Board: interactive browser app over data/live/outlook.json -> site/index.html

Run bias/pull.py and bias/build.py first. The data ships inside the page (no server).
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(f"{ROOT}/data/live/outlook.json"))
for m in D["markets"].values():               # trim what the app never reads
    m["cot"].pop("lead", None)
DATA = json.dumps(D, separators=(",", ":"))

PAGE = r"""<title>Bias Board</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* layout: sticky top bar, a board of market tiles grouped by sector, one focus panel that swaps per market */
:root{
  --bg:#edf1f6; --card:#ffffff; --ink:#16213a; --mute:#5d6985; --line:#d6dde8;
  --bull:#0d8466; --bull-soft:#d3f0e6; --bear:#d9472f; --bear-soft:#fbe0da; --flat:#8b95ab; --flat-soft:#e5e9f0;
  --sun:#c98a00; --sun-soft:#fdf0c4; --retail:#b23fc4; --comm:#2a63d4; --funds:#e07f0c;
  --display:"Bricolage Grotesque",ui-sans-serif,system-ui,sans-serif; --body:"Instrument Sans",system-ui,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,monospace; --shadow:0 1px 2px rgba(22,33,58,.06),0 6px 18px rgba(22,33,58,.07);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0e1424; --card:#161f33; --ink:#e8ecf5; --mute:#93a0bd; --line:#263252;
  --bull:#3fd0a4; --bull-soft:#12372f; --bear:#ff7d68; --bear-soft:#3d1f1d; --flat:#7d88a3; --flat-soft:#222c43;
  --sun:#ffc933; --sun-soft:#3a3115; --retail:#e07ae8; --comm:#6ea0ff; --funds:#ffaa4d; --shadow:0 1px 2px rgba(0,0,0,.3),0 8px 22px rgba(0,0,0,.25); color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0e1424; --card:#161f33; --ink:#e8ecf5; --mute:#93a0bd; --line:#263252;
  --bull:#3fd0a4; --bull-soft:#12372f; --bear:#ff7d68; --bear-soft:#3d1f1d; --flat:#7d88a3; --flat-soft:#222c43;
  --sun:#ffc933; --sun-soft:#3a3115; --retail:#e07ae8; --comm:#6ea0ff; --funds:#ffaa4d; --shadow:0 1px 2px rgba(0,0,0,.3),0 8px 22px rgba(0,0,0,.25); color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:15px/1.5 var(--body);margin:0}
.wrap{max-width:1220px;margin-inline:auto;padding-inline:18px;padding-block:0 60px}
.top{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.top .wrap{display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px;padding-block:12px}
.brand{font:800 24px/1 var(--display);letter-spacing:-.02em;display:flex;align-items:center;gap:9px}
.brand svg{width:26px;height:26px}
.meta{color:var(--mute);font-size:13px}
.filters{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap}
.chip{font:500 13px/1 var(--body);border:1px solid var(--line);background:var(--card);color:var(--ink);padding:7px 11px;border-radius:999px;cursor:pointer;transition:transform .15s,background .15s}
.chip:hover{transform:translateY(-1px)} .chip[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.chip:focus-visible,.tile:focus-visible,summary:focus-visible{outline:3px solid var(--sun);outline-offset:2px}
h2.sec{font:700 12px/1 var(--body);letter-spacing:.12em;text-transform:uppercase;color:var(--mute);margin:22px 0 10px}
.board{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}
.tile{position:relative;text-align:left;background:var(--card);border:1.5px solid var(--line);border-radius:14px;padding:11px 12px 10px;cursor:pointer;color:var(--ink);font:inherit;
  box-shadow:var(--shadow);transition:transform .18s cubic-bezier(.3,1.6,.5,1),border-color .15s,opacity .2s;display:flex;flex-direction:column;gap:6px;min-width:0}
.tile:hover{transform:translateY(-3px) rotate(-.4deg)}
.tile[aria-current="true"]{border-color:var(--ink);transform:translateY(-3px);box-shadow:0 0 0 3px color-mix(in srgb,var(--ink) 12%,transparent),var(--shadow)}
.tile.dim{opacity:.28}
.tile .nm{font:700 15px/1.15 var(--display);padding-right:38px} .tile .tk{font:12px var(--mono);color:var(--mute)}
.tile .row{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.tile .basis{font-size:11.5px;color:var(--mute);display:flex;align-items:center;gap:4px}
.tile .basis svg{width:13px;height:13px;flex:none}
.tile .ring{position:absolute;top:9px;right:9px;width:34px;height:34px}
.tile .spark{height:22px;width:100%}
.pill{display:inline-flex;align-items:center;gap:5px;font:600 12px/1 var(--body);padding:5px 8px;border-radius:999px;white-space:nowrap}
.pill.BULLISH{background:var(--bull-soft);color:var(--bull)} .pill.BEARISH{background:var(--bear-soft);color:var(--bear)}
.pill.flat{background:var(--flat-soft);color:var(--flat)}
.panel{margin-top:26px;background:var(--card);border:1.5px solid var(--line);border-radius:20px;box-shadow:var(--shadow);padding:22px clamp(16px,3vw,30px) 26px;animation:pop .45s cubic-bezier(.2,1.4,.4,1)}
@keyframes pop{from{transform:translateY(10px) scale(.985);opacity:0}to{transform:none;opacity:1}}
.hero{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px 24px;align-items:center}
.hero h1{font:800 clamp(30px,5vw,48px)/1 var(--display);letter-spacing:-.03em;margin:0}
.hero .sub{color:var(--mute);margin-top:6px;font-size:14px}
.why{font-size:17px;max-width:62ch;margin:14px 0 0;text-wrap:pretty}
.dial{width:190px} .dial text{font:600 11px var(--body);fill:var(--mute)}
.needle{transition:transform 1s cubic-bezier(.3,1.5,.5,1);transform-origin:95px 92px}
.banner{display:flex;gap:10px;align-items:flex-start;margin-top:16px;padding:11px 14px;border-radius:12px;background:var(--sun-soft);color:var(--ink);font-size:14px}
.banner.hot{background:var(--bear-soft)} .banner.calm{background:var(--flat-soft)}
.banner b{font-weight:600} .banner .clock{flex:none;width:22px;height:22px}
.engines{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
.eng{border:1px solid var(--line);border-radius:12px;padding:9px 12px;display:flex;align-items:center;gap:10px;font-size:13px;color:var(--mute)}
.eng b{color:var(--ink);font-weight:600}
.eng.lead{border-color:var(--ink);box-shadow:inset 0 0 0 1px var(--ink)}
.eng .k{font:700 10.5px/1 var(--body);letter-spacing:.1em;text-transform:uppercase}
.charts{display:flex;flex-direction:column;gap:22px;margin-top:22px}
.card{border:1px solid var(--line);border-radius:16px;padding:14px 16px 10px;min-width:0}
.card h3{font:700 19px/1.2 var(--display);margin:0;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.card h3 .tag{font:600 10.5px/1 var(--body);letter-spacing:.1em;text-transform:uppercase;padding:4px 7px;border-radius:999px;background:var(--ink);color:var(--bg)}
.card .note{color:var(--mute);font-size:13px;margin:4px 0 6px}
.ctl{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 2px}
.ctl .chip{font-size:12px;padding:5px 9px}
.chart{position:relative} .chart svg{width:100%;height:auto;display:block;overflow:visible}
.ax text{font:10.5px var(--mono);fill:var(--mute)} .ax line{stroke:var(--line)}
.draw{stroke-dasharray:var(--len);stroke-dashoffset:var(--len);animation:draw 1.3s ease-out forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.pulse{animation:pulse 1.6s ease-in-out infinite;transform-box:fill-box;transform-origin:center}
@keyframes pulse{50%{transform:scale(1.6);opacity:.35}}
.tip{position:absolute;pointer-events:none;background:var(--ink);color:var(--bg);font:12px/1.35 var(--mono);padding:6px 8px;border-radius:8px;white-space:nowrap;transform:translate(-50%,-110%);opacity:0;transition:opacity .12s}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--mute);margin-top:4px}
.legend i{display:inline-block;width:16px;height:4px;border-radius:2px;vertical-align:middle;margin-right:5px}
details{border:1px solid var(--line);border-radius:14px;padding:4px 14px;margin-top:12px}
details[open]{padding-bottom:12px}
summary{cursor:pointer;font:700 15px/1 var(--display);padding:10px 0;list-style:none;display:flex;justify-content:space-between;align-items:center;gap:10px}
summary::-webkit-details-marker{display:none} summary::after{content:"+";font:600 18px var(--mono);color:var(--mute);transition:transform .2s}
details[open] summary::after{transform:rotate(45deg)}
summary small{font:400 12.5px var(--body);color:var(--mute);margin-left:auto}
.tbl{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
thead th{font:600 11px var(--body);letter-spacing:.06em;text-transform:uppercase;color:var(--mute)}
td.n{font-family:var(--mono);font-variant-numeric:tabular-nums}
tr.ok td,tr.ok th{background:var(--sun-soft)}
.hm td.n{text-align:right;border-radius:6px} .hm td.hi{background:var(--bull-soft);color:var(--bull);font-weight:600} .hm td.lo{background:var(--bear-soft);color:var(--bear);font-weight:600}
.st{font:600 10.5px/1 var(--body);padding:3px 6px;border-radius:999px;background:var(--flat-soft);color:var(--mute)}
.st.live{background:var(--sun-soft);color:var(--sun)}
.nbrs{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;margin-top:6px}
.nbrs div{display:flex;flex-direction:column;align-items:center;gap:4px;font:11px var(--mono);color:var(--mute)}
.nbrs .bar{width:34px;border-radius:6px 6px 2px 2px;background:var(--flat-soft);position:relative;transition:height .6s cubic-bezier(.3,1.5,.5,1)}
.nbrs .bar.c{background:var(--ink)}
.tested{display:flex;align-items:center;gap:12px;margin-top:12px;padding:9px 12px;border:1px dashed var(--line);border-radius:12px;font-size:13px;color:var(--mute);max-width:62ch}
.tested > b{font:800 24px/1 var(--display);color:var(--ink)} .tested b.tl{font-weight:600;color:var(--ink)}
.card h3 .tag.ctx{background:var(--flat-soft);color:var(--mute)}
.yrs{display:flex;flex-wrap:wrap;gap:6px}
.yr{display:flex;flex-direction:column;align-items:center;gap:3px;font:11px var(--mono);color:var(--mute);padding:5px 4px 3px;border-radius:10px;border:2px solid transparent;min-width:38px}
.yr.agree{border-color:var(--ink)} .yr.against{border-color:var(--bear);border-style:dashed} .yr.none{border-color:var(--line)}
.yr .dot{width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font:700 12px var(--body);color:var(--card)}
.yr .dot.w{background:var(--bull)} .yr .dot.l{background:var(--bear)}
.legend .lg{width:14px;height:10px;border-radius:3px;border:2px solid var(--ink);background:transparent}
.legend .lg.against{border-color:var(--bear);border-style:dashed} .legend .lg.none{border-color:var(--line)}
.foot{color:var(--mute);font-size:12px;margin-top:28px;max-width:80ch}
.kbd{font:11px var(--mono);border:1px solid var(--line);border-bottom-width:2px;border-radius:5px;padding:1px 5px}
@media (max-width:640px){.hero{grid-template-columns:1fr}.dial{width:160px}.board{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}.draw{stroke-dashoffset:0}}
</style>

<div class="top"><div class="wrap">
  <div class="brand"><svg viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="11" fill="none" stroke="var(--ink)" stroke-width="2.5"/><path d="M13 13 L20 7" stroke="var(--bear)" stroke-width="3" stroke-linecap="round"/><circle cx="13" cy="13" r="2.6" fill="var(--ink)"/></svg>Bias Board</div>
  <div class="meta" id="meta"></div>
  <div class="filters" role="group" aria-label="Filter markets">
    <button class="chip" id="f-all" aria-pressed="true">All</button>
    <button class="chip" id="f-BULLISH" aria-pressed="false">Bullish</button>
    <button class="chip" id="f-BEARISH" aria-pressed="false">Bearish</button>
    <button class="chip" id="f-STAND ASIDE" aria-pressed="false">Stand aside</button>
    <button class="chip" id="f-hot" aria-pressed="false">Window ending</button>
    <a class="chip" href="outlook.html" style="text-decoration:none">Full report</a>
  </div>
</div></div>

<div class="wrap">
  <div id="boards"></div>
  <section class="panel" id="panel" aria-live="polite"></section>
  <p class="foot">COT: CFTC legacy report via LSE (CFTC history for WTI and natural gas). Prices: LSE daily spot, yen, franc and Canadian dollar in futures direction, dollar index rebuilt from its legs. Seasonal windows: true-seasonality scoring (each year's trend removed), 15 prior years, at least five days long. Move between markets with <span class="kbd">←</span> <span class="kbd">→</span>. A bias is not a trade. Educational, not advice.</p>
</div>

<script>
const D = __DATA__;
const M = D.markets, KEYS = Object.keys(M);
const TODAY = new Date(D.today + "T00:00:00");
const LBS = ["6 mo","1 yr","2 yr","3 yr","Multi-yr"];
const GN = {retail:"Retail", comm:"Commercials", fund:"Funds"};
const GC = {retail:"var(--retail)", comm:"var(--comm)", fund:"var(--funds)"};
const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmtD = s => new Date(s + "T00:00:00").toLocaleDateString("en-GB", {day:"2-digit", month:"short"});
const title = s => s.charAt(0) + s.slice(1).toLowerCase();
const seasonLed = m => ["Calendar only", "COT + calendar", "Calendar over COT"].includes(m.basis);
const cotLed = m => m.basis.startsWith("COT");
const arrow = v => v === "BULLISH" ? "▲" : v === "BEARISH" ? "▼" : "◆";
const pill = (v, txt) => `<span class="pill ${v === "BULLISH" || v === "BEARISH" ? v : "flat"}">${arrow(v)} ${esc(txt || title(v))}</span>`;
const sideV = s => s === "BUY" ? "BULLISH" : "BEARISH";

const ICON = {
  cal: `<svg viewBox="0 0 14 14" aria-hidden="true"><rect x="1.5" y="2.5" width="11" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M1.5 6h11M4.5 1v3M9.5 1v3" stroke="currentColor" stroke-width="1.4"/></svg>`,
  cot: `<svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2 12V7M5.5 12V3M9 12V8M12.5 12V5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`,
  both:`<svg viewBox="0 0 14 14" aria-hidden="true"><circle cx="5" cy="7" r="3.6" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="9" cy="7" r="3.6" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>`,
  none:`<svg viewBox="0 0 14 14" aria-hidden="true"><path d="M3 7h8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`,
};
const basisIcon = m => m.basis === "COT + calendar" ? ICON.both : (m.basis === "Calendar only" || m.basis === "Calendar over COT") ? ICON.cal : cotLed(m) ? ICON.cot : m.basis.startsWith("Conflict") ? ICON.both : ICON.none;
const T = D.tested;
const sgn = v => (v >= 0 ? "+" : "") + v;
const warnLevel = t => !t ? null : (t.closing && t.flip) ? "hot" : (t.closing || t.flip) ? "warn" : "calm";

/* ---------- tiles ---------- */
function ring(m) {
  const t = m.timing; if (!t) return "";
  const d = m.seas.driver, frac = Math.max(0, Math.min(1, t.left / d.len));
  const lvl = warnLevel(t), col = lvl === "hot" ? "var(--bear)" : lvl === "warn" ? "var(--sun)" : "var(--flat)";
  const C = 2 * Math.PI * 13;
  return `<svg class="ring" viewBox="0 0 34 34" role="img" aria-label="${t.left} days left in window">
    <circle cx="17" cy="17" r="13" fill="none" stroke="var(--line)" stroke-width="4"/>
    <circle cx="17" cy="17" r="13" fill="none" stroke="${col}" stroke-width="4" stroke-linecap="round" stroke-dasharray="${C * frac} ${C}" transform="rotate(-90 17 17)"/>
    <text x="17" y="21" text-anchor="middle" style="font:700 11px var(--mono);fill:var(--ink)">${t.left}</text></svg>`;
}
function spark(m) {
  const v = m.seas.cur, W = 150, H = 22, lo = Math.min(...v), hi = Math.max(...v);
  const pts = v.map((y, i) => `${(i / 124 * W).toFixed(1)},${(H - 2 - (y - lo) / (hi - lo || 1) * (H - 4)).toFixed(1)}`).join(" ");
  const col = m.verdict === "BULLISH" ? "var(--bull)" : m.verdict === "BEARISH" ? "var(--bear)" : "var(--flat)";
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="${col}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
}
function boards() {
  const secs = {};
  KEYS.forEach(k => (secs[M[k].sector] ||= []).push(k));
  $("#boards").innerHTML = Object.entries(secs).map(([s, ks]) => `<h2 class="sec">${s}</h2><div class="board">` + ks.map(k => {
    const m = M[k];
    return `<button class="tile" id="t-${k}" data-k="${k}" aria-current="false">${ring(m)}
      <div><div class="nm">${esc(m.name)}</div><div class="tk">${k}</div></div>
      <div class="row">${pill(m.verdict)}</div>
      <div class="basis">${basisIcon(m)}${esc(m.basis)}</div>${spark(m)}</button>`;
  }).join("") + `</div>`).join("");
  document.querySelectorAll(".tile").forEach(b => b.addEventListener("click", () => select(b.dataset.k, true)));
}

/* ---------- hero ---------- */
function dial(m) {
  const pos = {BULLISH: 1, BEARISH: -1}[m.verdict] || 0;
  const mag = m.basis === "COT + calendar" ? 1 : m.basis === "Calendar only" ? .55 : m.basis === "Calendar over COT" ? .45 : m.groups === 2 ? .9 : .62;
  const ang = pos * 70 * mag;
  return `<svg class="dial" viewBox="0 0 190 112" role="img" aria-label="Bias ${m.verdict}">
    <path d="M18 92 A77 77 0 0 1 95 15" fill="none" stroke="var(--bear-soft)" stroke-width="16"/>
    <path d="M95 15 A77 77 0 0 1 172 92" fill="none" stroke="var(--bull-soft)" stroke-width="16"/>
    <path d="M18 92 A77 77 0 0 1 172 92" fill="none" stroke="var(--line)" stroke-width="1.5" stroke-dasharray="2 5"/>
    <text x="14" y="108">Bearish</text><text x="176" y="108" text-anchor="end">Bullish</text>
    <g class="needle" id="needle" style="transform:rotate(0deg)" data-a="${ang}">
      <path d="M95 92 L95 26" stroke="var(--ink)" stroke-width="4" stroke-linecap="round"/></g>
    <circle cx="95" cy="92" r="8" fill="var(--ink)"/><circle cx="95" cy="92" r="3" fill="var(--card)"/></svg>`;
}
function seasStance(m) {
  const s = m.seas;
  if (s.read !== "BULLISH" && s.read !== "BEARISH") return s.read === "SELF-CANCELLING" ? "the calendar cancels itself out" : "there is no seasonal window in play";
  if (m.verdict === "STAND ASIDE") return `the calendar leans ${s.read.toLowerCase()}`;
  return s.read === m.verdict ? "the calendar points the same way" : "the calendar points the other way";
}
function why(m) {
  const c = m.cot, s = m.seas, d = s.driver;
  const win = d ? `${title(d.side)} window ${fmtD(d.start)}–${fmtD(d.end)}, ${d.wins} of 15 years` : "";
  const g = m.groups === 2 ? "retail and commercials both" : c.info.comm.lit >= 2 ? "commercials" : "retail";
  switch (m.basis) {
    case "COT + calendar": return `Both engines point ${m.verdict.toLowerCase()}: ${g} at extremes, and the calendar agrees (${win}).`;
    case "COT only": return `COT carries the bias alone: ${g} at extremes. ${s.read === "SELF-CANCELLING" ? "The calendar cancels itself out." : "No seasonal window is in play."}`;
    case "Calendar only": return `The calendar carries the bias alone: ${win}. Positioning has no side.`;
  }
  const ag = (s.past && s.past.summary.against) || {n: 0, w: 0};
  if (m.basis === "Calendar over COT") return `COT reads ${title(c.read)} (${g}), against the calendar: ${win}. In the past years when COT was against this window it still paid ${ag.w} of ${ag.n} times, so the calendar stands.`;
  if (m.basis.startsWith("Conflict")) return `No bias. COT reads ${title(c.read)} (${g}) while the calendar says ${title(s.read)} (${win}). ${ag.n >= 3 ? `In past years with COT against it, this window paid only ${ag.w} of ${ag.n} times` : `This window has too few past years with COT against it (${ag.n}) to judge`}, so COT is relevant here and we wait.`;
  if (m.basis.includes("disagree")) return `No bias. Retail and commercials point opposite ways, and ${s.read === "SELF-CANCELLING" ? "the calendar cancels itself out" : "there is no seasonal window"}.`;
  return `No bias. Positioning has no extreme on two or more lookbacks of either group, and ${s.read === "SELF-CANCELLING" ? "the calendar cancels itself out" : "there is no seasonal window in play"}.`;
}
function testedHero(m) {
  const t = m.tested;
  if (!t) return "";
  return `<div class="tested"><b>${t.win}%</b><span><b class="tl">How verdicts like this one did after the fact</b> (walk-forward, every past week, only data known then): ${t.label.replace("{win}", t.win)} · ${t.n} trades · average ${sgn(t.avg)}% in the trade direction · t ${t.t.toFixed(1)}. This is a different number from the window's own 15-year average below, which comes from the years it was picked from.</span></div>`;
}
function banner(m) {
  const t = m.timing; if (!t) return "";
  const lvl = warnLevel(t);
  let txt = `<b>Seasonal context: window ends ${fmtD(t.end)}, ${t.left} days left.</b>`;
  if (t.flip) txt += ` Then a ${t.flip.side.toLowerCase()} window opens ${fmtD(t.flip.start)} (${t.flip.wins} of 15 years).`;
  if (lvl === "hot") txt += ` The window is about to close and the calendar then turns the other way.`;
  return `<div class="banner ${lvl}"><svg class="clock" viewBox="0 0 22 22" aria-hidden="true"><circle cx="11" cy="11" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M11 6v5l3.5 2.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><div>${txt}</div></div>`;
}

/* ---------- charts ---------- */
function lineLen(pts) { let L = 0; for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); return Math.ceil(L) + 2; }
function poly(pts, stroke, w, extra = "") {
  return `<polyline points="${pts.map(p => p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ")}" fill="none" stroke="${stroke}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round" class="draw" style="--len:${lineLen(pts)}" ${extra}/>`;
}
function seasonChart(m) {
  const s = m.seas, W = 760, H = 270, L = 46, R = 14, T = 14, B = 26, n = s.avg["15"].length;
  const all = [...s.avg["5"], ...s.avg["10"], ...s.avg["15"], ...s.cur], lo = Math.min(...all, 0), hi = Math.max(...all, 0);
  const X = i => L + (W - L - R) * i / (n - 1), Y = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo || 1));
  const doy = d => { const t = new Date(d + "T00:00:00"); return (t - new Date(t.getFullYear(), 0, 1)) / 864e5; };
  const XD = d => { const t = new Date(d + "T00:00:00"); const yy = t.getFullYear() > TODAY.getFullYear() ? 365 : 0; return X(Math.min(n - 1, (doy(d) + yy) / 365 * (n - 1))); };
  let bands = "";
  s.windows.forEach((w, i) => {
    const x0 = XD(w.start), x1 = XD(w.end), main = i === 0, col = w.side === "BUY" ? "var(--bull)" : "var(--bear)";
    const flip = m.timing && m.timing.flip && m.timing.flip.start === w.start;
    if (!main && !flip) return;
    bands += `<rect x="${x0}" y="${T}" width="${Math.max(2, x1 - x0)}" height="${H - T - B}" fill="${col}" opacity="${main ? .13 : .07}" ${flip ? 'stroke="' + col + '" stroke-dasharray="4 4" stroke-opacity=".6"' : ""} rx="4"/>
      <text x="${x0 + 5}" y="${T + (main ? 13 : 29)}" style="font:600 11px var(--body);fill:${col}">${main ? "◀ driver · " : "next · "}${w.side.toLowerCase()} ${w.wins}/15</text>`;
  });
  const tx = X((s.cur.length - 1));
  const months = "JFMAMJJASOND".split("").map((c, i) => `<text x="${X((i + .5) / 12 * (n - 1))}" y="${H - 8}" text-anchor="middle">${c}</text>`).join("");
  const ticks = [lo, 0, hi].map(v => `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" ${v === 0 ? "" : 'stroke-dasharray="2 4"'}/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end">${v > 0 ? "+" : ""}${v.toFixed(0)}%</text>`).join("");
  const P = a => a.map((v, i) => [X(i), Y(v)]);
  const cur = P(s.cur);
  return `<div class="chart" data-kind="season"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Seasonal map">${bands}<g class="ax">${ticks}${months}</g>
    ${poly(P(s.avg["5"]), "var(--line)", 1.6)}${poly(P(s.avg["10"]), "var(--flat)", 1.6)}${poly(P(s.avg["15"]), "var(--mute)", 2.2)}
    ${poly(cur, "var(--ink)", 3)}
    <line x1="${tx}" x2="${tx}" y1="${T}" y2="${H - B}" stroke="var(--sun)" stroke-width="2" stroke-dasharray="3 3"/>
    <circle cx="${cur[cur.length - 1][0]}" cy="${cur[cur.length - 1][1]}" r="5" fill="var(--sun)" class="pulse"/>
    <circle cx="${cur[cur.length - 1][0]}" cy="${cur[cur.length - 1][1]}" r="4" fill="var(--sun)" stroke="var(--card)" stroke-width="2"/>
    <rect class="hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent"/></svg><div class="tip"></div></div>
    <div class="legend"><span><i style="background:var(--ink)"></i>${TODAY.getFullYear()}</span><span><i style="background:var(--mute)"></i>15-yr avg</span><span><i style="background:var(--flat)"></i>10-yr</span><span><i style="background:var(--line)"></i>5-yr</span><span><i style="background:var(--sun)"></i>today</span></div>`;
}
function cotChart(m, grp, lb) {
  const c = m.cot, sr = c.series, W = 760, H = 270, L = 62, R = 14, T = 14, B = 26, n = sr.dates.length;
  const gs = ["comm", "retail", "fund"];
  const vals = gs.flatMap(g => sr[g]), lo = Math.min(...vals, 0), hi = Math.max(...vals, 0);
  const X = i => L + (W - L - R) * i / (n - 1), Y = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo || 1));
  const band = c.bands[grp][lb], wk = {"6 mo": 26, "1 yr": 52, "2 yr": 104, "3 yr": 156, "Multi-yr": 260}[lb];
  const bx = X(Math.max(0, n - wk));
  const k = v => Math.abs(v) >= 1e3 ? (v / 1e3).toFixed(0) + "k" : v.toFixed(0);
  let marks = "";
  const row = (c.groups[grp] || []).find(r => r.lb === lb);
  if (row && row.cases) row.cases.forEach(([d, win]) => {
    const i = sr.dates.findIndex(x => x >= d); if (i < 0) return;
    marks += `<circle cx="${X(i)}" cy="${Y(sr[grp][i])}" r="5.5" fill="${win ? "var(--bull)" : "var(--bear)"}" stroke="var(--card)" stroke-width="2"><title>${d}: ${win ? "paid" : "did not pay"} after 4 weeks</title></circle>`;
  });
  const years = []; sr.dates.forEach((d, i) => { if (i && d.slice(0, 4) !== sr.dates[i - 1].slice(0, 4)) years.push(`<line x1="${X(i)}" x2="${X(i)}" y1="${T}" y2="${H - B}" stroke-dasharray="2 4"/><text x="${X(i) + 4}" y="${H - 8}">${d.slice(0, 4)}</text>`); });
  const lines = gs.map(g => poly(sr[g].map((v, i) => [X(i), Y(v)]), GC[g], g === grp ? 3 : 1.4, g === grp ? "" : 'opacity=".45"')).join("");
  const last = [X(n - 1), Y(sr[grp][n - 1])];
  return `<div class="chart" data-kind="cot" data-g="${grp}"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Net positions">
    <rect x="${bx}" y="${Y(band[1])}" width="${X(n - 1) - bx}" height="${Math.max(1, Y(band[0]) - Y(band[1]))}" fill="${GC[grp]}" opacity=".08"/>
    <line x1="${bx}" x2="${X(n - 1)}" y1="${Y(band[1])}" y2="${Y(band[1])}" stroke="${GC[grp]}" stroke-dasharray="5 4" stroke-width="1.4"/>
    <line x1="${bx}" x2="${X(n - 1)}" y1="${Y(band[0])}" y2="${Y(band[0])}" stroke="${GC[grp]}" stroke-dasharray="5 4" stroke-width="1.4"/>
    <text x="${bx + 4}" y="${Y(band[1]) - 5}" style="font:600 10.5px var(--body);fill:${GC[grp]}">80th pct · ${lb}</text>
    <text x="${bx + 4}" y="${Y(band[0]) + 14}" style="font:600 10.5px var(--body);fill:${GC[grp]}">20th pct</text>
    <g class="ax">${years}<line x1="${L}" x2="${W - R}" y1="${Y(0)}" y2="${Y(0)}"/><text x="${L - 6}" y="${Y(hi) + 4}" text-anchor="end">${k(hi)}</text><text x="${L - 6}" y="${Y(0) + 4}" text-anchor="end">0</text><text x="${L - 6}" y="${Y(lo) + 4}" text-anchor="end">${k(lo)}</text></g>
    ${lines}${marks}
    <circle cx="${last[0]}" cy="${last[1]}" r="6" fill="${GC[grp]}" class="pulse"/><circle cx="${last[0]}" cy="${last[1]}" r="5" fill="${GC[grp]}" stroke="var(--card)" stroke-width="2"/>
    <rect class="hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent"/></svg><div class="tip"></div></div>
    <div class="legend">${gs.map(g => `<span><i style="background:${GC[g]}"></i>${GN[g]} ${c.net[g] >= 0 ? "+" : ""}${c.net[g].toLocaleString("en-US")}</span>`).join("")}<span><i style="background:var(--bull);width:9px;height:9px;border-radius:50%"></i>past case paid</span><span><i style="background:var(--bear);width:9px;height:9px;border-radius:50%"></i>did not</span></div>`;
}
function hookTips(root, m) {
  root.querySelectorAll(".chart").forEach(ch => {
    const svg = ch.querySelector("svg"), tip = ch.querySelector(".tip"), hit = ch.querySelector(".hit");
    hit.addEventListener("mousemove", e => {
      const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal, fx = (e.clientX - r.left) / r.width * vb.width;
      const x0 = +hit.getAttribute("x"), w = +hit.getAttribute("width"), f = Math.max(0, Math.min(1, (fx - x0) / w));
      let html;
      if (ch.dataset.kind === "season") {
        const s = m.seas, i = Math.round(f * (s.avg["15"].length - 1)), mo = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ")[Math.min(11, Math.floor(f * 12))];
        html = `${mo} · 15y ${s.avg["15"][i] >= 0 ? "+" : ""}${s.avg["15"][i].toFixed(1)}%` + (i < s.cur.length ? ` · ${TODAY.getFullYear()} ${s.cur[i] >= 0 ? "+" : ""}${s.cur[i].toFixed(1)}%` : "");
      } else {
        const sr = m.cot.series, i = Math.round(f * (sr.dates.length - 1));
        html = `${sr.dates[i]} · ${GN[ch.dataset.g]} ${sr[ch.dataset.g][i].toLocaleString("en-US")}`;
      }
      tip.innerHTML = html; tip.style.left = (e.clientX - r.left) + "px"; tip.style.top = (e.clientY - r.top) + "px"; tip.style.opacity = 1;
    });
    hit.addEventListener("mouseleave", () => tip.style.opacity = 0);
  });
}

/* ---------- evidence ---------- */
function heat(m) {
  return `<div class="tbl"><table class="hm"><thead><tr><th>Percentile</th>${LBS.slice().reverse().map(l => `<th style="text-align:right">${l}</th>`).join("")}</tr></thead><tbody>` +
    ["retail", "comm", "fund"].map(g => `<tr><th style="color:${GC[g]}">${GN[g]}</th>${m.cot.groups[g].slice().reverse().map(r => `<td class="n ${r.side || ""}">${r.pct.toFixed(1)}</td>`).join("")}</tr>`).join("") +
    `</tbody></table></div>`;
}
function track(m, h) {
  const rows = [];
  ["retail", "comm"].forEach(g => m.cot.groups[g].forEach(r => {
    if (!r.dir) return; const x = r.h[h];
    rows.push(`<tr class="${x.ok ? "ok" : ""}"><th>${GN[g]} · ${r.lb}</th><td><span class="st ${x.past ? "" : "live"}">${x.past ? "past" : "live"}</span> ${r.weeks_in}w</td>` +
      (x.n ? `<td class="n">${Math.round(100 * x.w / x.n)}%</td><td class="n">${x.w} of ${x.n}</td><td class="n">${x.avg >= 0 ? "+" : ""}${x.avg.toFixed(2)}%</td>` : `<td colspan="3" style="color:var(--mute)">no comparable cases</td>`) +
      `<td class="n" style="color:var(--mute)">${r.hist} yrs</td></tr>`);
  }));
  return rows.length ? `<div class="tbl"><table><thead><tr><th>${h}-week result</th><th>Weeks in</th><th>Win</th><th>Cases</th><th>Avg</th><th>History</th></tr></thead><tbody>${rows.join("")}</tbody></table></div>` : `<p class="note">No retail or commercial lookback is at an extreme.</p>`;
}
function edge(m) {
  const e = m.cot.edge, H = {4: "4 weeks", 8: "8 weeks", 13: "3 months", 26: "6 months", 52: "1 year"};
  if (m.cot.read === "STAND ASIDE") return "The positioning read is neutral this week, so there is no direction to test.";
  return e ? `Strongest read: the ${e.lb.toLowerCase()} lookback on ${GN[e.group].toLowerCase()}, ${Math.round(100 * e.w / e.n)}% over ${H[e.h]}, ${e.w} of ${e.n} cases, ${e.avg >= 0 ? "+" : ""}${e.avg.toFixed(2)}% average.`
           : `Nothing in ${m.name} clears the bar (six cases, 60%, positive average). Treat the bias as context, not a tested edge.`;
}
function windowsTbl(m) {
  const s = m.seas; if (!s.windows.length) return `<p class="note">No seasonal window opens in the −2 to +8 week horizon.</p>`;
  return `<div class="tbl"><table><thead><tr><th>Trade</th><th>Window</th><th>Length</th><th>Won (trend removed)</th><th>Avg price move, 15 yrs</th><th>Last 4</th></tr></thead><tbody>` +
    s.windows.map((w, i) => `<tr><td>${pill(sideV(w.side), title(w.side))}${i === 0 ? ' <span class="st live">driver</span>' : ""}</td><td>${fmtD(w.start)} – ${fmtD(w.end)}</td><td class="n">${w.len}d</td><td class="n">${w.wins} of 15</td><td class="n">${w.avg >= 0 ? "+" : ""}${w.avg.toFixed(1)}%</td><td class="n">${w.rec}/4</td></tr>`).join("") + `</tbody></table></div><p class="note">Average price move over the 15 past years: negative is good for a sell window. Wins are counted after removing each year's trend, so a window can win 12 of 15 years with an average move close to zero or even against it.</p>`;
}
function nbrs(m) {
  const s = m.seas; if (!s.neigh) return "";
  const items = [...s.neigh.slice(0, 2), {shift: 0, win: Math.round(100 * s.driver.wins / 15), c: 1}, ...s.neigh.slice(2)];
  return `<div class="nbrs">` + items.map(x => `<div><span>${x.win}%</span><span class="bar ${x.c ? "c" : ""}" style="height:${Math.max(6, x.win * .7)}px"></span><span>${x.shift ? (x.shift > 0 ? "+" : "") + x.shift + "d" : "dates"}</span></div>`).join("") +
    `</div><p class="note">Same window shifted. Average of the shifts ${s.neigh_avg}%, timing ${s.timing}.</p>`;
}
function analogs(m) {
  const a = m.seas.analogs;
  return `<div class="tbl"><table><thead><tr><th>Year</th><th>Match</th><th>To date</th><th>Rest of year</th></tr></thead><tbody>` +
    a.map(x => `<tr><th>${x.y}</th><td class="n">${x.match >= 0 ? "+" : ""}${x.match.toFixed(2)}</td><td class="n">${x.todate >= 0 ? "+" : ""}${x.todate.toFixed(1)}%</td><td class="n" style="color:${x.rest >= 0 ? "var(--bull)" : "var(--bear)"}">${x.rest >= 0 ? "+" : ""}${x.rest.toFixed(1)}%</td></tr>`).join("") + `</tbody></table></div>`;
}

/* ---------- panel ---------- */
let state = {k: null, grp: null, lb: null};
function defaultCot(m) {
  const lead = ["comm", "retail"].filter(g => m.cot.info[g].lit).sort((a, b) => m.cot.info[b].lit - m.cot.info[a].lit)[0] || "comm";
  const lit = m.cot.groups[lead].filter(r => r.side).map(r => r.lb);
  return {grp: lead, lb: lit.length ? lit[lit.length - 1] : "Multi-yr"};
}
function cotCard(m, essential) {
  const c = m.cot;
  return `<div class="card" id="cotcard"><h3>Positioning ${essential ? '<span class="tag">drives the bias</span>' : ""} ${pill(c.read === "STAND ASIDE" ? "NEUTRAL" : c.read, c.read === "STAND ASIDE" ? "Neutral" : title(c.read))}</h3>
    <p class="note">Weekly net contracts, last five years. The shaded band is the 20th to 80th percentile of the chosen lookback; outside it a group is at an extreme. Dots are past cases.</p>
    <div class="ctl" role="group" aria-label="Group">${["comm", "retail", "fund"].map(g => `<button class="chip" data-g="${g}" aria-pressed="${g === state.grp}">${GN[g]} · ${c.groups[g].filter(r => r.side).length}/5 lit</button>`).join("")}</div>
    <div class="ctl" role="group" aria-label="Lookback">${LBS.map(l => { const r = c.groups[state.grp].find(x => x.lb === l); return `<button class="chip" data-lb="${l}" aria-pressed="${l === state.lb}">${l} · ${r.pct.toFixed(0)}${r.side ? " ●" : ""}</button>`; }).join("")}</div>
    <div id="cotchart">${cotChart(m, state.grp, state.lb)}</div>${heat(m)}</div>`;
}
function pastYears(m) {
  const P = m.seas.past; if (!P || !P.years.length) return "";
  const side = m.seas.driver.side === "BUY" ? "BULLISH" : "BEARISH";
  const cells = P.years.map(x => `<div class="yr ${x.rel}" title="${x.y}: COT ${title(x.cot)} · window ${x.win ? "paid" : "failed"} ${sgn(x.r)}%">
      <span class="dot ${x.win ? "w" : "l"}">${x.win ? "✓" : "✗"}</span><span>${String(x.y).slice(2)}</span></div>`).join("");
  const S = P.summary, f = (o) => o.n ? `${o.w} of ${o.n}` : "none";
  return `<h4 class="note" style="margin:14px 0 6px;font-weight:600;color:var(--ink)">This window in its past years, and what COT said at its start</h4>
    <div class="yrs">${cells}</div>
    <div class="legend"><span><i class="lg agree"></i>COT agreed: paid ${f(S.agree)}</span><span><i class="lg against"></i>COT against: paid ${f(S.against)}</span><span><i class="lg none"></i>COT no side: paid ${f(S.none)}</span></div>
    <p class="note">These are the same years the window was picked from, so every column looks good. The out-of-sample answer is in "How the board is tested" below.</p>`;
}
function seasonCard(m, ess) {
  const s = m.seas;
  return `<div class="card"><h3>Seasonality ${ess ? '<span class="tag">drives the bias</span>' : '<span class="tag ctx">not part of the verdict</span>'} ${pill(s.read === "BULLISH" || s.read === "BEARISH" ? s.read : "flat", title(s.read))}${s.strength ? ` <span class="st">${title(s.strength)} · ${s.kind}</span>` : ""}</h3>
    <p class="note">Average path of the last 5, 10 and 15 years and ${TODAY.getFullYear()} so far. Shape match ${s.shape >= 0 ? "+" : ""}${s.shape.toFixed(2)}, ${s.shape_read}.</p>${seasonChart(m)}${pastYears(m)}</div>`;
}
function testedSection() {
  if (!T) return "";
  const row = (lab, o) => o ? `<tr><th>${lab}</th><td class="n">${o.n}</td><td class="n">${o.win}%</td><td class="n">${sgn(o.avg)}%</td><td class="n">${o.t == null ? "–" : o.t.toFixed(1)}</td></tr>` : "";
  const hd = `<thead><tr><th></th><th>Trades</th><th>Won</th><th>Avg</th><th>t</th></tr></thead>`;
  const sc = T.seas_by_cot, cs = T.cot_by_seasonal, cc = T.cot;
  return `<details><summary>How the board is tested<small>walk-forward, no hindsight</small></summary>
    <p class="note">Every Saturday since the data allows, the board's own rules were run with only what was known that day: the COT report released by then and the seasonal windows picked from the 15 years before. One trade per market at a time. Seasonal trades run from the window start (or that Saturday) to the window end; COT trades are held 8 weeks.</p>
    <h4 class="note" style="font-weight:600;color:var(--ink)">The seasonal window, split by what COT said (${T.first_seas.slice(0, 4)}–${T.last.slice(0, 4)})</h4>
    <div class="tbl"><table>${hd}<tbody>${row("All seasonal trades", T.seas_all)}${row("COT agreed", sc.agree)}${row("COT against", sc.against)}${row("COT no side", sc.neutral)}${row("COT groups disagreed", sc.mixed)}</tbody></table></div>
    <h4 class="note" style="font-weight:600;color:var(--ink);margin-top:12px">The COT read, split by what the calendar said (${T.first_cot.slice(0, 4)}–${T.last.slice(0, 4)})</h4>
    <div class="tbl"><table>${hd}<tbody>${row("All COT trades", T.cot_all)}${row("Calendar agreed", cs.agree)}${row("Calendar against", cs.against)}${row("No seasonal window", cs.none)}
      ${row("Currencies, one group", cc["FX|1"])}${row("Currencies, both groups", cc["FX|2"])}${row("Commodities, one group", cc["Commodities|1"])}${row("Commodities, both groups", cc["Commodities|2"])}</tbody></table></div>
    <p class="note">How the board uses this: each engine may carry the bias alone. In a contradiction the calendar stands if the window already paid in at least 2 of 3 past years when COT was against it (at least 3 such years); otherwise there is no bias. Tested, that split made no difference: the calendar won 50.5% when the window had played out against COT and 50.0% when it had not. In contradictions the calendar won about half the time and COT only slightly more, so neither earns the right to overrule the other. Both edges are small: the COT read wins about 54% over 8 weeks and is only clearly above zero pooled across all markets; the seasonal windows have not beaten a coin flip out of sample.</p></details>`;
}
function render(k) {
  const m = M[k], P = $("#panel");
  const cEss = cotLed(m) || m.basis.startsWith("Conflict"), sEss = seasonLed(m) || m.basis.startsWith("Conflict");
  const cards = (m.basis === "Calendar only" || m.basis === "Calendar over COT") ? [seasonCard(m, true), cotCard(m, m.basis !== "Calendar only")] : [cotCard(m, cEss), seasonCard(m, sEss)];
  const extra = [];
  P.style.animation = "none"; void P.offsetWidth; P.style.animation = "";
  P.innerHTML = `<div class="hero"><div><h1>${esc(m.name)}</h1><div class="sub">${k} · ${m.sector} · ${pill(m.verdict)} <span style="margin-left:6px">${m.basis}</span></div>
      <p class="why">${why(m)}</p>${testedHero(m)}</div>${dial(m)}</div>${banner(m)}
    <div class="engines"><div class="eng ${cEss ? "lead" : ""}">${ICON.cot.replace("<svg", '<svg width="16" height="16"')}<span class="k">COT</span><b>${c_read(m)}</b>${m.cot.conv}</div>
      <div class="eng ${sEss ? "lead" : ""}">${ICON.cal.replace("<svg", '<svg width="16" height="16"')}<span class="k">Seasonality</span><b>${title(m.seas.read)}</b>${m.seas.strength ? title(m.seas.strength) : "–"}</div></div>
    <div class="charts">${cards.filter(Boolean).join("")}</div>${extra.join("")}
    <details><summary>Track record<small>what the live extremes did before</small></summary><p class="note">${edge(m)}</p>${track(m, 4)}${track(m, 8)}</details>
    ${m.seas.windows.length ? `<details><summary>Windows in play<small>entry −2 to +8 weeks</small></summary>${windowsTbl(m)}<h4 class="note" style="margin-top:12px">Neighbour test</h4>${nbrs(m)}</details>` : ""}
    <details><summary>Years most like this one<small>analog cross-check</small></summary>${analogs(m)}</details>${testedSection()}`;
  requestAnimationFrame(() => requestAnimationFrame(() => { const n = $("#needle"); if (n) n.style.transform = `rotate(${n.dataset.a}deg)`; }));
  hookTips(P, m); hookCot(m);
}
const c_read = m => m.cot.read === "STAND ASIDE" ? "Neutral" : title(m.cot.read);
function hookCot(m) {
  document.querySelectorAll("#panel #cotcard").forEach(card => {
    card.querySelectorAll("[data-g]").forEach(b => b.addEventListener("click", () => { state.grp = b.dataset.g; const lit = m.cot.groups[state.grp].filter(r => r.side).map(r => r.lb); state.lb = lit.length ? lit[lit.length - 1] : state.lb; refreshCot(m, card); }));
    card.querySelectorAll("[data-lb]").forEach(b => b.addEventListener("click", () => { state.lb = b.dataset.lb; refreshCot(m, card); }));
  });
}
function refreshCot(m, card) {
  const holder = document.createElement("div"); holder.innerHTML = cotCard(m, card.querySelector(".tag") !== null);
  card.replaceWith(holder.firstElementChild); hookTips($("#panel"), m); hookCot(m);
}
function select(k, user) {
  if (!M[k]) k = KEYS[0];
  state.k = k; Object.assign(state, defaultCot(M[k]));
  document.querySelectorAll(".tile").forEach(t => t.setAttribute("aria-current", t.dataset.k === k));
  render(k);
  if (user) { try { history.replaceState(null, "", "#" + k); } catch (e) {} if ($("#panel").getBoundingClientRect().top > innerHeight * .6) $("#panel").scrollIntoView({behavior: "smooth", block: "start"}); }
}

/* ---------- filters + keys ---------- */
function filt(f) {
  document.querySelectorAll(".filters .chip").forEach(b => b.setAttribute("aria-pressed", b.id === "f-" + f));
  document.querySelectorAll(".tile").forEach(t => {
    const m = M[t.dataset.k], on = f === "all" || m.verdict === f || (f === "hot" && m.timing && (m.timing.closing || m.timing.flip));
    t.classList.toggle("dim", !on);
  });
}
document.querySelectorAll(".filters .chip").forEach(b => b.addEventListener("click", () => filt(b.id.slice(2))));
addEventListener("keydown", e => {
  if (e.target.closest("input,textarea") || !["ArrowLeft", "ArrowRight"].includes(e.key)) return;
  const i = KEYS.indexOf(state.k), j = (i + (e.key === "ArrowRight" ? 1 : -1) + KEYS.length) % KEYS.length;
  select(KEYS[j], true); $("#t-" + KEYS[j]).focus({preventScroll: true});
});

$("#meta").textContent = `Week of ${new Date(D.today + "T00:00:00").toLocaleDateString("en-GB", {day: "numeric", month: "long", year: "numeric"})} · COT as of ${D.asof}`;
boards();
let start = (location.hash || "").slice(1);
if (!M[start]) start = KEYS.find(k => M[k].timing && M[k].timing.closing && M[k].timing.flip) || KEYS[0];
select(start, false);
</script>
"""

os.makedirs(f"{ROOT}/site", exist_ok=True)
HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">')
out = f"{ROOT}/site/index.html"
open(out, "w").write(HEAD + PAGE.replace("__DATA__", DATA) + "</html>")
print(out, os.path.getsize(out))

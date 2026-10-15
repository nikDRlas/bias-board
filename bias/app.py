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
  --q:#f5c518; --q-ink:#2b2100; --q-deep:#9a6b00; --q-soft:#fff3c2; --q-line:#ecd68a; --q-bg:#f7f3e6;
  --display:"Bricolage Grotesque",ui-sans-serif,system-ui,sans-serif; --body:"Instrument Sans",system-ui,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,monospace; --shadow:0 1px 2px rgba(22,33,58,.06),0 6px 18px rgba(22,33,58,.07);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0e1424; --card:#161f33; --ink:#e8ecf5; --mute:#93a0bd; --line:#263252;
  --bull:#3fd0a4; --bull-soft:#12372f; --bear:#ff7d68; --bear-soft:#3d1f1d; --flat:#7d88a3; --flat-soft:#222c43;
  --sun:#ffc933; --sun-soft:#3a3115; --retail:#e07ae8; --comm:#6ea0ff; --funds:#ffaa4d; --shadow:0 1px 2px rgba(0,0,0,.3),0 8px 22px rgba(0,0,0,.25);
  --q:#ffd23f; --q-ink:#231b00; --q-deep:#ffd23f; --q-soft:#3a3214; --q-line:#5a4b1a; --q-bg:#15140e; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0e1424; --card:#161f33; --ink:#e8ecf5; --mute:#93a0bd; --line:#263252;
  --bull:#3fd0a4; --bull-soft:#12372f; --bear:#ff7d68; --bear-soft:#3d1f1d; --flat:#7d88a3; --flat-soft:#222c43;
  --sun:#ffc933; --sun-soft:#3a3115; --retail:#e07ae8; --comm:#6ea0ff; --funds:#ffaa4d; --shadow:0 1px 2px rgba(0,0,0,.3),0 8px 22px rgba(0,0,0,.25);
  --q:#ffd23f; --q-ink:#231b00; --q-deep:#ffd23f; --q-soft:#3a3214; --q-line:#5a4b1a; --q-bg:#15140e; color-scheme:dark}
*{box-sizing:border-box}
[hidden]{display:none!important}
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
.tested{display:flex;flex-direction:column;gap:8px;margin-top:12px;padding:10px 12px;border:1px dashed var(--line);border-radius:12px;font-size:13px;color:var(--mute);max-width:66ch}
.iscs{display:flex;flex-wrap:wrap;gap:12px 18px} .isc{display:flex;align-items:center;gap:10px;min-width:0}
.isg{flex:1 1 260px;min-width:0;display:flex;flex-direction:column;gap:8px;padding:8px 10px;border-radius:10px;background:color-mix(in srgb,var(--line) 25%,transparent)}
.isgh{display:flex;align-items:center;gap:6px;font:700 11px/1 var(--body);letter-spacing:.08em;text-transform:uppercase;color:var(--ink)}
.isgh .fa{margin-right:0}
.isc > b{font:800 30px/1 var(--display);color:var(--ink)} .wf{margin:0;font-size:11.5px;color:var(--mute)}
.tested > b{font:800 24px/1 var(--display);color:var(--ink)} .tested b.tl{font-weight:600;color:var(--ink)}
.card h3 .tag.ctx{background:var(--flat-soft);color:var(--mute)}
.card h3 .tag.conflict{background:var(--bear-soft);color:var(--bear)}
.yrs{display:flex;flex-wrap:wrap;gap:6px}
.yr{display:flex;flex-direction:column;align-items:center;gap:3px;font:11px var(--mono);color:var(--mute);padding:5px 4px 3px;border-radius:10px;border:2px solid transparent;min-width:38px}
.yr.agree{border-color:var(--ink)} .yr.against{border-color:var(--bear);border-style:dashed} .yr.none{border-color:var(--line)}
.yr .dot{width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font:700 12px var(--body);color:var(--card)}
.yr .dot.w{background:var(--bull)} .yr .dot.l{background:var(--bear)}
.legend .lg{width:14px;height:10px;border-radius:3px;border:2px solid var(--ink);background:transparent}
.legend .lg.against{border-color:var(--bear);border-style:dashed} .legend .lg.none{border-color:var(--line)}
.evg{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin-top:8px}
.ev{border:1px solid var(--line);border-radius:14px;padding:10px 12px;display:flex;flex-direction:column;gap:6px;min-width:0}
.ev.on{border-color:var(--sun);box-shadow:inset 0 0 0 1px var(--sun)}
.evh{display:flex;justify-content:space-between;align-items:center;gap:8px} .evh b{font:700 15px var(--display)}
.evw{font-size:12.5px;color:var(--mute)} .evs{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--mute)} .evs b{font:600 14px var(--mono);color:var(--ink)}
.ev .note{margin:0}
.tile .evb{font:600 10.5px/1 var(--body);padding:3px 6px;border-radius:999px;background:var(--sun-soft);color:var(--sun)}
.views{display:inline-flex;border:1.5px solid var(--line);border-radius:999px;padding:3px;background:var(--card);gap:2px}
.vbtn{font:600 13px/1 var(--body);border:0;background:transparent;color:var(--mute);padding:8px 13px;border-radius:999px;cursor:pointer;transition:background .2s,color .2s}
.vbtn[aria-selected="true"]{background:var(--ink);color:var(--bg)}
.vbtn.q[aria-selected="true"]{background:var(--q);color:var(--q-ink)}
.vbtn:focus-visible{outline:3px solid var(--sun);outline-offset:2px}
.qintro{color:var(--mute);max-width:70ch;margin:20px 0 0;font-size:14px}
body.quant{background:var(--q-bg)}
body.quant .top{background:color-mix(in srgb,var(--q-bg) 88%,transparent);border-bottom-color:var(--q-line)}
#quant-view h2.sec{color:var(--q-deep)}
.qtile{position:relative;text-align:left;background:var(--card);border:1.5px solid var(--q-line);border-radius:14px;padding:11px 12px 10px;cursor:pointer;color:var(--ink);font:inherit;
  box-shadow:var(--shadow);transition:transform .18s cubic-bezier(.3,1.6,.5,1),border-color .15s;display:flex;flex-direction:column;gap:6px;min-width:0}
.qtile:hover{transform:translateY(-3px) rotate(.4deg)}
.qtile[aria-current="true"]{border-color:var(--q-deep);box-shadow:0 0 0 3px color-mix(in srgb,var(--q) 35%,transparent),var(--shadow)}
.qtile.on{background:linear-gradient(180deg,var(--q-soft),var(--card) 70%)}
.qtile:focus-visible{outline:3px solid var(--q-deep);outline-offset:2px}
.qtile .nm{font:700 15px/1.15 var(--display)} .qtile .tk{font:12px var(--mono);color:var(--mute)}
.qstat{font-size:12px;color:var(--mute)} .qstat b{font:700 13px var(--mono);color:var(--ink)}
.qwhen{font:600 11.5px/1 var(--body);padding:4px 7px;border-radius:999px;background:var(--q-soft);color:var(--q-deep);align-self:flex-start}
.qwhen.on{background:var(--q);color:var(--q-ink)}
.bars{height:24px;width:100%}
.qpanel{border-color:var(--q-line)}
.qpanel .hero h1{color:var(--ink)}
.qbig{display:flex;flex-wrap:wrap;gap:12px 28px;margin-top:16px}
.qbig div{display:flex;flex-direction:column;gap:3px} .qbig b{font:800 34px/1 var(--display);color:var(--q-deep)} .qbig span{font-size:12px;color:var(--mute)}
.qbanner{display:flex;gap:10px;align-items:flex-start;margin-top:16px;padding:11px 14px;border-radius:12px;background:var(--q-soft);font-size:14px}
.qbanner.on{background:var(--q);color:var(--q-ink)}
.qrule{border-left:4px solid var(--q);padding:8px 12px;margin-top:16px;background:var(--q-soft);border-radius:0 10px 10px 0;font-size:14px}
.dots{display:inline-flex;gap:3px;align-items:center;vertical-align:middle;margin-left:4px}
.dots i{width:7px;height:7px;border-radius:50%;background:var(--line);display:block}
.dots i.on{background:var(--ink)}
.dots.big i{width:10px;height:10px}
.fa{display:inline-block;font:600 10px/1 var(--body);letter-spacing:.06em;text-transform:uppercase;padding:3px 6px;border-radius:999px;margin-right:6px;background:var(--flat-soft);color:var(--mute)}
.fa.for{background:var(--bull-soft);color:var(--bull)} .fa.against{background:var(--bear-soft);color:var(--bear)}
.wstats{display:flex;flex-wrap:wrap;gap:1px;background:var(--line);border:1px solid var(--line);border-radius:12px;overflow:hidden;margin:10px 0 4px}
.wstats div{flex:1 1 180px;background:var(--card);padding:9px 12px;display:flex;flex-direction:column;gap:3px;min-width:0}
.wstats b{font:700 18px/1 var(--mono);color:var(--ink)} .wstats span{font-size:12px;color:var(--mute)}
.spd{margin:0;font-size:12px;color:var(--mute)} .sp{display:inline-block;font:600 10.5px/1 var(--body);text-transform:uppercase;letter-spacing:.06em;padding:3px 6px;border-radius:999px;margin-right:4px;background:var(--flat-soft);color:var(--mute)}
.sp.fast{background:var(--bull-soft);color:var(--bull)} .sp.slow{background:var(--bear-soft);color:var(--bear)}
.foot{color:var(--mute);font-size:12px;margin-top:28px;max-width:80ch}
.kbd{font:11px var(--mono);border:1px solid var(--line);border-bottom-width:2px;border-radius:5px;padding:1px 5px}
@media (max-width:640px){.hero{grid-template-columns:1fr}.dial{width:160px}.board{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}.draw{stroke-dashoffset:0}}
</style>

<div class="top"><div class="wrap">
  <div class="brand"><svg viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="11" fill="none" stroke="var(--ink)" stroke-width="2.5"/><path d="M13 13 L20 7" stroke="var(--bear)" stroke-width="3" stroke-linecap="round"/><circle cx="13" cy="13" r="2.6" fill="var(--ink)"/></svg>Bias Board</div>
  <div class="views" role="tablist" aria-label="View">
    <button class="vbtn" id="v-outlook" role="tab" aria-selected="true">Outlook</button>
    <button class="vbtn q" id="v-quant" role="tab" aria-selected="false">Quant strategies</button>
  </div>
  <div class="meta" id="meta"></div>
  <div class="filters" id="filters" role="group" aria-label="Filter markets">
    <button class="chip" id="f-all" aria-pressed="true">All</button>
    <button class="chip" id="f-BULLISH" aria-pressed="false">Bullish</button>
    <button class="chip" id="f-BEARISH" aria-pressed="false">Bearish</button>
    <button class="chip" id="f-STAND ASIDE" aria-pressed="false">Stand aside</button>
    <button class="chip" id="f-hot" aria-pressed="false">Window ending</button>
    <a class="chip" href="outlook.html" style="text-decoration:none">Full report</a>
  </div>
</div></div>

<div class="wrap">
  <div id="outlook-view">
    <div id="boards"></div>
    <section class="panel" id="panel" aria-live="polite"></section>
  </div>
  <div id="quant-view" hidden>
    <p class="qintro">Fixed rules with a known cause, defined before testing and validated on the 20 years after they were published. Each one trades on its own dates, separate from the weekly outlook.</p>
    <div id="qboards"></div>
    <section class="panel qpanel" id="qpanel" aria-live="polite"></section>
  </div>
  <p class="foot">COT: CFTC legacy report via LSE (CFTC history for WTI and natural gas). Prices: LSE daily spot, yen, franc and Canadian dollar in futures direction, dollar index rebuilt from its legs. Seasonal windows: Seasonax-style scan in trading days, 15 prior years, at least five trading days long, win ratio 12 of 15 or better. Move between markets with <span class="kbd">←</span> <span class="kbd">→</span>. A bias is not a trade. Educational, not advice.</p>
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
  return `<svg class="ring" viewBox="0 0 34 34" role="img" aria-label="${t.left} trading days left in window">
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
function dots(m, big) {
  const c = m.confidence; if (!c || m.verdict === "STAND ASIDE") return "";
  const tip = `Confidence ${c.dots}/5: ${c.scope} won ${c.win}% (${c.n} trades, avg ${sgn(c.avg)}%, t ${c.t.toFixed(1)}) in the walk-forward test ${c.first}–${c.last}`;
  return `<span class="dots${big ? " big" : ""}" title="${esc(tip)}" aria-label="${esc(tip)}">${[1, 2, 3, 4, 5].map(i => `<i class="${i <= c.dots ? "on" : ""}"></i>`).join("")}</span>`;
}
function evBadge(m) {
  if (!m.events) return "";
  const on = m.events.filter(e => e.active), soon = m.events.filter(e => !e.active && e.days_to <= 5);
  if (on.length) return `<div class="row"><span class="evb">● ${esc(on.map(e => e.name.split(" (")[0]).join(", "))}</span></div>`;
  if (soon.length) return `<div class="row"><span class="evb">○ ${esc(soon.map(e => e.name.split(" (")[0]).join(", "))} in ${Math.min(...soon.map(e => e.days_to))}d</span></div>`;
  return "";
}
function boards() {
  const secs = {};
  KEYS.forEach(k => (secs[M[k].sector] ||= []).push(k));
  $("#boards").innerHTML = Object.entries(secs).map(([s, ks]) => `<h2 class="sec">${s}</h2><div class="board">` + ks.map(k => {
    const m = M[k];
    return `<button class="tile" id="t-${k}" data-k="${k}" aria-current="false">${ring(m)}
      <div><div class="nm">${esc(m.name)}</div><div class="tk">${k}</div></div>
      <div class="row">${pill(m.verdict)}${dots(m)}</div>
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
  const g = m.groups === 2 ? "commercials, with retail and funds on the other side" : "commercials, with retail or funds on the other side";
  switch (m.basis) {
    case "COT + calendar": return `Both engines point ${m.verdict.toLowerCase()}: ${g} at extremes, and the calendar agrees (${win}).`;
    case "COT only": return `COT carries the bias alone: ${g} at extremes. ${s.read === "SELF-CANCELLING" ? "The calendar cancels itself out." : "No seasonal window is in play."}`;
    case "Calendar only": return `The calendar carries the bias alone: ${win}. Positioning has no side.`;
  }
  const ag = (s.past && s.past.summary.against) || {n: 0, w: 0};
  if (m.basis === "Calendar over COT") return `COT reads ${title(c.read)} (${g}), against the calendar: ${win}. In the past years when COT was against this window it still paid ${ag.w} of ${ag.n} times, so the calendar stands.`;
  if (m.basis.startsWith("Conflict")) return `No bias. COT reads ${title(c.read)} (${g}) while the calendar says ${title(s.read)} (${win}). ${ag.n >= 3 ? `In past years with COT against it, this window paid only ${ag.w} of ${ag.n} times` : `This window has too few past years with COT against it (${ag.n}) to judge`}, so COT is relevant here and we wait.`;
  return `No bias. The commercials are not at an extreme with retail or funds on the other side, and ${s.read === "SELF-CANCELLING" ? "the calendar cancels itself out" : "there is no seasonal window in play"}.`;
}
function bestCotRow(m) {
  const e = m.cot.edge;
  if (e) return {...e, bar: true};
  let best = null;
  ["retail", "comm"].forEach(g => m.cot.groups[g].forEach(r => {
    if (!r.dir || r.dir !== m.cot.read) return;
    [4, 8].forEach(h => { const c = r.h[h]; if (c && c.n >= 3 && (!best || c.w / c.n > best.w / best.n)) best = {...c, group: g, lb: r.lb, h, bar: false}; });
  }));
  return best;
}
function fa(m, side) {
  if (m.verdict === "STAND ASIDE") return `<span class="fa">${side === "BULLISH" ? "says bullish" : "says bearish"}</span>`;
  return side === m.verdict ? '<span class="fa for">for the verdict</span>' : '<span class="fa against">against the verdict</span>';
}
function testedHero(m) {
  const d = m.seas.driver, groups = [], cf = m.confidence;
  const usesCal = ["Calendar only", "Calendar over COT", "COT + calendar"].includes(m.basis) || m.basis.startsWith("Conflict");
  const usesCot = m.basis.startsWith("COT") || m.basis === "Calendar over COT" || m.basis.startsWith("Conflict");
  const line = (big, title, txt) => `<div class="isc"><b>${big}</b><span><b class="tl">${title}</b> ${txt}</span></div>`;
  if (usesCal && d) {
    const dirAvg = d.side === "BUY" ? d.avg : -d.avg;
    groups.push(`<div class="isg"><div class="isgh">${fa(m, d.side === "BUY" ? "BULLISH" : "BEARISH")}<span>Seasonality</span></div>
      ${line(`${Math.round(100 * d.wins / 15)}%`, "Window", `${d.wins} of 15 years · avg ${sgn(+dirAvg.toFixed(2))}% · last 4: ${d.rec}/4`)}</div>`);
  }
  if (usesCot && m.cot.read !== "STAND ASIDE") {
    const rc = m.cot.record, c = bestCotRow(m), rows = [];
    const H = {4: "4 weeks", 8: "8 weeks", 13: "3 months", 26: "6 months", 52: "1 year"};
    if (rc) rows.push(line(`${Math.round(100 * rc.w / rc.n)}%`, `Read ${m.cot.read.toLowerCase()}`, `${rc.w} of ${rc.n} times since ${rc.first} · avg ${sgn(rc.avg)}% over ${rc.hold} weeks · last 4: ${rc.rec}/4`));
    if (c) rows.push(line(`${Math.round(100 * c.w / c.n)}%`, `${GN[c.group]} · ${c.lb}`, `${c.w} of ${c.n} past cases · avg ${sgn(c.avg)}% over ${H[c.h]}${c.bar ? "" : " · below the 6-case bar"}`));
    const sp = m.cot.speed;
    if (sp) rows.push(`<p class="spd"><b class="sp ${sp.speed}">${sp.speed === "fast" ? "Reached fast" : sp.speed === "slow" ? "Crept in slowly" : "Medium speed"}</b> commercials moved ${sp.move.toFixed(1)}× a typical 4-week change into this extreme. ${title(sp.speed)} signals won ${sp.all.win}% since 2003 and ${sp.recent.win}% since 2016 (fast ${sp.fast_all.win}%, slow ${sp.slow_all.win}%).</p>`);
    if (rows.length) groups.push(`<div class="isg"><div class="isgh">${fa(m, m.cot.read)}<span>COT</span></div>${rows.join("")}</div>`);
  }
  if (!groups.length && !cf) return "";
  const wf = cf ? `<p class="wf">Confidence ${cf.dots}/5 · walk-forward ${cf.first}–${cf.last}: ${esc(cf.scope)} won ${cf.win}% · ${cf.n} trades · avg ${sgn(cf.avg)}% · t ${cf.t.toFixed(1)}. The big numbers are each signal's own history; this line is how this kind of verdict did when traded week by week afterwards.</p>` : "";
  return `<div class="tested">${groups.length ? `<div class="iscs">${groups.join("")}</div>` : ""}${wf}</div>`;
}
function banner(m) {
  const t = m.timing; if (!t) return "";
  const lvl = warnLevel(t);
  let txt = `<b>Seasonal window ends ${fmtD(t.end)}, ${t.left} trading days left.</b>`;
  if (t.flip) txt += ` Then a ${t.flip.side.toLowerCase()} window opens ${fmtD(t.flip.start)} (${t.flip.wins} of 15 years).`;
  if (lvl === "hot") txt += ` The window is about to close and the calendar then turns the other way.`;
  return `<div class="banner ${lvl}"><svg class="clock" viewBox="0 0 22 22" aria-hidden="true"><circle cx="11" cy="11" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M11 6v5l3.5 2.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><div>${txt}</div></div>`;
}

/* ---------- charts ---------- */
function lineLen(pts) { let L = 0; for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); return Math.ceil(L) + 2; }
function poly(pts, stroke, w, extra = "") {
  return `<polyline points="${pts.map(p => p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ")}" fill="none" stroke="${stroke}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round" class="draw" style="--len:${lineLen(pts)}" ${extra}/>`;
}
let seasonFit = true;
const fmtPx = v => { const a = Math.abs(v); return v.toFixed(a >= 1000 ? 0 : a >= 100 ? 1 : a >= 10 ? 2 : a >= 1 ? 3 : 5); };
function seasonPaths(m) {
  const s = m.seas, base = s.base, toP = v => base * (1 + v / 100), n = s.avg["15"].length, mc = s.cur.length;
  const a15 = s.avg["15"], k0 = mc - 1, now = toP(s.cur[k0]);
  // every average path is anchored to pass through today's price, so it reads directly against the price line
  const anchor = a => a.map(v => now * (1 + v / 100) / (1 + a[k0] / 100));
  const cur = s.cur.map(toP);
  let A5 = anchor(s.avg["5"]), A10 = anchor(s.avg["10"]), A15 = anchor(a15), k = 1;
  if (seasonFit) {
    // stretch the seasonal paths around today's price so their swing so far this year matches the price's swing
    const rng = a => Math.max(...a.slice(0, mc)) - Math.min(...a.slice(0, mc));
    k = Math.max(1, Math.min(25, rng(cur) / (rng(A15) || 1)));
    const st = a => a.map(v => now + k * (v - now));
    A5 = st(A5); A10 = st(A10); A15 = st(A15);
  }
  const proj = []; for (let i = k0; i < n; i++) proj.push([i, A15[i]]);
  return {n, mc, cur, a5: A5, a10: A10, a15: A15, proj, k};
}
function windowStats(m) {
  const s = m.seas, d = s.driver, r = s.remaining; if (!d || !r) return "";
  const pc = v => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
  const cell = (big, small) => `<div><b>${big}</b><span>${small}</span></div>`;
  return `<div class="wstats">
    ${cell(pc(d.avg), `usual move over the whole window, ${fmtD(d.start)} – ${fmtD(d.end)}`)}
    ${cell(pc(r.avg), `${r.started ? "still to come" : "expected"} over the ${r.days} trading days ${r.started ? "left" : "of the window"} · went that way ${r.wins} of 15 years`)}
    ${r.so_far == null ? "" : cell(pc(r.so_far), "this year so far in the window")}
  </div>`;
}
function seasonChart(m) {
  const s = m.seas, W = 760, H = 290, L = 58, R = 14, T = 14, B = 26, sp = seasonPaths(m), n = sp.n;
  const all = [...sp.cur, ...sp.a5, ...sp.a10, ...sp.a15, ...sp.proj.map(p => p[1])];
  let lo = Math.min(...all), hi = Math.max(...all); const pad = (hi - lo) * .06; lo -= pad; hi += pad;
  const X = i => L + (W - L - R) * i / (n - 1), Y = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo || 1));
  const doy = d => { const t = new Date(d + "T00:00:00"); return (t - new Date(t.getFullYear(), 0, 1)) / 864e5; };
  const XD = d => { const t = new Date(d + "T00:00:00"); const yy = t.getFullYear() > TODAY.getFullYear() ? 365 : 0; return X(Math.min(n - 1, (doy(d) + yy) / 365 * (n - 1))); };
  let bands = "";
  s.windows.forEach(w => {
    const x0 = XD(w.start), x1 = XD(w.end), main = !!(s.driver && w.start === s.driver.start && w.side === s.driver.side), col = w.side === "BUY" ? "var(--bull)" : "var(--bear)";
    const flip = m.timing && m.timing.flip && m.timing.flip.start === w.start;
    if (!main && !flip) return;
    bands += `<rect x="${x0}" y="${T}" width="${Math.max(2, x1 - x0)}" height="${H - T - B}" fill="${col}" opacity="${main ? .13 : .07}" ${flip ? 'stroke="' + col + '" stroke-dasharray="4 4" stroke-opacity=".6"' : ""} rx="4"/>
      <text x="${x0 + 5}" y="${T + (main ? 13 : 29)}" style="font:600 11px var(--body);fill:${col}">${main ? "◀ driver · " : "next · "}${w.side.toLowerCase()} ${w.wins}/15</text>`;
  });
  const tx = X(sp.mc - 1);
  const months = "JFMAMJJASOND".split("").map((c, i) => `<text x="${X((i + .5) / 12 * (n - 1))}" y="${H - 8}" text-anchor="middle">${c}</text>`).join("");
  const tv = [0, 1, 2, 3, 4].map(j => lo + (hi - lo) * (j + .5) / 5);
  const ticks = tv.map(v => `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke-dasharray="2 4"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end">${fmtPx(v)}</text>`).join("");
  const P = a => a.map((v, i) => [X(i), Y(v)]);
  const cur = P(sp.cur), proj = sp.proj.map(([i, v]) => [X(i), Y(v)]);
  const d = s.driver, xEnd = d ? XD(d.end) : null;
  const projW = d ? proj.filter(p => p[0] <= xEnd + 0.5) : [];
  const pcol = d && d.side === "SELL" ? "var(--bear)" : "var(--bull)";
  return `<div class="chart" data-kind="season"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Seasonal price chart">${bands}<g class="ax">${ticks}${months}</g>
    ${poly(P(sp.a5), "var(--line)", 1.4)}${poly(P(sp.a10), "var(--flat)", 1.4)}${poly(P(sp.a15), "var(--mute)", 1.8)}
    ${poly(cur, "var(--ink)", 3)}
    ${projW.length > 1 ? `<polyline points="${projW.map(p => p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ")}" fill="none" stroke="${pcol}" stroke-width="3" stroke-dasharray="7 5" stroke-linecap="round"/><circle cx="${projW[projW.length - 1][0]}" cy="${projW[projW.length - 1][1]}" r="4.5" fill="${pcol}" stroke="var(--card)" stroke-width="2"/>` : ""}
    <line x1="${tx}" x2="${tx}" y1="${T}" y2="${H - B}" stroke="var(--sun)" stroke-width="2" stroke-dasharray="3 3"/>
    <circle cx="${cur[cur.length - 1][0]}" cy="${cur[cur.length - 1][1]}" r="5" fill="var(--sun)" class="pulse"/>
    <circle cx="${cur[cur.length - 1][0]}" cy="${cur[cur.length - 1][1]}" r="4" fill="var(--sun)" stroke="var(--card)" stroke-width="2"/>
    <rect class="hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent"/></svg><div class="tip"></div></div>
    ${windowStats(m)}
    <div class="legend"><span><i style="background:var(--ink)"></i>${TODAY.getFullYear()} price</span><span><i style="background:${pcol}"></i>usual path to the window's end</span><span><i style="background:var(--mute)"></i>15-yr avg</span><span><i style="background:var(--flat)"></i>10-yr</span><span><i style="background:var(--line)"></i>5-yr</span><span><i style="background:var(--sun)"></i>today</span>${sp.k > 1 ? `<span>seasonal paths stretched ×${sp.k.toFixed(1)} to compare shape; the numbers above are real</span>` : ""}</div>`;
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
        const sp = seasonPaths(m), i = Math.round(f * (sp.n - 1)), mo = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ")[Math.min(11, Math.floor(f * 12))];
        const pj = sp.proj.find(p => p[0] === i);
        html = `${mo} · 15y avg ${fmtPx(sp.a15[i])}` + (i < sp.mc ? ` · ${TODAY.getFullYear()} ${fmtPx(sp.cur[i])}` : pj ? ` · projection ${fmtPx(pj[1])}` : "");
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
  const pc = v => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
  return `<div class="tbl"><table><thead><tr><th>Trade</th><th>Window</th><th>Trading days</th><th>Win ratio</th><th>Avg</th><th>Median</th><th>Annualised</th><th>Best / worst</th><th>Trend removed</th><th>Last 4</th></tr></thead><tbody>` +
    s.windows.map(w => `<tr><td>${pill(sideV(w.side), title(w.side))}${s.driver && w.start === s.driver.start ? ' <span class="st live">driver</span>' : ""}</td><td>${fmtD(w.start)} – ${fmtD(w.end)}</td><td class="n">${w.len}</td><td class="n">${w.wins} of 15</td><td class="n">${pc(w.avg)}</td><td class="n">${pc(w.median)}</td><td class="n">${w.annual >= 0 ? "+" : ""}${w.annual}%</td><td class="n">${pc(w.best)} / ${pc(w.worst)}</td><td class="n">${w.wins_true} of 15</td><td class="n">${w.rec}/4</td></tr>`).join("") +
    `</tbody></table></div><p class="note">Seasonax-style statistics over the last 15 years, counted in trading days. Win ratio: years in which price moved the trade's way over the window. Avg, median and annualised are price moves (negative is good for a sell window); best and worst are in the trade's direction. Trend removed: the same count after taking out each year's trend.</p>`;
}
function eventsCard(m) {
  const ev = m.events; if (!ev) return "";
  const card = e => {
    const when = e.active ? `<span class="st live">active now</span> until ${fmtD(e.exit)}` : e.entry ? `next: ${fmtD(e.entry)} → ${fmtD(e.exit)} · in ${e.days_to} trading days` : "";
    return `<div class="ev ${e.active ? "on" : ""}"><div class="evh"><b>${esc(e.name)}</b>${pill("BULLISH", "Buy")}</div>
      <div class="evw">${when}</div>
      <div class="evs"><span><b>${e.win}%</b> won</span><span><b>${e.avg >= 0 ? "+" : ""}${e.avg}%</b> avg</span><span><b>${e.n}</b> times, 15 yrs</span></div>
      <p class="note">${esc(e.why)}. Tested: ${esc(e.test)}.</p></div>`;
  };
  return `<div class="card"><h3>Calendar events <span class="tag ctx">fixed in advance, with a cause</span></h3>
    <p class="note">Seasonal effects defined before testing and validated in our July 2026 test on 20 years after their publication. Shown as information; they do not change the verdict.</p>
    <div class="evg">${ev.map(card).join("")}</div></div>`;
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
  return `<div class="card" id="cotcard"><h3>Positioning ${chartTag(m, "cot")} ${pill(c.read === "STAND ASIDE" ? "NEUTRAL" : c.read, c.read === "STAND ASIDE" ? "Neutral" : title(c.read))}</h3>
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
function chartTag(m, which) {
  const b = m.basis, drive = '<span class="tag">drives the bias</span>', off = t => `<span class="tag ctx">${t}</span>`;
  if (b.startsWith("Conflict")) return '<span class="tag conflict">in conflict · no bias</span>';
  if (b === "COT + calendar") return drive;
  if (b === "COT only") return which === "cot" ? drive : off("not part of the verdict");
  if (b === "Calendar only") return which === "seas" ? drive : off("not part of the verdict");
  if (b === "Calendar over COT") return which === "seas" ? drive : off("overruled by the calendar");
  return off("no side");
}
function seasonCard(m, ess) {
  const s = m.seas;
  return `<div class="card"><h3>Seasonality ${chartTag(m, "seas")} ${pill(s.read === "BULLISH" || s.read === "BEARISH" ? s.read : "flat", title(s.read))}${s.strength ? ` <span class="st">${title(s.strength)} · ${s.kind}</span>` : ""}</h3>
    <p class="note">In price: ${TODAY.getFullYear()} so far, and the average path of the last 5, 10 and 15 years lined up to pass through today's price, with the usual path from today to the end of the current seasonal window (dashed). The numbers under the chart are measured over the same trading days in each of the last 15 years. Shape match ${s.shape >= 0 ? "+" : ""}${s.shape.toFixed(2)}, ${s.shape_read}.</p>
    <div class="ctl" role="group" aria-label="Seasonal scale"><button class="chip" data-fit="1" aria-pressed="${seasonFit}">Stretched to the price's swing</button><button class="chip" data-fit="0" aria-pressed="${!seasonFit}">Real size</button></div>
    <div id="seaschart">${seasonChart(m)}</div>${pastYears(m)}</div>`;
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
      ${row("Currencies, vs one group", cc["FX|1"])}${row("Currencies, vs retail & funds", cc["FX|2"])}${row("Metals & energy, vs one group", cc["Commodities|1"])}${row("Metals & energy, vs retail & funds", cc["Commodities|2"])}${row("Indices, vs one group", cc["Indices|1"])}${row("Indices, vs retail & funds", cc["Indices|2"])}${row("Agriculture, vs one group", cc["Agriculture|1"])}${row("Agriculture, vs retail & funds", cc["Agriculture|2"])}</tbody></table></div>
    ${D.verdict_test ? `<h4 class="note" style="font-weight:600;color:var(--ink);margin-top:12px">The board's final verdict (${D.verdict_test.first.slice(0, 4)}–${D.verdict_test.last.slice(0, 4)}), the basis of the confidence dots</h4>
    <div class="tbl"><table>${hd}<tbody>${row("All verdicts", D.verdict_test.all)}${Object.entries(D.verdict_test.by_basis).map(([k, o]) => row(k, o)).join("")}${Object.entries(D.verdict_test.by_cell).map(([k, o]) => row("· " + k.replace(" | ", ", "), o)).join("")}</tbody></table></div>
    <p class="note">Dots: t below 0 = 1, 0–1 = 2, 1–2 = 3, 2–3 = 4, 3 or more = 5, from the verdict type in the market's asset class (or across all markets when that cell has fewer than 40 trades).</p>` : ""}
    <h4 class="note" style="font-weight:600;color:var(--ink);margin-top:12px">Per asset: each market tested on its own data</h4>
    <div class="tbl"><table><thead><tr><th>Market</th><th>Seasonal trades</th><th>Won</th><th>Avg</th><th>COT trades</th><th>Won</th><th>Avg</th></tr></thead><tbody>${KEYS.map(k => { const pa = (T.per_asset || {})[k] || {}, a = pa.seas, b = pa.cot;
      const c = o => o ? `<td class="n">${o.n}</td><td class="n">${o.win}%</td><td class="n">${sgn(o.avg)}%</td>` : `<td class="n">–</td><td class="n">–</td><td class="n">–</td>`;
      return `<tr><th>${esc(M[k].name)}</th>${c(a)}${c(b)}</tr>`; }).join("")}</tbody></table></div>
    <p class="note">Per market the samples are small (a few dozen trades over 7–10 years), so single rows swing a lot; the pooled rows above are the more reliable read.</p>
    <p class="note">How the board uses this: each engine may carry the bias alone. In a contradiction the calendar stands if the window already paid in at least 2 of 3 past years when COT was against it (at least 3 such years); otherwise there is no bias. Tested, that split made no difference: the calendar won 50.5% when the window had played out against COT and 50.0% when it had not. In contradictions the calendar won about half the time and COT only slightly more, so neither earns the right to overrule the other. Both edges are small: the COT read wins about 54% over 8 weeks and is only clearly above zero pooled across all markets; the seasonal windows have not beaten a coin flip out of sample.</p></details>`;
}
function render(k) {
  const m = M[k], P = $("#panel");
  const cEss = cotLed(m) || m.basis.startsWith("Conflict"), sEss = seasonLed(m) || m.basis.startsWith("Conflict");
  const evc = "";
  const cards = (m.basis === "Calendar only" || m.basis === "Calendar over COT") ? [seasonCard(m, true), evc, cotCard(m, m.basis !== "Calendar only")] : [cotCard(m, cEss), seasonCard(m, sEss), evc];
  const extra = [];
  P.style.animation = "none"; void P.offsetWidth; P.style.animation = "";
  P.innerHTML = `<div class="hero"><div><h1>${esc(m.name)}</h1><div class="sub">${k} · ${m.sector} · ${pill(m.verdict)} ${dots(m, true)} <span style="margin-left:6px">${m.basis}</span></div>
      <p class="why">${why(m)}</p>${testedHero(m)}</div>${dial(m)}</div>${banner(m)}
    <div class="engines"><div class="eng ${cEss ? "lead" : ""}">${ICON.cot.replace("<svg", '<svg width="16" height="16"')}<span class="k">COT</span><b>${c_read(m)}</b>${m.cot.conv}</div>
      <div class="eng ${sEss ? "lead" : ""}">${ICON.cal.replace("<svg", '<svg width="16" height="16"')}<span class="k">Seasonality</span><b>${title(m.seas.read)}</b>${m.seas.strength ? title(m.seas.strength) : "–"}</div></div>
    <div class="charts">${cards.filter(Boolean).join("")}</div>${extra.join("")}
    <details><summary>Track record<small>what the live extremes did before</small></summary><p class="note">${edge(m)}</p>${track(m, 4)}${track(m, 8)}</details>
    ${m.seas.windows.length ? `<details><summary>Windows in play<small>entry −2 to +8 weeks</small></summary>${windowsTbl(m)}<h4 class="note" style="margin-top:12px">Neighbour test</h4>${nbrs(m)}</details>` : ""}
    <details><summary>Years most like this one<small>analog cross-check</small></summary>${analogs(m)}</details>${testedSection()}`;
  requestAnimationFrame(() => requestAnimationFrame(() => { const n = $("#needle"); if (n) n.style.transform = `rotate(${n.dataset.a}deg)`; }));
  hookTips(P, m); hookCot(m); hookFit(m);
}
function hookFit(m) {
  document.querySelectorAll("#panel [data-fit]").forEach(b => b.addEventListener("click", () => {
    seasonFit = b.dataset.fit === "1";
    document.querySelectorAll("#panel [data-fit]").forEach(x => x.setAttribute("aria-pressed", (x.dataset.fit === "1") === seasonFit));
    const holder = $("#seaschart"); if (holder) { holder.innerHTML = seasonChart(m); hookTips(holder, m); }
  }));
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

/* ---------- quant strategies ---------- */
const Q = D.quant || [];
const QBY = Object.fromEntries(Q.map(q => [q.id, q]));
const qWhen = q => q.active ? `Active · ${q.days_left} td left` : q.entry ? (q.days_to <= 0 ? "Starts today" : `In ${q.days_to} td`) : "No date";
function qbars(q, W = 150, H = 24, last = 36) {
  const h = q.hist.slice(-last); if (!h.length) return "";
  const mx = Math.max(...h.map(x => Math.abs(x.r))) || 1, bw = W / h.length;
  return `<svg class="bars" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><line x1="0" x2="${W}" y1="${H / 2}" y2="${H / 2}" stroke="var(--line)"/>` +
    h.map((x, i) => { const hh = Math.max(1, Math.abs(x.r) / mx * (H / 2 - 1)); return `<rect x="${(i * bw + bw * .15).toFixed(1)}" width="${(bw * .7).toFixed(1)}" y="${x.r >= 0 ? H / 2 - hh : H / 2}" height="${hh}" fill="${x.r > 0 ? "var(--bull)" : "var(--bear)"}"/>`; }).join("") + `</svg>`;
}
function qboards() {
  const by = {};
  Q.forEach(q => (by[q.name] ||= []).push(q));
  $("#qboards").innerHTML = Object.entries(by).map(([name, qs]) => `<h2 class="sec">${esc(name)}</h2><div class="board">` + qs.map(q =>
    `<button class="qtile ${q.active ? "on" : ""}" id="qt-${q.id}" data-q="${q.id}" aria-current="false">
       <div><div class="nm">${esc(q.market_name)}</div><div class="tk">${q.market} · ${esc(q.name)}</div></div>
       <div class="row">${pill(sideV(q.side), title(q.side))}<span class="qwhen ${q.active ? "on" : ""}">${qWhen(q)}</span></div>
       <div class="qstat"><b>${q.win}%</b> won · PF <b>${q.pf == null ? "∞" : q.pf.toFixed(2)}</b> · <b>${sgn(q.avg)}%</b> avg · ${q.n}×</div>${qbars(q)}</button>`).join("") + `</div>`).join("");
  document.querySelectorAll(".qtile").forEach(b => b.addEventListener("click", () => qselect(b.dataset.q, true)));
}
function qchart(q) {
  const h = q.hist, W = 760, H = 240, L = 46, R = 12, T = 14, B = 26; if (!h.length) return "";
  const mx = Math.max(...h.map(x => Math.abs(x.r))) || 1, n = h.length, bw = (W - L - R) / n;
  const Y = v => T + (H - T - B) * (1 - (v + mx) / (2 * mx));
  const years = []; h.forEach((x, i) => { if (i && x.d.slice(0, 4) !== h[i - 1].d.slice(0, 4)) years.push(`<line x1="${L + i * bw}" x2="${L + i * bw}" y1="${T}" y2="${H - B}" stroke-dasharray="2 4"/><text x="${L + i * bw + 3}" y="${H - 8}">${x.d.slice(0, 4)}</text>`); });
  let cum = 0; const cp = h.map((x, i) => { cum += x.r; return [L + (i + .5) * bw, cum]; });
  const cmx = Math.max(...cp.map(c => Math.abs(c[1])), 1e-9), CY = v => T + (H - T - B) * (1 - (v + cmx) / (2 * cmx));
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Every occurrence, last 15 years">
    <g class="ax">${years.join("")}<line x1="${L}" x2="${W - R}" y1="${Y(0)}" y2="${Y(0)}"/><text x="${L - 6}" y="${Y(mx) + 4}" text-anchor="end">+${mx.toFixed(1)}%</text><text x="${L - 6}" y="${Y(-mx) + 4}" text-anchor="end">−${mx.toFixed(1)}%</text></g>
    ${h.map((x, i) => { const y0 = Y(0), y1 = Y(x.r); return `<rect x="${(L + i * bw + bw * .12).toFixed(1)}" width="${Math.max(1, bw * .76).toFixed(1)}" y="${Math.min(y0, y1).toFixed(1)}" height="${Math.max(1, Math.abs(y1 - y0)).toFixed(1)}" rx="1.5" fill="${x.r > 0 ? "var(--bull)" : "var(--bear)"}" opacity=".85"><title>${x.d}: ${sgn(x.r)}%</title></rect>`; }).join("")}
    ${poly(cp.map(c => [c[0], CY(c[1])]), "var(--q-deep)", 2.6)}</svg></div>
    <div class="legend"><span><i style="background:var(--bull)"></i>trade won</span><span><i style="background:var(--bear)"></i>lost</span><span><i style="background:var(--q-deep)"></i>running total (own scale)</span></div>`;
}
let qstate = null;
function qrender(id) {
  const q = QBY[id], P = $("#qpanel");
  const when = q.active ? `<b>Active now.</b> Entered ${fmtD(q.entry)}, exit at the close on ${fmtD(q.exit)} (${q.days_left} trading days left).`
    : q.entry ? `<b>Next: ${q.side === "BUY" ? "buy" : "sell"} at the close on ${fmtD(q.entry)}, exit at the close on ${fmtD(q.exit)}.</b> Starts in ${q.days_to} trading days.` : "No upcoming date.";
  P.style.animation = "none"; void P.offsetWidth; P.style.animation = "";
  P.innerHTML = `<div class="hero"><div><h1>${esc(q.name)}</h1><div class="sub">${esc(q.market_name)} · ${q.market} · ${pill(sideV(q.side), title(q.side))}</div>
      <p class="why">${esc(q.why.charAt(0).toUpperCase() + q.why.slice(1))}.</p></div></div>
    <div class="qbanner ${q.active ? "on" : ""}"><svg class="clock" width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><circle cx="11" cy="11" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M11 6v5l3.5 2.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><div>${when}</div></div>
    <div class="qbig"><div><b>${q.win}%</b><span>won, last 15 years</span></div><div><b>${q.pf == null ? "∞" : q.pf.toFixed(2)}</b><span>profit factor</span></div><div><b>${sgn(q.avg)}%</b><span>average per trade</span></div><div><b>${sgn(q.median)}%</b><span>median</span></div><div><b>${q.n}</b><span>trades</span></div><div><b>${q.t == null ? "–" : q.t.toFixed(1)}</b><span>t-stat</span></div></div>
    <div class="qrule"><b>Rule.</b> ${esc(q.rule)}</div>
    <div class="charts"><div class="card"><h3>Every trade, last 15 years</h3><p class="note">One bar per trade, in the trade's direction. Hover a bar for its date.</p>${qchart(q)}</div></div>
    <p class="note" style="margin-top:14px"><b>Validation.</b> ${esc(q.test.charAt(0).toUpperCase() + q.test.slice(1))}.</p>`;
}
function qselect(id, user) {
  if (!QBY[id]) id = (Q.find(q => q.active) || Q[0] || {}).id; if (!id) return;
  qstate = id;
  document.querySelectorAll(".qtile").forEach(t => t.setAttribute("aria-current", t.dataset.q === id));
  qrender(id);
  if (user) { try { history.replaceState(null, "", "#q-" + id); } catch (e) {} if ($("#qpanel").getBoundingClientRect().top > innerHeight * .6) $("#qpanel").scrollIntoView({behavior: "smooth", block: "start"}); }
}
let view = "outlook";
function setView(v, user) {
  view = v;
  $("#outlook-view").hidden = v !== "outlook"; $("#quant-view").hidden = v !== "quant"; $("#filters").hidden = v !== "outlook";
  document.body.classList.toggle("quant", v === "quant");
  $("#v-outlook").setAttribute("aria-selected", v === "outlook"); $("#v-quant").setAttribute("aria-selected", v === "quant");
  if (v === "quant" && !qstate) qselect(null, false);
  if (user) { try { history.replaceState(null, "", v === "quant" ? "#q-" + qstate : "#" + state.k); } catch (e) {} }
}
$("#v-outlook").addEventListener("click", () => setView("outlook", true));
$("#v-quant").addEventListener("click", () => setView("quant", true));

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
  if (view === "quant") { const ids = Q.map(q => q.id), i = ids.indexOf(qstate), j = (i + (e.key === "ArrowRight" ? 1 : -1) + ids.length) % ids.length; qselect(ids[j], true); $("#qt-" + ids[j]).focus({preventScroll: true}); return; }
  const i = KEYS.indexOf(state.k), j = (i + (e.key === "ArrowRight" ? 1 : -1) + KEYS.length) % KEYS.length;
  select(KEYS[j], true); $("#t-" + KEYS[j]).focus({preventScroll: true});
});

$("#meta").textContent = `Week of ${new Date(D.today + "T00:00:00").toLocaleDateString("en-GB", {day: "numeric", month: "long", year: "numeric"})} · COT as of ${D.asof}`;
boards(); qboards();
let start = (location.hash || "").slice(1);
if (start.startsWith("q-")) { qselect(start.slice(2), false); setView("quant", false); start = ""; }
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

"""Visual theme: "AI Aurora". Deep-space navy surfaces lit by a violet -> indigo -> cyan gradient.

Tokens (all text colours pass WCAG AA on their surfaces)
  ink-0  #070C1C  page background          ink-1 #0D1430 sidebar      ink-2 #141D3D cards
  line   #27315E  borders                  text  #E7EBF7 primary      muted #A3ACCB secondary (7.9:1 on ink-0)
  violet #8B5CF6  primary action           indigo #5B7CFA  gradient middle
  cyan   #22D3EE  data, live, "AI is listening"
  pink   #F472B6  recording / live accent (used sparingly)
  good #34D399 · warn #FBBF24 · bad #F87171
Type: Sora for headings and numbers, IBM Plex Sans for reading text.
Signature elements: the animated agent avatar and the violet-to-cyan scorecard bars.
"""
from avatar import AVATAR_CSS

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root {
  --ink-0:#070C1C; --ink-1:#0D1430; --ink-2:#141D3D; --line:#27315E;
  --text:#E7EBF7; --muted:#A3ACCB; --violet:#8B5CF6; --indigo:#5B7CFA; --volt:#22D3EE; --pink:#F472B6;
  --good:#34D399; --warn:#FBBF24; --bad:#F87171;
  --aurora: linear-gradient(90deg, #8B5CF6, #5B7CFA 55%, #22D3EE);
}
html, body, [class*="css"], .stMarkdown, p, li, label, textarea, input {
  font-family: 'IBM Plex Sans', system-ui, sans-serif;
}
h1, h2, h3, h4, .am-num { font-family: 'Sora', 'IBM Plex Sans', system-ui, sans-serif; letter-spacing: -0.01em; }
.stApp {
  background:
    radial-gradient(900px 520px at 88% -8%, rgba(139,92,246,0.16), transparent 60%),
    radial-gradient(700px 420px at -5% 105%, rgba(34,211,238,0.08), transparent 60%),
    var(--ink-0);
}
section[data-testid="stSidebar"] { background: var(--ink-1); border-right: 1px solid var(--line); }
section[data-testid="stSidebar"] .stRadio label { padding: 5px 8px; border-radius: 8px; transition: background .15s; }
section[data-testid="stSidebar"] .stRadio label:hover { background: rgba(139,92,246,0.14); }
section[data-testid="stSidebar"] .stRadio label:has(input:checked) { background: rgba(139,92,246,0.20);
  box-shadow: inset 3px 0 0 var(--violet); }
.block-container { padding-top: 2rem; max-width: 1200px; }

/* Brand + hero */
.am-brandrow { display:flex; align-items:center; gap:12px; margin: 2px 0 14px; }
.am-brand { font-family:'Sora',sans-serif; font-weight:700; font-size:1.12rem; line-height:1.15;
  background: var(--aurora); -webkit-background-clip:text; background-clip:text; color:transparent; }
.am-brand span { display:block; font-family:'IBM Plex Sans',sans-serif; font-weight:400; font-size:0.74rem;
  color:var(--muted); -webkit-text-fill-color: var(--muted); margin-top:4px; }
.am-hero { display:flex; align-items:center; gap:22px; padding: 22px 24px; margin-bottom: 18px; border-radius: 20px;
  background: linear-gradient(135deg, rgba(139,92,246,.18), rgba(34,211,238,.06)); border:1px solid var(--line); }
.am-hero h1 { margin:0 0 6px; font-size:2.1rem; background: var(--aurora); -webkit-background-clip:text;
  background-clip:text; color:transparent; }
.am-hero p { margin:0; color: var(--muted); max-width: 62ch; font-size:1.02rem; }

.am-head { margin-bottom: 1.25rem; }
.am-head h1 { font-size: 1.9rem; margin: 0 0 0.3rem 0; color: var(--text); }
.am-head p { color: var(--muted); margin: 0; max-width: 70ch; }

.am-card { background: var(--ink-2); border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; margin-bottom: 12px; }
.am-metric .am-num { font-size: 2rem; font-weight: 600; color: var(--text); }
.am-metric .am-label { color: var(--muted); font-size: 0.85rem; }
.am-metric .am-sub { color: var(--muted); font-size: 0.75rem; margin-top: 2px; }
.am-metric.empty .am-num { color: #56618F; }

/* Conversation bubbles */
.am-chat { display:flex; flex-direction:column; gap:12px; margin: 8px 0 14px; }
.am-msg { display:flex; gap:10px; align-items:flex-end; }
.am-msg.me { justify-content:flex-end; }
.am-bub { max-width: min(78ch, 82%); padding: 12px 16px; border-radius: 16px; border:1px solid var(--line);
  background: var(--ink-2); color: var(--text); font-size: 1.02rem; line-height:1.5; }
.am-msg.ai .am-bub { border-bottom-left-radius: 4px;
  background: linear-gradient(135deg, rgba(139,92,246,.16), rgba(34,211,238,.06)), var(--ink-2);
  border-color: rgba(139,92,246,.45); }
.am-msg.me .am-bub { border-bottom-right-radius: 4px; background: #182452; border-color:#2E3C78; }
.am-msg .am-who { color: var(--muted); font-size: 0.78rem; margin-bottom: 3px; letter-spacing:.01em; }
.am-me { width:40px; height:40px; border-radius:50%; display:flex; align-items:center; justify-content:center;
  font-size:22px; background:#182452; border:1px solid #2E3C78; flex:none; }
.am-time { color:#7F8AB0; font-size:0.72rem; margin-top:6px; }
.am-who { color: var(--muted); font-size: 0.82rem; margin-bottom: 4px; }
.am-question { border-left: 3px solid var(--volt); background: linear-gradient(90deg, rgba(34,211,238,0.07), transparent 70%);
  padding: 14px 18px; border-radius: 0 10px 10px 0; font-size: 1.12rem; color: var(--text); margin: 6px 0 14px 0; }

.am-callout { display:flex; gap:14px; align-items:center; padding: 14px 16px; border-radius: 14px; margin-bottom: 10px;
  border:1px solid rgba(251,191,36,.45); background: rgba(251,191,36,.07); }
.am-callout span { color: var(--muted); }

.am-chip { display:inline-block; font-size:0.75rem; padding:2px 9px; border-radius:999px; border:1px solid var(--line);
  color: var(--muted); margin: 0 6px 6px 0; }
.am-chip.violet { border-color: rgba(139,92,246,0.6); color:#C4B5FD; }
.am-chip.volt { border-color: rgba(34,211,238,0.55); color:#A5F3FC; }
.am-chip.warn { border-color: rgba(251,191,36,0.55); color:#FCD34D; }

/* Scorecard: the signature data element */
.am-score { display:grid; grid-template-columns: 210px 1fr 34px; gap: 8px 12px; align-items:center; }
.am-score .lbl { color: var(--muted); font-size: 0.86rem; }
.am-score .bar { height: 8px; background: #1C2550; border-radius: 99px; overflow: hidden; }
.am-score .bar i { display:block; height:100%; border-radius:99px; background: var(--aurora);
  animation: am-grow .7s cubic-bezier(.2,.8,.2,1) both; transform-origin: left; }
.am-score .val { font-family:'Sora',sans-serif; color: var(--text); font-size: 0.9rem; text-align:right; }
.am-score .na { color:#6E79A3; font-size:0.8rem; }
.am-total { font-family:'Sora',sans-serif; font-size: 3rem; font-weight:700; line-height:1;
  background: var(--aurora); -webkit-background-clip:text; background-clip:text; color:transparent; }
.am-total small { font-size: 1rem; color: var(--muted); -webkit-text-fill-color: var(--muted); font-weight: 500; }
@keyframes am-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }

.am-fix { border:1px solid var(--line); border-radius:10px; padding:10px 12px; margin-bottom:8px; background: rgba(20,29,61,0.6); }
.am-fix .from { color:#FCA5A5; text-decoration: line-through; text-decoration-color: rgba(248,113,113,0.5); }
.am-fix .to { color:#86EFAC; }
.am-fix .why { color: var(--muted); font-size: 0.85rem; margin-top: 4px; }

.am-phase { border:1px solid var(--line); border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; background: var(--ink-2); }
.am-phase.now { border-color: var(--violet); box-shadow: 0 0 0 1px rgba(139,92,246,0.35) inset; }
.am-phase h4 { margin: 0 0 4px 0; color: var(--text); }
.am-phase .days { color: var(--volt); font-size: 0.8rem; }

.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"],
.stFormSubmitButton > button[kind="primary"] {
  background: linear-gradient(90deg, var(--violet), var(--indigo)); border: none; font-weight: 600; }
.stButton > button[kind="primary"]:hover { filter: brightness(1.08); }
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button { border-radius: 10px; }
[data-testid="stMetricValue"] { font-family:'Sora',sans-serif; }
textarea { font-size: 1rem !important; }
:focus-visible { outline: 2px solid var(--volt) !important; outline-offset: 2px; }
@media (max-width: 700px) {
  .am-score { grid-template-columns: 1fr 34px; }
  .am-score .bar { grid-column: 1 / span 2; }
  .am-head h1 { font-size: 1.5rem; }
  .am-hero { flex-direction: column; text-align:center; }
  .am-bub { max-width: 100%; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
""" + AVATAR_CSS + """
</style>
"""

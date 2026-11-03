"""Visual theme: dark navy surfaces, purple and electric-blue accents.

Tokens
  ink-0  #070C1C  page background (deep navy, not grey-black)
  ink-1  #0E1530  sidebar / raised surface
  ink-2  #151E40  cards
  line   #26305C  borders
  text   #E7EBF7  primary text,  muted #9AA3C2
  violet #8B5CF6  primary accent (actions, progress)
  volt   #2EC5FF  electric blue (data, highlights)
Type: Sora for headings and numbers, IBM Plex Sans for reading text.
The one bold element is the scorecard: a violet-to-blue bar per category.
"""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root {
  --ink-0:#070C1C; --ink-1:#0E1530; --ink-2:#151E40; --line:#26305C;
  --text:#E7EBF7; --muted:#9AA3C2; --violet:#8B5CF6; --volt:#2EC5FF;
  --good:#34D399; --warn:#FBBF24; --bad:#F87171;
}
html, body, [class*="css"], .stMarkdown, p, li, label, textarea, input {
  font-family: 'IBM Plex Sans', system-ui, sans-serif;
}
h1, h2, h3, h4, .am-num { font-family: 'Sora', 'IBM Plex Sans', system-ui, sans-serif; letter-spacing: -0.01em; }
.stApp { background: radial-gradient(1200px 600px at 85% -10%, rgba(139,92,246,0.10), transparent 60%), var(--ink-0); }
section[data-testid="stSidebar"] { background: var(--ink-1); border-right: 1px solid var(--line); }
section[data-testid="stSidebar"] .stRadio label { padding: 4px 6px; border-radius: 6px; }
section[data-testid="stSidebar"] .stRadio label:hover { background: rgba(139,92,246,0.12); }
.block-container { padding-top: 2rem; max-width: 1200px; }

.am-brand { font-family:'Sora',sans-serif; font-weight:700; font-size:1.25rem; color:var(--text); line-height:1.15; }
.am-brand span { display:block; font-family:'IBM Plex Sans',sans-serif; font-weight:400; font-size:0.78rem; color:var(--muted); margin-top:6px; }

.am-head { margin-bottom: 1.25rem; }
.am-head h1 { font-size: 1.9rem; margin: 0 0 0.3rem 0; color: var(--text); }
.am-head p { color: var(--muted); margin: 0; max-width: 70ch; }

.am-card { background: var(--ink-2); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px; margin-bottom: 12px; }
.am-metric .am-num { font-size: 2rem; font-weight: 600; color: var(--text); }
.am-metric .am-label { color: var(--muted); font-size: 0.85rem; }
.am-metric .am-sub { color: var(--muted); font-size: 0.75rem; margin-top: 2px; }
.am-metric.empty .am-num { color: #4A5585; }

.am-question { border-left: 3px solid var(--volt); background: linear-gradient(90deg, rgba(46,197,255,0.07), transparent 70%);
  padding: 14px 18px; border-radius: 0 10px 10px 0; font-size: 1.12rem; color: var(--text); margin: 6px 0 14px 0; }
.am-who { color: var(--muted); font-size: 0.82rem; margin-bottom: 4px; }

.am-chip { display:inline-block; font-size:0.75rem; padding:2px 9px; border-radius:999px; border:1px solid var(--line);
  color: var(--muted); margin: 0 6px 6px 0; }
.am-chip.violet { border-color: rgba(139,92,246,0.6); color:#C4B5FD; }
.am-chip.volt { border-color: rgba(46,197,255,0.55); color:#9BE3FF; }
.am-chip.warn { border-color: rgba(251,191,36,0.55); color:#FCD34D; }

/* Scorecard: the signature element */
.am-score { display:grid; grid-template-columns: 210px 1fr 34px; gap: 8px 12px; align-items:center; }
.am-score .lbl { color: var(--muted); font-size: 0.86rem; }
.am-score .bar { height: 8px; background: #1C2550; border-radius: 99px; overflow: hidden; }
.am-score .bar i { display:block; height:100%; border-radius:99px; background: linear-gradient(90deg, var(--violet), var(--volt)); }
.am-score .val { font-family:'Sora',sans-serif; color: var(--text); font-size: 0.9rem; text-align:right; }
.am-score .na { color:#4A5585; font-size:0.8rem; }
.am-total { font-family:'Sora',sans-serif; font-size: 3rem; font-weight:700; color: var(--text); line-height:1; }
.am-total small { font-size: 1rem; color: var(--muted); font-weight: 500; }

.am-fix { border:1px solid var(--line); border-radius:10px; padding:10px 12px; margin-bottom:8px; background: rgba(21,30,64,0.6); }
.am-fix .from { color:#FCA5A5; text-decoration: line-through; text-decoration-color: rgba(248,113,113,0.5); }
.am-fix .to { color:#86EFAC; }
.am-fix .why { color: var(--muted); font-size: 0.85rem; margin-top: 4px; }

.am-phase { border:1px solid var(--line); border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; background: var(--ink-2); }
.am-phase.now { border-color: var(--violet); box-shadow: 0 0 0 1px rgba(139,92,246,0.35) inset; }
.am-phase h4 { margin: 0 0 4px 0; color: var(--text); }
.am-phase .days { color: var(--volt); font-size: 0.8rem; }

.stButton > button[kind="primary"] { background: linear-gradient(90deg, var(--violet), #6D5BF0); border: none; }
.stButton > button { border-radius: 8px; }
textarea { font-size: 1rem !important; }
:focus-visible { outline: 2px solid var(--volt) !important; outline-offset: 2px; }
@media (max-width: 700px) {
  .am-score { grid-template-columns: 1fr 34px; }
  .am-score .bar { grid-column: 1 / span 2; }
  .am-head h1 { font-size: 1.5rem; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
</style>
"""

"""The AI agent's face: an animated SVG logo/avatar ("Mentor").

One drawing is reused everywhere (sidebar logo, chat bubbles, the voice player
and the video-call stage). Motion comes from CSS classes, so the same SVG can
be idle (float + blink), speaking (mouth + sound rings), listening (ear waves)
or thinking (orbiting dots). Everything is inline: no image files, no CDN.
All motion is switched off for people who ask for reduced motion.
"""
from __future__ import annotations

import html
import itertools

_ids = itertools.count(1)

AVATAR_CSS = """
.am-av { display:inline-block; position:relative; line-height:0; }
.am-av svg { overflow:visible; }
.am-av .float { animation: am-float 5s ease-in-out infinite; transform-origin:50% 50%; }
.am-av .eye { animation: am-blink 4.8s infinite; transform-origin: 50% 50%; transform-box: fill-box; }
.am-av .halo { animation: am-spin 14s linear infinite; transform-origin:50% 50%; transform-box: fill-box; }
.am-av .core { animation: am-glow 3.2s ease-in-out infinite; }
.am-av .mouth rect { transform-origin: 50% 50%; transform-box: fill-box; transform: scaleY(.25); }
.am-av .ring { opacity:0; transform-origin:50% 50%; transform-box: fill-box; }
.am-av .wave { opacity:0; }
.am-av .dots circle { opacity:0; }

.am-av.speaking .mouth rect { animation: am-talk .42s ease-in-out infinite alternate; }
.am-av.speaking .mouth rect:nth-child(2) { animation-duration:.31s; animation-delay:-.1s; }
.am-av.speaking .mouth rect:nth-child(3) { animation-duration:.37s; animation-delay:-.2s; }
.am-av.speaking .mouth rect:nth-child(4) { animation-duration:.28s; animation-delay:-.05s; }
.am-av.speaking .mouth rect:nth-child(5) { animation-duration:.45s; animation-delay:-.15s; }
.am-av.speaking .ring { animation: am-ring 1.8s ease-out infinite; }
.am-av.speaking .ring.r2 { animation-delay:.6s; } .am-av.speaking .ring.r3 { animation-delay:1.2s; }
.am-av.listening .wave { animation: am-wave 1.3s ease-in-out infinite; }
.am-av.listening .wave.w2 { animation-delay:.25s; }
.am-av.listening .eye { animation: none; }
.am-av.thinking .dots circle { animation: am-dot 1.2s ease-in-out infinite; }
.am-av.thinking .dots circle:nth-child(2) { animation-delay:.2s; }
.am-av.thinking .dots circle:nth-child(3) { animation-delay:.4s; }
.am-av.thinking .halo { animation-duration: 3s; }

@keyframes am-float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
@keyframes am-blink { 0%,92%,100% { transform: scaleY(1); } 95% { transform: scaleY(.1); } }
@keyframes am-spin { to { transform: rotate(360deg); } }
@keyframes am-glow { 0%,100% { opacity:.55; } 50% { opacity:.95; } }
@keyframes am-talk { from { transform: scaleY(.25); } to { transform: scaleY(1); } }
@keyframes am-ring { 0% { opacity:.7; transform: scale(.82); } 100% { opacity:0; transform: scale(1.28); } }
@keyframes am-wave { 0%,100% { opacity:.15; } 50% { opacity:.9; } }
@keyframes am-dot { 0%,100% { opacity:.2; transform: translateY(0); } 50% { opacity:1; transform: translateY(-3px); } }
@media (prefers-reduced-motion: reduce) { .am-av * { animation: none !important; } }
"""


def avatar_svg(size: int = 64, state: str = "idle", title: str = "AI Mentor") -> str:
    """Inline SVG of the agent. state: idle | speaking | listening | thinking."""
    n = next(_ids)
    g, c, v = f"amg{n}", f"amc{n}", f"amv{n}"
    state = state if state in {"idle", "speaking", "listening", "thinking"} else "idle"
    return f"""<span class="am-av {state}" role="img" aria-label="{html.escape(title)} ({state})" style="width:{size}px;height:{size}px">
<svg viewBox="0 0 120 120" width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">
 <defs>
  <linearGradient id="{g}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8B5CF6"/><stop offset=".55" stop-color="#5B7CFA"/><stop offset="1" stop-color="#22D3EE"/></linearGradient>
  <radialGradient id="{c}" cx=".5" cy=".42" r=".6"><stop offset="0" stop-color="#1E2A5A"/><stop offset="1" stop-color="#0B1230"/></radialGradient>
  <linearGradient id="{v}" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#22D3EE"/><stop offset="1" stop-color="#A78BFA"/></linearGradient>
 </defs>
 <circle class="ring r1" cx="60" cy="60" r="54" fill="none" stroke="#22D3EE" stroke-width="2"/>
 <circle class="ring r2" cx="60" cy="60" r="54" fill="none" stroke="#8B5CF6" stroke-width="2"/>
 <circle class="ring r3" cx="60" cy="60" r="54" fill="none" stroke="#F472B6" stroke-width="1.5"/>
 <g class="halo"><circle cx="60" cy="60" r="55" fill="none" stroke="url(#{g})" stroke-width="2" stroke-dasharray="6 10" opacity=".55"/></g>
 <g class="float">
  <path class="wave" d="M12 52 q-6 8 0 16" stroke="#22D3EE" stroke-width="3" fill="none" stroke-linecap="round"/>
  <path class="wave w2" d="M5 46 q-9 14 0 28" stroke="#22D3EE" stroke-width="2.5" fill="none" stroke-linecap="round"/>
  <path class="wave" d="M108 52 q6 8 0 16" stroke="#22D3EE" stroke-width="3" fill="none" stroke-linecap="round"/>
  <path class="wave w2" d="M115 46 q9 14 0 28" stroke="#22D3EE" stroke-width="2.5" fill="none" stroke-linecap="round"/>
  <line x1="60" y1="20" x2="60" y2="11" stroke="url(#{g})" stroke-width="3" stroke-linecap="round"/>
  <circle class="core" cx="60" cy="9" r="4.5" fill="#22D3EE"/>
  <rect x="22" y="20" width="76" height="76" rx="30" fill="url(#{c})" stroke="url(#{g})" stroke-width="3.5"/>
  <rect x="16" y="50" width="9" height="20" rx="4.5" fill="url(#{g})"/>
  <rect x="95" y="50" width="9" height="20" rx="4.5" fill="url(#{g})"/>
  <path d="M100 70 q2 18 -18 21" stroke="url(#{g})" stroke-width="3" fill="none" stroke-linecap="round"/>
  <circle cx="80" cy="91" r="3.5" fill="#F472B6"/>
  <rect x="32" y="40" width="56" height="24" rx="12" fill="#070C1C" stroke="url(#{v})" stroke-width="1.5" opacity=".95"/>
  <ellipse class="eye" cx="47" cy="52" rx="5" ry="5.5" fill="#22D3EE"/>
  <ellipse class="eye" cx="73" cy="52" rx="5" ry="5.5" fill="#A78BFA"/>
  <circle cx="48.6" cy="50.2" r="1.5" fill="#E7F9FF"/><circle cx="74.6" cy="50.2" r="1.5" fill="#F3EEFF"/>
  <g class="mouth" fill="url(#{v})">
   <rect x="47" y="72" width="3.4" height="10" rx="1.7"/><rect x="52.6" y="70" width="3.4" height="14" rx="1.7"/>
   <rect x="58.3" y="68" width="3.4" height="18" rx="1.7"/><rect x="64" y="70" width="3.4" height="14" rx="1.7"/>
   <rect x="69.6" y="72" width="3.4" height="10" rx="1.7"/>
  </g>
  <g class="dots" fill="#E7EBF7"><circle cx="50" cy="104" r="2.6"/><circle cx="60" cy="104" r="2.6"/><circle cx="70" cy="104" r="2.6"/></g>
 </g>
</svg></span>"""


def brand_html() -> str:
    return (f'<div class="am-brandrow">{avatar_svg(46, "idle", "AI Career Mentor logo")}'
            '<div class="am-brand">AI Career Mentor<span>Interviewer · Coach · Career partner</span></div></div>')


def bubble(text: str, who: str, role: str = "assistant", state: str = "idle", meta: str = "") -> str:
    """One chat message. `text` is escaped; `meta` must already be safe HTML."""
    body = html.escape(text or "").replace("\n", "<br>")
    if role == "assistant":
        return (f'<div class="am-msg ai">{avatar_svg(44, state, who)}<div class="am-bub">'
                f'<div class="am-who">{html.escape(who)}</div><div class="am-text">{body}</div>{meta}</div></div>')
    return (f'<div class="am-msg me"><div class="am-bub"><div class="am-who">{html.escape(who)}</div>'
            f'<div class="am-text">{body}</div>{meta}</div><div class="am-me">🧑‍💼</div></div>')

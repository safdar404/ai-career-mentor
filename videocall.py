"""🎥 Live audio / video conversation stage.

A two-tile "video call": the animated AI interviewer on the left (it speaks each
question with the browser's voice and moves its mouth while talking) and the
learner's own camera on the right, with a live microphone meter.

Answers are captured with the browser's speech recognition (Chrome / Edge,
free, no key) and sent back to Python together with an optional webcam frame
for presence coaching. Nothing is uploaded until the learner presses Send, the
frame is only used for one feedback call and is never stored.

Built on st.components.v2 (runs in the page, so camera and microphone work).
"""
from __future__ import annotations

import base64
import binascii

import streamlit as st

from avatar import AVATAR_CSS, avatar_svg
from voice import ACCENT_LANG

_CSS = AVATAR_CSS + """
:host { display:block; }
.vc { font-family:'IBM Plex Sans', system-ui, sans-serif; color:#E7EBF7; }
.vc-grid { display:grid; grid-template-columns: 1fr 1fr; gap:12px; }
.tile { position:relative; border-radius:16px; overflow:hidden; min-height:250px; border:1px solid #2A3566;
  background: radial-gradient(420px 260px at 50% 35%, rgba(139,92,246,.22), transparent 70%), #0B1230; }
.tile.ai { display:flex; flex-direction:column; align-items:center; justify-content:center; padding:18px 14px 52px; }
.tile.ai.speaking { border-color:#8B5CF6; box-shadow: 0 0 0 1px rgba(139,92,246,.5), 0 0 28px rgba(139,92,246,.25); }
.tile.me.live { border-color:#22D3EE; box-shadow: 0 0 0 1px rgba(34,211,238,.5), 0 0 28px rgba(34,211,238,.18); }
.tile video { width:100%; height:100%; min-height:250px; object-fit:cover; transform: scaleX(-1); display:block; background:#070C1C; }
.camoff { position:absolute; inset:0; display:flex; flex-direction:column; gap:8px; align-items:center; justify-content:center;
  color:#A3ACCB; font-size:14px; text-align:center; padding:16px; }
.camoff .big { font-size:42px; }
.name { position:absolute; left:10px; bottom:10px; background:rgba(7,12,28,.72); backdrop-filter: blur(6px);
  padding:4px 10px; border-radius:999px; font-size:12.5px; border:1px solid #2A3566; }
.pill { position:absolute; right:10px; top:10px; font-size:12px; padding:3px 10px; border-radius:999px;
  background:rgba(7,12,28,.72); border:1px solid #2A3566; color:#C9D1EA; }
.pill.rec { border-color:#F472B6; color:#FBCFE8; }
.pill.rec::before { content:''; display:inline-block; width:8px; height:8px; border-radius:50%; background:#F43F5E;
  margin-right:6px; animation: vc-blink 1s infinite; vertical-align:middle; }
.clock { position:absolute; left:10px; top:10px; font-size:12px; color:#A3ACCB; font-variant-numeric: tabular-nums; }
.meter { position:absolute; right:10px; bottom:12px; width:90px; height:6px; border-radius:99px; background:#1C2550; overflow:hidden; }
.meter i { display:block; height:100%; width:0%; background:linear-gradient(90deg,#22D3EE,#A78BFA,#F472B6); transition: width .08s; }
.caption { margin-top:12px; max-width:44ch; text-align:center; font-size:15px; line-height:1.45; color:#E7EBF7; }
.status { margin-top:6px; font-size:12.5px; color:#A3ACCB; min-height:1em; }
.bar { display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin:12px 0 8px; }
button { font: inherit; font-size:14px; border-radius:999px; padding:8px 16px; cursor:pointer; color:#E7EBF7;
  background:#18224A; border:1px solid #33407A; transition: background .15s, border-color .15s, transform .05s; }
button:hover { background:#222E62; border-color:#8B5CF6; }
button:active { transform: translateY(1px); }
button:focus-visible { outline:2px solid #22D3EE; outline-offset:2px; }
button.primary { background: linear-gradient(90deg,#8B5CF6,#5B7CFA); border:none; font-weight:600; }
button.danger { border-color:#F472B6; }
button[disabled] { opacity:.45; cursor:not-allowed; }
textarea { width:100%; box-sizing:border-box; min-height:96px; resize:vertical; border-radius:12px; padding:10px 12px;
  background:#0B1230; color:#E7EBF7; border:1px solid #2A3566; font: inherit; font-size:15px; line-height:1.5; }
textarea:focus { outline:none; border-color:#8B5CF6; }
.hint { font-size:12px; color:#A3ACCB; margin-top:6px; }
.interim { color:#7F8AB0; font-style:italic; }
@keyframes vc-blink { 50% { opacity:.2; } }
@media (max-width: 720px) { .vc-grid { grid-template-columns: 1fr; } .tile, .tile video { min-height:200px; } }
@media (prefers-reduced-motion: reduce) { * { animation:none !important; transition:none !important; } }
"""

_HTML = f"""
<div class="vc">
  <div class="vc-grid">
    <div class="tile ai" id="aiTile">
      <span class="clock" id="clock">00:00</span>
      <span class="pill" id="aiPill">🤖 AI interviewer</span>
      {avatar_svg(150, "idle", "AI interviewer")}
      <div class="caption" id="caption" aria-live="polite"></div>
      <div class="status" id="status"></div>
      <span class="name" id="aiName">Mentor</span>
    </div>
    <div class="tile me" id="meTile">
      <video id="self" autoplay playsinline muted></video>
      <div class="camoff" id="camoff"><div class="big">🎙️</div><div id="camoffText">Audio call. Your camera is off.</div></div>
      <span class="pill" id="mePill">You</span>
      <div class="meter" aria-hidden="true"><i id="level"></i></div>
      <span class="name">🧑‍💼 You</span>
    </div>
  </div>
  <div class="bar">
    <button id="cam" aria-label="Turn camera on or off">📷 Camera</button>
    <button id="repeat" aria-label="Repeat the question">🔁 Repeat question</button>
    <button id="talk" class="primary" aria-label="Start or stop answering by voice">🎙️ Start answering</button>
    <button id="snap" aria-label="Get feedback on how you look on camera">📸 Presence check</button>
  </div>
  <textarea id="answer" aria-label="Your answer (live transcript, editable)"
    placeholder="Press 🎙️ Start answering and speak. Your words appear here and you can edit them before sending."></textarea>
  <div class="hint" id="interim"></div>
  <div class="bar">
    <button id="clear" aria-label="Clear the answer">🧹 Clear</button>
    <button id="send" class="primary" aria-label="Send your answer">✅ Send answer</button>
  </div>
  <div class="hint" id="note"></div>
</div>
"""

_JS = r"""
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const $ = (id) => parentElement.querySelector('#' + id);
  const S = parentElement.__vc || (parentElement.__vc = { listening:false, finalText:'', lastQid:null,
      started: Date.now(), rec:null, silence:null, sent:false });
  const G = window.__amVC || (window.__amVC = { stream:null, ctx:null, videos:new Set(), raf:null });
  const d = data || {};
  const av = parentElement.querySelector('.am-av');
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  const setAv = (s) => { if (av) av.setAttribute('class', 'am-av ' + s); $('aiTile').classList.toggle('speaking', s === 'speaking'); };
  const status = (t) => { $('status').textContent = t; };
  const note = (t) => { $('note').textContent = t; };

  // ---------- question
  $('caption').textContent = d.question || '';
  $('aiName').textContent = d.who || 'Mentor';
  if (!SR) note('🛈 Live voice typing needs Chrome or Edge. You can still type your answer here, or use the recorder below.');

  // ---------- clock
  if (!S.clockTimer) S.clockTimer = setInterval(() => {
    const s = Math.floor((Date.now() - S.started) / 1000);
    const el = $('clock'); if (el) el.textContent = String(Math.floor(s/60)).padStart(2,'0') + ':' + String(s%60).padStart(2,'0');
  }, 1000);

  // ---------- speaking
  function speak(text, then) {
    if (!('speechSynthesis' in window) || !text) { then && then(); return; }
    stopListening();
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = d.lang || 'en-GB'; u.rate = d.rate || 0.97;
    const voices = window.speechSynthesis.getVoices();
    const v = voices.find(x => x.lang === u.lang) || voices.find(x => x.lang && x.lang.startsWith(u.lang.slice(0,2)));
    if (v) u.voice = v;
    u.onstart = () => { setAv('speaking'); status('🔊 Speaking…'); };
    u.onend = u.onerror = () => { setAv('idle'); status('Your turn'); then && then(); };
    window.speechSynthesis.speak(u);
  }

  // ---------- camera + mic meter
  function attach() {
    const vid = $('self');
    G.videos.add(vid);
    const hasVideo = G.stream && G.stream.getVideoTracks().some(t => t.readyState === 'live' && t.enabled);
    if (hasVideo) { vid.srcObject = G.stream; $('camoff').style.display = 'none'; }
    else { vid.srcObject = null; $('camoff').style.display = 'flex'; }
    $('cam').textContent = hasVideo ? '📷 Camera off' : '📷 Camera on';
    $('snap').disabled = !hasVideo;
  }
  function meter() {
    if (!G.stream || !G.stream.getAudioTracks().length) return;
    try {
      G.ctx = G.ctx || new (window.AudioContext || window.webkitAudioContext)();
      const src = G.ctx.createMediaStreamSource(G.stream);
      const an = G.ctx.createAnalyser(); an.fftSize = 512; src.connect(an);
      const buf = new Uint8Array(an.fftSize);
      cancelAnimationFrame(G.raf);
      const tick = () => {
        an.getByteTimeDomainData(buf);
        let peak = 0; for (const x of buf) peak = Math.max(peak, Math.abs(x - 128));
        const lvl = parentElement.querySelector('#level'); if (lvl) lvl.style.width = Math.min(100, peak * 1.6) + '%';
        G.raf = requestAnimationFrame(tick);
      };
      tick();
    } catch (e) { /* meter is decorative */ }
  }
  async function cameraOn(withVideo) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { note('Camera and microphone need HTTPS and a modern browser.'); return; }
    try {
      if (G.stream) G.stream.getTracks().forEach(t => t.stop());
      G.stream = await navigator.mediaDevices.getUserMedia({ audio: true,
        video: withVideo ? { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' } : false });
      attach(); meter();
    } catch (e) {
      note(withVideo ? '🚫 Camera blocked. Allow camera access in the address bar, or continue as an audio call.'
                     : '🚫 Microphone blocked. Allow microphone access in the address bar.');
      attach();
    }
  }
  function cameraOff() {
    if (G.stream) G.stream.getVideoTracks().forEach(t => t.stop());
    attach();
  }
  // stop the camera when this stage leaves the page
  if (!G.watch) G.watch = setInterval(() => {
    for (const v of [...G.videos]) if (!v.isConnected) G.videos.delete(v);
    if (!G.videos.size && G.stream) { G.stream.getTracks().forEach(t => t.stop()); G.stream = null; cancelAnimationFrame(G.raf); }
  }, 2500);

  // ---------- listening
  function startListening() {
    if (!SR) { $('answer').focus(); return; }
    if (S.listening) return;
    window.speechSynthesis && window.speechSynthesis.cancel();
    S.finalText = $('answer').value ? $('answer').value.trim() + ' ' : '';
    const rec = new SR();
    rec.lang = d.lang || 'en-GB'; rec.continuous = true; rec.interimResults = true;
    rec.onresult = (ev) => {
      let interim = '';
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        if (r.isFinal) S.finalText += r[0].transcript.trim() + ' ';
        else interim += r[0].transcript;
      }
      $('answer').value = S.finalText;
      $('interim').innerHTML = '';
      if (interim) { const s = document.createElement('span'); s.className = 'interim'; s.textContent = '… ' + interim; $('interim').appendChild(s); }
      clearTimeout(S.silence);
      if (d.handsFree) S.silence = setTimeout(() => { if (S.listening && $('answer').value.trim()) send(); }, (d.silenceMs || 3500));
    };
    rec.onerror = (e) => { if (e.error === 'not-allowed') { note('🚫 Microphone blocked for voice typing.'); stopListening(); } };
    rec.onend = () => { if (S.listening) { try { rec.start(); } catch (e) {} } };
    S.rec = rec; S.listening = true;
    try { rec.start(); } catch (e) {}
    setAv('listening'); status('👂 Listening… speak naturally');
    $('talk').textContent = '⏹ Stop'; $('mePill').textContent = 'Recording'; $('mePill').classList.add('rec');
    $('meTile').classList.add('live');
  }
  function stopListening() {
    S.listening = false; clearTimeout(S.silence);
    if (S.rec) { try { S.rec.stop(); } catch (e) {} S.rec = null; }
    setAv('idle'); $('interim').textContent = '';
    $('talk').textContent = '🎙️ Start answering'; $('mePill').textContent = 'You'; $('mePill').classList.remove('rec');
    $('meTile').classList.remove('live');
  }

  // ---------- snapshot + send
  function snapshot() {
    const v = $('self');
    if (!v.srcObject || !v.videoWidth) return null;
    const c = document.createElement('canvas'); c.width = 480; c.height = Math.round(480 * v.videoHeight / v.videoWidth);
    c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
    return c.toDataURL('image/jpeg', 0.72);
  }
  function send() {
    const text = $('answer').value.trim();
    if (!text) { note('Say or type an answer first.'); return; }
    stopListening();
    setAv('thinking'); status('⏳ Your coaches are reviewing…');
    $('send').disabled = true;
    setTriggerValue('answer', { qid: d.qid, text, image: d.presence ? snapshot() : null });
  }

  // ---------- wire buttons (re-bound on every render, so always current)
  $('cam').onclick = () => { const on = G.stream && G.stream.getVideoTracks().some(t => t.readyState === 'live'); on ? cameraOff() : cameraOn(true); };
  $('repeat').onclick = () => speak(d.question);
  $('talk').onclick = () => S.listening ? stopListening() : startListening();
  $('clear').onclick = () => { $('answer').value = ''; S.finalText = ''; };
  $('send').onclick = send;
  $('snap').onclick = () => { const img = snapshot(); if (img) { setAv('thinking'); status('📸 Checking your on-camera presence…'); setTriggerValue('presence', { qid: d.qid, image: img }); } };

  // ---------- new question arrives
  if (S.lastQid !== d.qid) {
    S.lastQid = d.qid; S.sent = false;
    $('answer').value = ''; S.finalText = ''; $('send').disabled = false;
    if (!G.stream) cameraOn(!!d.camera); else attach();
    const next = d.handsFree ? startListening : null;
    if (d.autoplay !== false) {
      if (window.speechSynthesis && window.speechSynthesis.getVoices().length === 0) {
        window.speechSynthesis.onvoiceschanged = () => { window.speechSynthesis.onvoiceschanged = null; speak(d.question, next); };
        setTimeout(() => { if (!S.listening && $('status').textContent === '') speak(d.question, next); }, 900);
      } else speak(d.question, next);
    } else status('Your turn');
  } else {
    attach();
    $('send').disabled = false;
    if (!S.listening) setAv('idle');
  }

  return () => { if (S.rec) { S.listening = false; try { S.rec.stop(); } catch (e) {} } };
}
"""

_stage = st.components.v2.component("am_video_stage", html=_HTML, css=_CSS, js=_JS)


def decode_image(data_url: str | None) -> bytes | None:
    """Turn the stage's JPEG data URL into bytes, rejecting anything that is not a small JPEG/PNG."""
    if not data_url or not isinstance(data_url, str):
        return None
    head, _, b64 = data_url.partition(",")
    if head not in {"data:image/jpeg;base64", "data:image/png;base64"} or len(b64) > 6_000_000:
        return None
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        return None
    return raw if raw[:3] == b"\xff\xd8\xff" or raw[:8] == b"\x89PNG\r\n\x1a\n" else None


def stage(qid: int, question: str, who: str, accent: str, *, camera: bool, presence: bool, hands_free: bool,
          autoplay: bool, key: str):
    """Mount the call stage. Returns the component result (.answer / .presence trigger values)."""
    return _stage(key=key, data={"qid": qid, "question": question, "who": who, "lang": ACCENT_LANG.get(accent, "en-GB"),
                                 "camera": camera, "presence": presence, "handsFree": hands_free,
                                 "autoplay": autoplay, "rate": 0.97},
                  on_answer_change=lambda: None, on_presence_change=lambda: None)

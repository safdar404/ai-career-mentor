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
from robot3d import ROBOT_LIB
from voice import ACCENT_LANG

_CSS = AVATAR_CSS + """
:host { display:block; }
.vc { font-family:'IBM Plex Sans', system-ui, sans-serif; color:#E7EBF7; }
.vc-grid { display:grid; grid-template-columns: 1.25fr 1fr; gap:16px; perspective: 1400px; padding: 6px 4px 10px; }
.tile { position:relative; border-radius:22px; overflow:hidden; min-height:380px; transform-style: preserve-3d;
  border:1px solid rgba(139,92,246,.35);
  background: radial-gradient(70% 60% at 50% 35%, rgba(91,124,250,.28), transparent 70%),
              radial-gradient(50% 40% at 85% 100%, rgba(244,114,182,.14), transparent 70%), #070C1C;
  box-shadow: 0 40px 70px -30px rgba(0,0,0,.85), 0 0 0 1px rgba(255,255,255,.03) inset, 0 1px 0 rgba(255,255,255,.08) inset;
  transition: transform .6s cubic-bezier(.2,.8,.2,1), box-shadow .3s, border-color .3s; }
.tile.ai { transform: rotateY(5deg) translateZ(0); }
.tile.me { transform: rotateY(-5deg) translateZ(0); }
.tile:hover { transform: rotateY(0) translateZ(12px); }
.tile.ai.speaking { border-color:#8B5CF6; box-shadow: 0 40px 70px -30px rgba(0,0,0,.85), 0 0 0 1px rgba(139,92,246,.55), 0 0 46px rgba(139,92,246,.35); }
.tile.ai.listening { border-color:#2DD4BF; box-shadow: 0 40px 70px -30px rgba(0,0,0,.85), 0 0 0 1px rgba(45,212,191,.5), 0 0 40px rgba(45,212,191,.25); }
.tile.me.live { border-color:#22D3EE; box-shadow: 0 40px 70px -30px rgba(0,0,0,.85), 0 0 0 1px rgba(34,211,238,.5), 0 0 40px rgba(34,211,238,.22); }
.stage3d { position:absolute; inset:0; }
.stage3d canvas { position:absolute; inset:0; width:100%; height:100%; display:block; opacity:0; transition: opacity .8s; }
.stage3d.ready canvas { opacity:1; }
.stage3d .fallback { position:absolute; inset:0 0 110px; display:flex; align-items:center; justify-content:center; transition: opacity .5s; }
.stage3d.ready .fallback { opacity:0; pointer-events:none; }
.scan { position:absolute; inset:0; pointer-events:none; opacity:.45;
  background: repeating-linear-gradient(0deg, rgba(255,255,255,.025) 0 1px, transparent 1px 3px); }
.sweep { position:absolute; left:0; right:0; height:70px; top:-70px; pointer-events:none; opacity:0;
  background: linear-gradient(180deg, transparent, rgba(34,211,238,.10), transparent); }
.tile.ai.thinking .sweep { opacity:1; animation: vc-sweep 1.8s linear infinite; }
.hud { position:absolute; width:18px; height:18px; border-color: rgba(34,211,238,.7); border-style: solid; pointer-events:none; }
.hud.tl { top:10px; left:10px; border-width:2px 0 0 2px; border-radius:6px 0 0 0; }
.hud.tr { top:10px; right:10px; border-width:2px 2px 0 0; border-radius:0 6px 0 0; }
.hud.bl { bottom:10px; left:10px; border-width:0 0 2px 2px; border-radius:0 0 0 6px; }
.hud.br { bottom:10px; right:10px; border-width:0 2px 2px 0; border-radius:0 0 6px 0; }
.glass { position:absolute; left:14px; right:14px; bottom:14px; padding:12px 16px 10px; border-radius:16px;
  background: linear-gradient(180deg, rgba(20,29,61,.55), rgba(7,12,28,.78)); backdrop-filter: blur(10px) saturate(1.3);
  -webkit-backdrop-filter: blur(10px) saturate(1.3); border:1px solid rgba(255,255,255,.08); }
.tile video { width:100%; height:100%; min-height:380px; object-fit:cover; transform: scaleX(-1); display:block; background:#070C1C; }
.camoff { position:absolute; inset:0; display:flex; flex-direction:column; gap:8px; align-items:center; justify-content:center;
  color:#A3ACCB; font-size:14px; text-align:center; padding:16px; }
.camoff .big { font-size:46px; filter: drop-shadow(0 0 18px rgba(34,211,238,.45)); }
.name { position:absolute; left:16px; top:14px; background:rgba(7,12,28,.6); backdrop-filter: blur(6px);
  padding:4px 11px; border-radius:999px; font-size:12px; border:1px solid rgba(255,255,255,.1); letter-spacing:.02em; }
.tile.me .name { top:auto; bottom:16px; }
.pill { position:absolute; right:16px; top:14px; font-size:12px; padding:4px 11px; border-radius:999px;
  background:rgba(7,12,28,.6); border:1px solid rgba(255,255,255,.1); color:#C9D1EA; backdrop-filter: blur(6px); }
.pill.rec { border-color:#F472B6; color:#FBCFE8; }
.pill.rec::before, .live-dot::before { content:''; display:inline-block; width:8px; height:8px; border-radius:50%; background:#F43F5E;
  margin-right:6px; animation: vc-blink 1s infinite; vertical-align:middle; }
.clock { position:absolute; right:18px; top:46px; font-size:11.5px; color:#A3ACCB;
  font-variant-numeric: tabular-nums; letter-spacing:.12em; text-transform:uppercase; }
.meter { position:absolute; right:16px; bottom:22px; width:110px; height:6px; border-radius:99px; background:rgba(28,37,80,.8); overflow:hidden; }
.meter i { display:block; height:100%; width:0%; background:linear-gradient(90deg,#22D3EE,#A78BFA,#F472B6); transition: width .08s; }
.caption { max-width:60ch; margin:0 auto; text-align:center; font-size:15.5px; line-height:1.45; color:#F1F4FF; }
.status { margin-top:6px; text-align:center; font-size:11.5px; color:#9BE7FF; min-height:1em; letter-spacing:.08em; text-transform:uppercase; }
.bar { display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin:14px 0 8px; }
button { font: inherit; font-size:14px; border-radius:999px; padding:9px 17px; cursor:pointer; color:#E7EBF7;
  background: linear-gradient(180deg, #1B2654, #141D40); border:1px solid #33407A;
  box-shadow: 0 6px 16px -8px rgba(0,0,0,.8), 0 1px 0 rgba(255,255,255,.06) inset;
  transition: background .15s, border-color .15s, transform .08s, box-shadow .2s; }
button:hover { border-color:#8B5CF6; box-shadow: 0 8px 22px -8px rgba(139,92,246,.6), 0 1px 0 rgba(255,255,255,.08) inset; transform: translateY(-1px); }
button:active { transform: translateY(1px); }
button:focus-visible { outline:2px solid #22D3EE; outline-offset:2px; }
button.primary { background: linear-gradient(90deg,#8B5CF6,#5B7CFA 60%,#22D3EE); border:none; font-weight:600;
  box-shadow: 0 10px 26px -10px rgba(91,124,250,.8), 0 1px 0 rgba(255,255,255,.25) inset; }
button[disabled] { opacity:.45; cursor:not-allowed; transform:none; }
textarea { width:100%; box-sizing:border-box; min-height:96px; resize:vertical; border-radius:14px; padding:12px 14px;
  background: rgba(11,18,48,.85); color:#E7EBF7; border:1px solid #2A3566; font: inherit; font-size:15px; line-height:1.5;
  box-shadow: 0 1px 0 rgba(255,255,255,.04) inset; }
textarea:focus { outline:none; border-color:#8B5CF6; box-shadow: 0 0 0 3px rgba(139,92,246,.25); }
.hint { font-size:12px; color:#A3ACCB; margin-top:6px; }
.interim { color:#7F8AB0; font-style:italic; }
@keyframes vc-blink { 50% { opacity:.2; } }
@keyframes vc-sweep { from { top:-70px; } to { top:100%; } }
@media (max-width: 760px) { .vc-grid { grid-template-columns: 1fr; perspective:none; }
  .tile, .tile.ai, .tile.me, .tile:hover { transform:none; } .tile, .tile video { min-height:300px; } }
@media (prefers-reduced-motion: reduce) { * { animation:none !important; transition:none !important; } .tile { transform:none !important; } }
"""

_HTML = f"""
<div class="vc">
  <div class="vc-grid">
    <div class="tile ai" id="aiTile">
      <div class="stage3d" id="stage3d"><canvas id="bot3d" aria-label="3D AI interviewer"></canvas>
        <div class="fallback">{avatar_svg(170, "idle", "AI interviewer")}</div></div>
      <div class="scan"></div><div class="sweep"></div>
      <span class="hud tl"></span><span class="hud tr"></span><span class="hud bl"></span><span class="hud br"></span>
      <span class="name" id="aiName">🤖 Mentor</span>
      <span class="clock live-dot" id="clock">00:00</span>
      <span class="pill" id="aiPill">AI agent · online</span>
      <div class="glass">
        <div class="caption" id="caption" aria-live="polite"></div>
        <div class="status" id="status"></div>
      </div>
    </div>
    <div class="tile me" id="meTile">
      <video id="self" autoplay playsinline muted></video>
      <div class="camoff" id="camoff"><div class="big">🎙️</div><div id="camoffText">Audio call. Your camera is off.</div></div>
      <span class="hud tl"></span><span class="hud tr"></span><span class="hud bl"></span><span class="hud br"></span>
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

_JS = ROBOT_LIB + r"""
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const $ = (id) => parentElement.querySelector('#' + id);
  const S = parentElement.__vc || (parentElement.__vc = { listening:false, finalText:'', lastQid:null,
      started: Date.now(), rec:null, silence:null, sent:false });
  const G = window.__amVC || (window.__amVC = { stream:null, ctx:null, videos:new Set(), raf:null });
  const d = data || {};
  const av = parentElement.querySelector('.am-av');
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  const setAv = (s) => {
    if (av) av.setAttribute('class', 'am-av ' + s);
    for (const c of ['speaking', 'listening', 'thinking']) $('aiTile').classList.toggle(c, s === c);
    if (S.bot) S.bot.setState(s);
    $('aiPill').textContent = { speaking: '🔊 Speaking', listening: '👂 Listening', thinking: '🧠 Thinking' }[s] || 'AI agent · online';
  };
  // ---------- 3D robot (falls back to the SVG avatar if WebGL / CDN is unavailable)
  if ((!S.bot || S.bot.disposed) && !S.botLoading && amWebGL()) {
    S.botLoading = true;
    amLoadThree().then((THREE) => {
      S.bot = amBuildRobot(THREE, $('bot3d'), { mood: d.mood, getLevel: () => (window.__amVC && window.__amVC.level) || 0 });
      $('stage3d').classList.add('ready');
      if (!S.greeted) { S.greeted = true; setTimeout(() => S.bot && S.bot.wave(), 400); }
    }).catch(() => {}).finally(() => { S.botLoading = false; });
  }
  if (S.bot) S.bot.setMood(d.mood);
  const status = (t) => { $('status').textContent = t; };
  const note = (t) => { $('note').textContent = t; };

  // ---------- question
  $('caption').textContent = d.question || '';
  $('aiName').textContent = '🤖 ' + (d.who || 'Mentor');
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
    u.onboundary = () => { if (S.bot) S.bot.pulse(); };
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
      const an = G.ctx.createAnalyser(); an.fftSize = 2048; src.connect(an); G.an = an;
      const buf = new Uint8Array(an.fftSize);
      cancelAnimationFrame(G.raf);
      const tick = () => {
        an.getByteTimeDomainData(buf);
        let peak = 0; for (const x of buf) peak = Math.max(peak, Math.abs(x - 128));
        G.level = peak / 128;
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

  // ---------- voice measurements (pace, pauses, steadiness, pitch) taken locally while answering
  function pitchOf(buf, rate) {
    let mean = 0; for (const x of buf) mean += x; mean /= buf.length;
    const lo = Math.floor(rate / 400), hi = Math.floor(rate / 75);
    let e0 = 0; for (const x of buf) e0 += (x - mean) * (x - mean);
    if (!e0) return null;
    let best = 0, lag = 0;
    for (let L = lo; L <= hi && L < buf.length; L++) {
      let c = 0; for (let i = 0; i + L < buf.length; i++) c += (buf[i] - mean) * (buf[i + L] - mean);
      if (c > best) { best = c; lag = L; }
    }
    return lag && best / e0 > 0.3 ? rate / lag : null;
  }
  function startMeasure() {
    S.m = { t0: performance.now(), first: null, voiced: 0, total: 0, rms: [], pitches: [], pauses: [], run: 0, floor: null, peak: 0 };
    clearInterval(S.mTimer);
    S.mTimer = setInterval(() => {
      if (!G.an || !S.listening) return;
      const buf = new Float32Array(G.an.fftSize); G.an.getFloatTimeDomainData(buf);
      let sq = 0; for (const x of buf) sq += x * x; const r = Math.sqrt(sq / buf.length);
      const m = S.m; m.total += 50; m.peak = Math.max(m.peak, r);
      if (m.total <= 400) { m.floor = m.floor === null ? r : Math.min(m.floor, r); return; }
      const th = Math.max((m.floor || 0.003) * 2.5, m.peak * 0.08, 0.004);
      if (r >= th) {
        if (m.first === null) m.first = performance.now() - m.t0;
        if (m.run >= 350) m.pauses.push(m.run);
        m.run = 0; m.voiced += 50; m.rms.push(r);
        if (m.rms.length % 2 === 0 && r >= m.peak * 0.15) { const p = pitchOf(buf, G.ctx.sampleRate); if (p) m.pitches.push(p); }
      } else if (m.first !== null) m.run += 50;
    }, 50);
  }
  function measured() {
    const m = S.m; if (!m || !m.rms.length) return {};
    clearInterval(S.mTimer);
    const mean = m.rms.reduce((a, b) => a + b, 0) / m.rms.length;
    const sd = Math.sqrt(m.rms.reduce((a, b) => a + (b - mean) ** 2, 0) / m.rms.length);
    const dur = (performance.now() - m.t0) / 1000;
    const out = { duration_s: dur, speech_s: m.voiced / 1000, silence_ratio: Math.max(0, 1 - (m.voiced / 1000) / Math.max(dur, 0.1)),
      first_word_s: m.first === null ? null : m.first / 1000, long_pauses: m.pauses.filter(x => x >= 1500).length,
      avg_pause_s: m.pauses.length ? m.pauses.reduce((a, b) => a + b, 0) / m.pauses.length / 1000 : 0,
      loudness_variation: mean ? sd / mean : 0, loudness_level: m.peak ? mean / m.peak : 0 };
    if (m.pitches.length >= 8) {
      const st = m.pitches.map(p => 12 * Math.log2(p / 100)); const sm = st.reduce((a, b) => a + b, 0) / st.length;
      out.pitch_hz = m.pitches.reduce((a, b) => a + b, 0) / m.pitches.length;
      out.pitch_variation_st = Math.sqrt(st.reduce((a, b) => a + (b - sm) ** 2, 0) / st.length);
    }
    for (const k in out) if (out[k] === null) delete out[k];
    return out;
  }

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
    if (!S.m) startMeasure();
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
    if (S.bot) S.bot.nod();
    setAv('thinking'); status('⏳ Your coaches are reviewing…');
    $('send').disabled = true;
    setTriggerValue('answer', { qid: d.qid, text, image: d.presence ? snapshot() : null, voice: measured() });
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
    $('answer').value = ''; S.finalText = ''; $('send').disabled = false; S.m = null;
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
          autoplay: bool, key: str, mood: str = "neutral"):
    """Mount the call stage. Returns the component result (.answer / .presence trigger values)."""
    return _stage(key=key, data={"qid": qid, "question": question, "who": who, "lang": ACCENT_LANG.get(accent, "en-GB"),
                                 "camera": camera, "presence": presence, "handsFree": hands_free,
                                 "autoplay": autoplay, "rate": 0.97, "mood": mood},
                  on_answer_change=lambda: None, on_presence_change=lambda: None)

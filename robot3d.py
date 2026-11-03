"""🤖 The 3D robotic AI agent (Three.js, built from primitives: no model files to download).

ROBOT_LIB is plain JavaScript shared by every component that shows the robot. It loads Three.js once from
jsDelivr (pinned version), builds the robot into a <canvas>, and returns a small controller:

    bot.setState('idle' | 'speaking' | 'listening' | 'thinking')
    bot.setMood('neutral' | 'encouraging' | 'celebrate')
    bot.pulse()   // a spoken word: drives the lip-sync
    bot.nod()     // acknowledges an answer
    bot.wave()    // greets
    bot.look(x, y)  // -1..1 gaze target

Behaviour that makes it feel alive: breathing float, random blinks, eyes that follow the pointer (or glance
toward the learner's camera), head tilt while listening, a scanning sweep while thinking, ear rings and chest
LEDs that react to the learner's microphone level, a hologram base with drifting particles.
If WebGL or the CDN is unavailable, callers keep showing the SVG avatar instead.
"""
from __future__ import annotations

import streamlit as st

from avatar import AVATAR_CSS, avatar_svg

THREE_URL = "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js"

ROBOT_LIB = r"""
const AM_THREE_URL = '__THREE_URL__';
function amLoadThree() {
  if (!window.__amThree) window.__amThree = import(AM_THREE_URL);
  return window.__amThree;
}
function amWebGL() {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); }
  catch (e) { return false; }
}

function amBuildRobot(THREE, canvas, opts = {}) {
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  // bust: head + shoulders (hero cards); full: head to hologram base, robot sitting above the caption panel
  if (opts.bust) { camera.position.set(0, 1.5, 6.4); camera.lookAt(0, 1.05, 0); }
  else { camera.fov = 34; camera.position.set(0, 0.5, 7.9); camera.lookAt(0, -0.05, 0); }

  // ---- lights: soft sky, a key light, violet + cyan rims (the app's aurora palette)
  scene.add(new THREE.HemisphereLight(0xc7d6ff, 0x140c2e, 1.0));
  const key = new THREE.DirectionalLight(0xffffff, 2.4); key.position.set(2.5, 4.5, 5); scene.add(key);
  const fill = new THREE.DirectionalLight(0x9fb4ff, 0.6); fill.position.set(-4, 1, 3); scene.add(fill);
  const rimV = new THREE.PointLight(0x8b5cf6, 40, 14); rimV.position.set(-3.2, 2.6, -1.8); scene.add(rimV);
  const rimC = new THREE.PointLight(0x22d3ee, 40, 14); rimC.position.set(3.2, 1.8, -1.8); scene.add(rimC);

  // ---- materials
  const shell = new THREE.MeshPhysicalMaterial({ color: 0xeef1fb, metalness: 0.12, roughness: 0.26, clearcoat: 1, clearcoatRoughness: 0.1 });
  const steel = new THREE.MeshPhysicalMaterial({ color: 0x2a3366, metalness: 0.85, roughness: 0.3, clearcoat: 0.6 });
  const visorM = new THREE.MeshPhysicalMaterial({ color: 0x060a1f, metalness: 0.7, roughness: 0.08, clearcoat: 1, clearcoatRoughness: 0.05,
                                                  side: THREE.DoubleSide });
  const violet = new THREE.MeshStandardMaterial({ color: 0x7c5cf6, metalness: 0.5, roughness: 0.3, emissive: 0x3b1d9a, emissiveIntensity: 0.7 });
  const eyeM = new THREE.MeshBasicMaterial({ color: 0x22d3ee });
  const mouthM = new THREE.MeshBasicMaterial({ color: 0x7dd3fc });
  const glow = (c, o = 1) => new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: o, blending: THREE.AdditiveBlending, depthWrite: false });

  const root = new THREE.Group(); scene.add(root);

  // ---- torso
  const body = new THREE.Group(); root.add(body);
  const torso = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 32), shell);
  torso.scale.set(0.95, 0.9, 0.7); torso.position.y = -0.35; body.add(torso);
  const belt = new THREE.Mesh(new THREE.TorusGeometry(0.86, 0.06, 16, 64), steel);
  belt.rotation.x = Math.PI / 2; belt.position.y = -0.62; belt.scale.set(1, 0.78, 1); body.add(belt);
  const panel = new THREE.Mesh(new THREE.BoxGeometry(0.78, 0.42, 0.06), visorM);
  panel.position.set(0, -0.2, 0.66); panel.rotation.x = -0.12; body.add(panel);
  const leds = [];
  for (let i = 0; i < 7; i++) {
    const l = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.26, 0.02), glow(i % 2 ? 0x8b5cf6 : 0x22d3ee, 0.95));
    l.position.set(-0.27 + i * 0.09, -0.2, 0.705); l.rotation.x = -0.12; body.add(l); leds.push(l);
  }
  const core = new THREE.Mesh(new THREE.CircleGeometry(0.09, 32), glow(0xf472b6, 0.9));
  core.position.set(0.0, 0.16, 0.7); body.add(core);

  // ---- arms (pivot at the shoulder)
  function arm(side) {
    const g = new THREE.Group(); g.position.set(side * 1.0, 0.18, 0); body.add(g);
    const sh = new THREE.Mesh(new THREE.SphereGeometry(0.24, 32, 16), violet); g.add(sh);
    const upper = new THREE.Mesh(new THREE.CapsuleGeometry(0.15, 0.5, 8, 16), shell); upper.position.y = -0.45; g.add(upper);
    const elbow = new THREE.Group(); elbow.position.y = -0.78; g.add(elbow);
    const joint = new THREE.Mesh(new THREE.SphereGeometry(0.14, 24, 12), steel); elbow.add(joint);
    const fore = new THREE.Mesh(new THREE.CapsuleGeometry(0.13, 0.42, 8, 16), shell); fore.position.y = -0.36; elbow.add(fore);
    const hand = new THREE.Mesh(new THREE.SphereGeometry(0.16, 24, 16), steel); hand.position.y = -0.7; hand.scale.set(1, 1.1, 0.8); elbow.add(hand);
    g.rotation.z = side * 0.12;
    return { g, elbow };
  }
  const armL = arm(-1), armR = arm(1);

  // ---- neck + head
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.22, 0.32, 24), steel); neck.position.y = 0.62; body.add(neck);
  const head = new THREE.Group(); head.position.y = 0.78; body.add(head);
  const skull = new THREE.Mesh(new THREE.SphereGeometry(0.86, 64, 48), shell);
  skull.scale.set(1.12, 0.94, 0.96); skull.position.y = 0.55; head.add(skull);
  const visor = new THREE.Mesh(new THREE.SphereGeometry(0.875, 64, 32, Math.PI / 2 - 0.98, 1.96, Math.PI / 2 - 0.52, 0.98), visorM);
  visor.scale.copy(skull.scale); visor.position.copy(skull.position); head.add(visor);
  const visorRim = new THREE.Mesh(new THREE.TorusGeometry(0.62, 0.012, 8, 96, Math.PI), glow(0x8b5cf6, 0.55));
  visorRim.position.set(0, 0.55, 0.82); visorRim.rotation.z = Math.PI; visorRim.scale.set(1.45, 0.75, 1); head.add(visorRim);

  const eyes = [];
  for (const x of [-0.3, 0.3]) {
    const e = new THREE.Mesh(new THREE.CapsuleGeometry(0.085, 0.1, 6, 16), eyeM);
    e.position.set(x, 0.66, 0.84 - Math.abs(x) * 0.12); head.add(e); eyes.push(e);
    const halo = new THREE.Mesh(new THREE.CircleGeometry(0.2, 32), glow(0x22d3ee, 0.22));
    halo.position.set(x, 0.66, 0.83 - Math.abs(x) * 0.12); head.add(halo); e.userData.halo = halo;
  }
  const mouth = [];
  for (let i = 0; i < 9; i++) {
    const x = -0.24 + i * 0.06;
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.042, 0.2, 0.02), mouthM);
    m.position.set(x, 0.33, 0.8 - x * x * 0.6); m.rotation.y = x * 0.8; head.add(m); mouth.push(m);
  }
  const ears = [];
  for (const s of [-1, 1]) {
    const ear = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.18, 32), violet);
    ear.rotation.z = Math.PI / 2; ear.position.set(s * 0.97, 0.55, 0); head.add(ear);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.025, 12, 48), glow(0x22d3ee, 0.9));
    ring.rotation.y = Math.PI / 2; ring.position.set(s * 1.07, 0.55, 0); head.add(ring); ears.push(ring);
  }
  const antenna = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.03, 0.42, 12), steel);
  antenna.position.set(0, 1.5, 0); head.add(antenna);
  const tip = new THREE.Mesh(new THREE.SphereGeometry(0.075, 24, 16), glow(0x22d3ee, 1));
  tip.position.set(0, 1.74, 0); head.add(tip);
  const tipLight = new THREE.PointLight(0x22d3ee, 3, 2.5); tipLight.position.copy(tip.position); head.add(tipLight);

  // ---- hologram base, grid and particles
  const baseY = -1.62;
  const ring1 = new THREE.Mesh(new THREE.TorusGeometry(1.45, 0.018, 8, 128), glow(0x22d3ee, 0.8));
  ring1.rotation.x = Math.PI / 2; ring1.position.y = baseY; scene.add(ring1);
  const ring2 = new THREE.Mesh(new THREE.TorusGeometry(1.75, 0.01, 8, 128, Math.PI * 1.4), glow(0x8b5cf6, 0.7));
  ring2.rotation.x = Math.PI / 2; ring2.position.y = baseY; scene.add(ring2);
  const disc = new THREE.Mesh(new THREE.CircleGeometry(1.45, 64), glow(0x5b7cfa, 0.12));
  disc.rotation.x = -Math.PI / 2; disc.position.y = baseY - 0.01; scene.add(disc);
  const grid = new THREE.GridHelper(14, 28, 0x5b7cfa, 0x1e2a5a);
  grid.position.y = baseY - 0.02; grid.material.transparent = true; grid.material.opacity = 0.35; scene.add(grid);
  const N = 180, pos = new Float32Array(N * 3), speed = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const a = Math.random() * Math.PI * 2, r = 0.6 + Math.random() * 2.2;
    pos[i * 3] = Math.cos(a) * r; pos[i * 3 + 1] = baseY + Math.random() * 4; pos[i * 3 + 2] = Math.sin(a) * r - 0.5;
    speed[i] = 0.12 + Math.random() * 0.3;
  }
  const pGeo = new THREE.BufferGeometry(); pGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const particles = new THREE.Points(pGeo, new THREE.PointsMaterial({ color: 0x9be7ff, size: 0.035, transparent: true, opacity: 0.8,
    blending: THREE.AdditiveBlending, depthWrite: false }));
  scene.add(particles);

  // ---- state
  const COLORS = { idle: 0x22d3ee, speaking: 0x38bdf8, listening: 0x2dd4bf, thinking: 0xa78bfa };
  const st = { state: 'idle', mood: opts.mood || 'neutral', look: { x: 0.25, y: 0 }, lookT: 0, pulse: 0, nod: 0, wave: 0,
               blink: 0, nextBlink: 2, eyeColor: new THREE.Color(COLORS.idle), level: 0 };
  const api = {
    setState(s) { st.state = COLORS[s] !== undefined ? s : 'idle'; },
    setMood(m) { st.mood = m || 'neutral'; },
    pulse() { st.pulse = 1; },
    nod() { st.nod = 1; },
    wave() { st.wave = 1; },
    look(x, y) { st.look.x = x; st.look.y = y; st.lookT = 2.5; },
    disposed: false,
  };
  canvas.addEventListener('pointermove', (ev) => {
    const r = canvas.getBoundingClientRect();
    api.look(((ev.clientX - r.left) / r.width) * 2 - 1, -(((ev.clientY - r.top) / r.height) * 2 - 1));
  });

  function resize() {
    const w = canvas.clientWidth || 300, h = canvas.clientHeight || 300;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize); ro.observe(canvas); resize();

  const clock = new THREE.Clock();
  const lerp = (a, b, k) => a + (b - a) * k;
  function frame() {
    if (!canvas.isConnected) { api.disposed = true; ro.disconnect(); renderer.dispose(); return; }
    requestAnimationFrame(frame);
    const dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime;
    const m = reduce ? 0.15 : 1;
    const level = opts.getLevel ? Math.min(1, opts.getLevel() * 3) : 0;
    st.level = lerp(st.level, level, 0.25);

    root.position.y = Math.sin(t * 1.3) * 0.06 * m;
    body.rotation.y = Math.sin(t * 0.4) * 0.05 * m;

    // gaze: pointer if recent, otherwise glance toward the learner (right) with micro-saccades
    st.lookT -= dt;
    let gx = st.lookT > 0 ? st.look.x : 0.28 + Math.sin(t * 0.7) * 0.08, gy = st.lookT > 0 ? st.look.y : 0.02;
    let tilt = 0, lean = 0;
    if (st.state === 'thinking') { gx = Math.sin(t * 1.1) * 0.5; gy = 0.25; tilt = 0.14; }
    if (st.state === 'listening') { tilt = -0.12 + Math.sin(t * 0.9) * 0.03; lean = 0.08; }
    if (st.state === 'speaking') { tilt = Math.sin(t * 1.7) * 0.05; gy += Math.sin(t * 3.1) * 0.04; }
    let nod = 0;
    if (st.nod > 0) { st.nod = Math.max(0, st.nod - dt * 1.4); nod = Math.sin((1 - st.nod) * Math.PI * 3) * 0.2 * st.nod; }
    head.rotation.y = lerp(head.rotation.y, gx * 0.45 * m, 0.08);
    head.rotation.x = lerp(head.rotation.x, -gy * 0.3 * m + nod - lean, 0.1);
    head.rotation.z = lerp(head.rotation.z, tilt * m, 0.06);
    for (const e of eyes) { e.position.x = Math.sign(e.position.x) * 0.3 + gx * 0.05; }

    // blink
    st.nextBlink -= dt;
    if (st.nextBlink <= 0) { st.blink = 1; st.nextBlink = 2.5 + Math.random() * 3.5; }
    st.blink = Math.max(0, st.blink - dt * 7);
    const happy = st.mood === 'celebrate' || (st.mood === 'encouraging' && st.state !== 'thinking');
    const eyeY = happy ? 0.45 : 1;
    for (const e of eyes) {
      e.scale.y = lerp(e.scale.y, eyeY * (1 - Math.sin(st.blink * Math.PI) * 0.92), 0.5);
      e.userData.halo.material.opacity = 0.16 + 0.12 * Math.sin(t * 2) + st.level * 0.3;
    }
    const targetColor = new THREE.Color(st.mood === 'celebrate' ? 0xfbbf24 : (st.mood === 'encouraging' && st.state === 'idle' ? 0xf9a8d4 : COLORS[st.state]));
    st.eyeColor.lerp(targetColor, 0.08); eyeM.color.copy(st.eyeColor);
    for (const e of eyes) e.userData.halo.material.color.copy(st.eyeColor);

    // lip-sync: word pulses + syllable jitter while speaking
    st.pulse = Math.max(0, st.pulse - dt * 4);
    const talk = st.state === 'speaking' ? Math.max(st.pulse, 0.35 + 0.4 * Math.abs(Math.sin(t * 13 + Math.sin(t * 7)))) : 0;
    mouth.forEach((b, i) => {
      const shape = 1 - Math.abs(i - 4) / 5.5;
      const target = st.state === 'speaking' ? 0.25 + talk * shape * (0.75 + 0.35 * Math.sin(t * 22 + i * 1.7)) * 1.6
                   : (happy ? 0.3 + (Math.abs(i - 4) / 4) * 0.45 : 0.32);
      b.scale.y = lerp(b.scale.y, Math.max(0.2, target), 0.45);
    });
    mouthM.color.copy(st.eyeColor).lerp(new THREE.Color(0xffffff), 0.25);

    // chest LEDs + ears + antenna
    leds.forEach((l, i) => {
      let v;
      if (st.state === 'speaking') v = 0.3 + talk * (0.6 + 0.4 * Math.sin(t * 18 + i));
      else if (st.state === 'listening') v = 0.2 + st.level * (0.7 + 0.3 * Math.sin(t * 10 + i * 2));
      else if (st.state === 'thinking') v = 0.25 + 0.75 * Math.max(0, Math.sin(t * 6 - i * 0.7));
      else v = 0.35 + 0.15 * Math.sin(t * 1.5 + i * 0.5);
      l.scale.y = lerp(l.scale.y, Math.max(0.15, v * 1.4), 0.35);
    });
    core.material.opacity = 0.55 + 0.35 * Math.sin(t * 2.2);
    ears.forEach((r) => {
      const s = 1 + (st.state === 'listening' ? 0.12 + st.level * 0.5 : 0.04 * Math.sin(t * 2));
      r.scale.setScalar(lerp(r.scale.x, s, 0.3));
      r.material.color.copy(st.state === 'listening' ? new THREE.Color(0x2dd4bf) : new THREE.Color(0x22d3ee));
    });
    tip.material.opacity = 0.6 + 0.4 * Math.abs(Math.sin(t * (st.state === 'thinking' ? 6 : 2)));
    tipLight.intensity = 1.5 + 2 * tip.material.opacity;

    // arms: idle sway, greeting wave, small speaking gestures
    st.wave = Math.max(0, st.wave - dt * 0.45);
    const w = st.wave > 0 ? Math.sin(Math.min(1, (1 - st.wave) * 4) * Math.PI / 2) * Math.min(1, st.wave * 3) : 0;
    armR.g.rotation.z = lerp(armR.g.rotation.z, 0.12 + w * 2.5 + (st.state === 'speaking' ? Math.sin(t * 2.2) * 0.08 : 0), 0.12);
    armR.g.rotation.x = lerp(armR.g.rotation.x, (st.state === 'speaking' ? -0.25 - Math.max(0, Math.sin(t * 1.6)) * 0.25 : 0) - w * 0.2, 0.08);
    armR.elbow.rotation.z = lerp(armR.elbow.rotation.z, w * (0.5 + Math.sin(t * 10) * 0.45), 0.25);
    armL.g.rotation.z = lerp(armL.g.rotation.z, -0.12 - Math.sin(t * 1.3) * 0.03 * m, 0.1);
    armL.g.rotation.x = lerp(armL.g.rotation.x, st.state === 'thinking' ? -0.9 : 0, 0.06);
    armL.elbow.rotation.x = lerp(armL.elbow.rotation.x, st.state === 'thinking' ? -1.4 : 0, 0.06);

    // hologram
    ring1.rotation.z += dt * 0.25 * m; ring2.rotation.z -= dt * 0.45 * m;
    ring1.material.opacity = 0.55 + 0.25 * Math.sin(t * 2);
    const p = pGeo.attributes.position.array;
    for (let i = 0; i < N; i++) { p[i * 3 + 1] += speed[i] * dt * m; if (p[i * 3 + 1] > 2.6) p[i * 3 + 1] = baseY; }
    pGeo.attributes.position.needsUpdate = true;

    renderer.render(scene, camera);
  }
  frame();
  return api;
}
""".replace("__THREE_URL__", THREE_URL)

_VIEW_CSS = AVATAR_CSS + """
:host { display:block; }
.bot { position:relative; width:100%; border-radius:20px; overflow:hidden;
  background: radial-gradient(60% 70% at 50% 40%, rgba(91,124,250,.28), transparent 70%),
              radial-gradient(40% 40% at 80% 90%, rgba(244,114,182,.12), transparent 70%), #070C1C; }
.bot canvas { position:absolute; inset:0; width:100%; height:100%; display:block; opacity:0; transition: opacity .6s; }
.bot.ready canvas { opacity:1; }
.bot .fallback { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; transition: opacity .4s; }
.bot.ready .fallback { opacity:0; pointer-events:none; }
.bot .scan { position:absolute; inset:0; pointer-events:none; opacity:.5;
  background: repeating-linear-gradient(0deg, rgba(255,255,255,.025) 0 1px, transparent 1px 3px); }
"""

_VIEW_HTML = f"""<div class="bot" id="bot"><div class="fallback">{avatar_svg(150, "idle", "AI agent")}</div>
<canvas id="c" aria-label="3D AI agent"></canvas><div class="scan"></div></div>"""

_VIEW_JS = ROBOT_LIB + r"""
export default function (component) {
  const { data, parentElement } = component;
  const d = data || {};
  const box = parentElement.querySelector('#bot');
  box.style.height = (d.height || 320) + 'px';
  const S = parentElement.__bot || (parentElement.__bot = {});
  if (S.bot && !S.bot.disposed) { S.bot.setState(d.state || 'idle'); S.bot.setMood(d.mood); return; }
  if (S.loading || !amWebGL()) return;
  S.loading = true;
  amLoadThree().then((THREE) => {
    S.bot = amBuildRobot(THREE, parentElement.querySelector('#c'), { mood: d.mood, bust: !!d.bust });
    S.bot.setState(d.state || 'idle');
    if (d.wave) setTimeout(() => S.bot.wave(), 600);
    box.classList.add('ready');
  }).catch(() => {}).finally(() => { S.loading = false; });
}
"""

_view = st.components.v2.component("am_robot_view", html=_VIEW_HTML, css=_VIEW_CSS, js=_VIEW_JS)


def robot(key: str, height: int = 320, state: str = "idle", mood: str = "neutral", wave: bool = False,
          bust: bool = False) -> None:
    """Show the 3D robot (falls back to the animated SVG if WebGL or the CDN is unavailable)."""
    _view(key=key, data={"height": height, "state": state, "mood": mood, "wave": wave, "bust": bust}, height=height)

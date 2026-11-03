"""Speech services.

Speech-to-text: OpenAI transcription (needs OPENAI_API_KEY). Without it, the
app falls back to typed answers and says so.

Text-to-speech, two options:
  * "browser": the browser's built-in speech synthesis. Free, no key, and it
    supports accent selection (en-US, en-GB, en-AU, en-CA, en-NZ) when the
    user's device has those voices installed.
  * "openai": OpenAI TTS audio (needs OPENAI_API_KEY). Natural voices, but no
    accent choice.

Pronunciation and speaking speed are NOT measured: transcription returns text
only. The UI states this. To add real pronunciation scoring, plug a provider
with phoneme-level assessment into `PronunciationProvider`.
"""
from __future__ import annotations

import html
import io
import json
from typing import Protocol

from config import Settings, get_logger, resolve, settings
from llm import LLMError

log = get_logger(__name__)

ACCENT_LANG = {
    "American English": "en-US",
    "British English": "en-GB",
    "Canadian English": "en-CA",
    "Australian English": "en-AU",
    "New Zealand English": "en-NZ",
    "International English": "en-GB",
}

MAX_AUDIO_BYTES = 24 * 1024 * 1024  # OpenAI transcription limit is 25 MB


def stt_available(cfg: Settings = settings) -> bool:
    return cfg.has_openai


def transcribe(audio_bytes: bytes, filename: str = "answer.wav", cfg: Settings = settings) -> str:
    cfg = resolve(cfg)
    if not cfg.has_openai:
        raise LLMError("Voice answers need OPENAI_API_KEY for transcription. Type your answer instead, or add the key.")
    if not audio_bytes:
        raise LLMError("No audio was recorded.")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise LLMError("The recording is too long. Keep answers under about 10 minutes.")
    import openai

    client = openai.OpenAI(api_key=cfg.openai_api_key, timeout=cfg.llm_timeout)
    buf = io.BytesIO(audio_bytes)
    buf.name = filename
    try:
        resp = client.audio.transcriptions.create(model=cfg.stt_model, file=buf, language="en")
    except Exception as exc:  # noqa: BLE001
        log.error("Transcription failed: %s", type(exc).__name__)
        raise LLMError("Transcription failed. Check your OpenAI key and try again, or type your answer.") from exc
    text = getattr(resp, "text", "") or ""
    if not text.strip():
        raise LLMError("No speech was detected in the recording. Try again closer to the microphone.")
    return text.strip()


def openai_tts(text: str, voice: str = "alloy", cfg: Settings = settings) -> bytes:
    cfg = resolve(cfg)
    if not cfg.has_openai:
        raise LLMError("OpenAI voice needs OPENAI_API_KEY. Switch to the browser voice in Settings.")
    import openai

    client = openai.OpenAI(api_key=cfg.openai_api_key, timeout=cfg.llm_timeout)
    try:
        resp = client.audio.speech.create(model=cfg.tts_model, voice=voice, input=text[:4000])
        return resp.read() if hasattr(resp, "read") else resp.content
    except Exception as exc:  # noqa: BLE001
        log.error("TTS failed: %s", type(exc).__name__)
        raise LLMError("Could not generate speech audio.") from exc


_PLAYER_CSS = """
body { margin:0; font-family:'IBM Plex Sans', system-ui, sans-serif; background:transparent; }
.row { display:flex; align-items:center; gap:10px; }
button { background:#18224A; color:#E7EBF7; border:1px solid #33407A; border-radius:999px; padding:6px 14px;
  cursor:pointer; font-size:13.5px; transition: background .15s, border-color .15s; }
button:hover { background:#222E62; border-color:#8B5CF6; }
button.ghost { background:transparent; color:#A3ACCB; }
#info { color:#A3ACCB; font-size:12px; }
"""


def _player_shell(controls_js: str, label: str, with_avatar: bool, size: int = 40) -> str:
    from avatar import AVATAR_CSS, avatar_svg

    face = avatar_svg(size, "idle", "AI interviewer") if with_avatar else ""
    btn = html.escape(label)
    return f"""<style>{AVATAR_CSS}{_PLAYER_CSS}</style>
<div class="row">{face}
  <button id="speak" aria-label="{btn}">&#9654; {btn}</button>
  <button id="stop" class="ghost" aria-label="Stop">&#9632; Stop</button>
  <span id="info" aria-live="polite"></span>
</div>
<script>
const av = document.querySelector('.am-av');
function setState(s) {{ if (av) av.className = 'am-av ' + s; }}
{controls_js}
</script>"""


def _js_string(text: str) -> str:
    # json.dumps alone is not safe inside <script>: model text containing "</script>" could break out.
    # Escaping every "<", ">" and "&" as a unicode escape keeps it a plain JS string.
    return json.dumps(text).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def browser_tts_html(text: str, accent: str, autoplay: bool = True, label: str = "Play", rate: float = 0.95,
                     with_avatar: bool = True) -> str:
    """Browser speech synthesis with an avatar that animates while it talks."""
    lang = ACCENT_LANG.get(accent, "en-GB")
    js = f"""
const text = {_js_string(text)};
const lang = "{lang}";
function pickVoice() {{
  const voices = window.speechSynthesis.getVoices();
  return voices.find(v => v.lang === lang) || voices.find(v => v.lang && v.lang.startsWith(lang.slice(0,2))) || null;
}}
function speak() {{
  if (!('speechSynthesis' in window)) {{ document.getElementById('info').textContent = 'Speech is not supported in this browser.'; return; }}
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang; u.rate = {rate};
  const v = pickVoice();
  if (v) {{ u.voice = v; document.getElementById('info').textContent = '🔊 ' + v.name; }}
  else {{ document.getElementById('info').textContent = 'No ' + lang + ' voice installed; using default.'; }}
  u.onstart = () => setState('speaking');
  u.onend = () => setState('idle');
  u.onerror = () => setState('idle');
  window.speechSynthesis.speak(u);
}}
document.getElementById('speak').onclick = speak;
document.getElementById('stop').onclick = () => {{ window.speechSynthesis.cancel(); setState('idle'); }};
if ({str(autoplay).lower()}) {{
  if (window.speechSynthesis.getVoices().length) speak();
  else window.speechSynthesis.onvoiceschanged = () => {{ window.speechSynthesis.onvoiceschanged = null; speak(); }};
}}
"""
    return _player_shell(js, label, with_avatar)


def audio_player_html(audio: bytes, autoplay: bool = True, label: str = "Play", mime: str = "audio/mpeg",
                      with_avatar: bool = True) -> str:
    """OpenAI TTS audio with the same animated avatar, synced to play/pause."""
    import base64

    src = f"data:{mime};base64,{base64.b64encode(audio).decode()}"
    js = f"""
const a = new Audio("{src}");
a.onplay = () => setState('speaking');
a.onpause = a.onended = () => setState('idle');
document.getElementById('speak').onclick = () => {{ a.currentTime = 0; a.play().catch(() => {{}}); }};
document.getElementById('stop').onclick = () => a.pause();
if ({str(autoplay).lower()}) a.play().catch(() => {{ document.getElementById('info').textContent = 'Press play to listen.'; }});
"""
    return _player_shell(js, label, with_avatar)


class PronunciationProvider(Protocol):
    """Extension point for a service with phoneme-level pronunciation scoring."""

    def assess(self, audio_bytes: bytes, reference_text: str) -> dict: ...

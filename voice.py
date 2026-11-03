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

from config import Settings, get_logger, settings
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


def browser_tts_html(text: str, accent: str, autoplay: bool = True, label: str = "Play", rate: float = 0.95) -> str:
    """A small self-contained player that uses the browser's speech synthesis."""
    lang = ACCENT_LANG.get(accent, "en-GB")
    # json.dumps alone is not safe inside <script>: model text containing "</script>" could break out.
    # Escaping every "<", ">" and "&" as a unicode escape keeps it a plain JS string.
    payload = json.dumps(text).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    btn = html.escape(label)
    return f"""
<div style="font-family: 'IBM Plex Sans', system-ui, sans-serif;">
  <button id="speak" style="background:#1B2650;color:#E7EBF7;border:1px solid #3B4A85;border-radius:8px;
     padding:6px 14px;cursor:pointer;font-size:14px;">&#9654; {btn}</button>
  <button id="stop" style="background:transparent;color:#9AA3C2;border:1px solid #2A3566;border-radius:8px;
     padding:6px 12px;cursor:pointer;font-size:14px;margin-left:6px;">Stop</button>
  <span id="info" style="color:#9AA3C2;font-size:12px;margin-left:8px;"></span>
</div>
<script>
const text = {payload};
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
  if (v) {{ u.voice = v; document.getElementById('info').textContent = v.name; }}
  else {{ document.getElementById('info').textContent = 'No ' + lang + ' voice installed; using default.'; }}
  window.speechSynthesis.speak(u);
}}
document.getElementById('speak').onclick = speak;
document.getElementById('stop').onclick = () => window.speechSynthesis.cancel();
if ({str(autoplay).lower()}) {{
  if (window.speechSynthesis.getVoices().length) speak();
  else window.speechSynthesis.onvoiceschanged = () => {{ window.speechSynthesis.onvoiceschanged = null; speak(); }};
}}
</script>"""


class PronunciationProvider(Protocol):
    """Extension point for a service with phoneme-level pronunciation scoring."""

    def assess(self, audio_bytes: bytes, reference_text: str) -> dict: ...

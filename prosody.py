"""Measurable signals of how someone spoke: the honest, deterministic layer under the emotion coach.

Two sources feed the same dictionary:
  * voice:  a WAV recording (Whisper path) or live numbers measured in the browser during a voice/video call:
            pace, pauses, time before the first word, loudness steadiness and pitch variation
  * words:  the transcript or typed answer: filler words, hedges, apologies, self-corrections and
            negative self-talk ("I'm bad at this", "I'm nervous")

These are signals, not feelings. The ConfidenceCoach agent interprets them carefully, together with the
learner's own self-reports, and never presents them as a diagnosis.
"""
from __future__ import annotations

import io
import math
import re
import wave
from typing import Any

# "like", "actually", "kind of" are often meaningful, so only unambiguous fillers are counted here
FILLERS = ["um", "umm", "uh", "uhh", "er", "erm", "ah", "hmm", "you know", "basically", "i mean", "so yeah",
           "literally"]
HEDGES = ["i think", "i guess", "maybe", "probably", "perhaps", "not sure", "i don't know", "i dont know",
          "might be", "i suppose", "kind of", "sort of"]
APOLOGIES = ["sorry", "apologies", "excuse me", "my bad", "pardon"]
NEGATIVE_SELF_TALK = [
    "i'm bad at", "im bad at", "i am bad at", "i'm not good", "i am not good", "im not good", "i can't", "i cant",
    "i cannot do", "i always fail", "i'm stupid", "i am stupid", "i'm nervous", "i am nervous", "im nervous",
    "i'm scared", "i am scared", "i'm afraid", "i am afraid", "i'm anxious", "i am anxious", "i panic", "i freeze",
    "my english is bad", "my english is poor", "i'm not confident", "i am not confident", "i'm not smart",
    "i'll never", "i will never", "i hate speaking", "i'm worried", "i am worried", "i'm confused",
]
POSITIVE_MARKERS = ["i built", "i designed", "i led", "i solved", "i improved", "i'm confident", "i am confident",
                    "i enjoyed", "i learned", "i achieved", "i delivered", "i implemented", "i'm excited",
                    "i am excited", "i'm proud", "i am proud"]


def _count(text: str, phrases: list[str]) -> dict[str, int]:
    out = {}
    for p in phrases:
        n = len(re.findall(r"(?<![a-z'])" + re.escape(p) + r"(?![a-z'])", text))
        if n:
            out[p] = n
    return out


def text_signals(text: str) -> dict[str, Any]:
    """Language signals from what was said or typed."""
    raw = (text or "").strip()
    low = raw.lower().replace("’", "'")
    words = re.findall(r"[a-zA-Z']+", low)
    n = len(words)
    fillers = _count(low, FILLERS)
    hedges = _count(low, HEDGES)
    apologies = _count(low, APOLOGIES)
    negative = _count(low, NEGATIVE_SELF_TALK)
    positive = _count(low, POSITIVE_MARKERS)
    repeats = sum(1 for a, b in zip(words, words[1:]) if a == b and len(a) > 1)
    sentences = [s for s in re.split(r"[.!?]+", raw) if s.strip()]
    per100 = (lambda c: round(100 * sum(c.values()) / n, 1)) if n else (lambda c: 0.0)
    return {
        "words": n,
        "sentences": len(sentences),
        "avg_sentence_words": round(n / len(sentences), 1) if sentences else 0,
        "fillers": fillers, "fillers_per_100": per100(fillers),
        "hedges": hedges, "hedges_per_100": per100(hedges),
        "apologies": sum(apologies.values()),
        "negative_self_talk": list(negative),
        "positive_ownership": list(positive),
        "repeated_words": repeats,
        "very_short": n < 12,
    }


# --------------------------------------------------------------------------- voice

def _frames(samples, rate: int, ms: int = 30):
    step = max(1, int(rate * ms / 1000))
    return [samples[i:i + step] for i in range(0, len(samples) - step + 1, step)], ms / 1000


def _pitch(frame, rate: int) -> float | None:
    """Autocorrelation pitch estimate (75-400 Hz) for one voiced frame."""
    import numpy as np

    x = frame - frame.mean()
    if not x.any():
        return None
    corr = np.correlate(x, x, mode="full")[len(x) - 1:]
    lo, hi = int(rate / 400), int(rate / 75)
    if hi >= len(corr) or lo < 1:
        return None
    seg = corr[lo:hi]
    lag = int(seg.argmax()) + lo
    if corr[0] <= 0 or corr[lag] / corr[0] < 0.3:  # not periodic enough to trust
        return None
    return rate / lag


def _summarise(rms: list[float], pitches: list[float], frame_s: float, duration: float) -> dict[str, Any]:
    if not rms:
        return {}
    peak = max(rms) or 1.0
    floor = sorted(rms)[len(rms) // 10]  # 10th percentile ~ room noise
    thresh = max(floor * 2.5, peak * 0.08)
    voiced = [r >= thresh for r in rms]
    speech_s = sum(voiced) * frame_s
    first = next((i for i, v in enumerate(voiced) if v), None)
    last = len(voiced) - 1 - next((i for i, v in enumerate(reversed(voiced)) if v), len(voiced))
    long_pauses, run = 0, 0
    pauses: list[float] = []
    if first is not None:
        for v in voiced[first:last + 1]:
            if v:
                if run * frame_s >= 0.35:
                    pauses.append(run * frame_s)
                if run * frame_s >= 1.5:
                    long_pauses += 1
                run = 0
            else:
                run += 1
    vrms = [r for r, v in zip(rms, voiced) if v]
    mean_v = sum(vrms) / len(vrms) if vrms else 0
    cv = (math.sqrt(sum((r - mean_v) ** 2 for r in vrms) / len(vrms)) / mean_v) if vrms and mean_v else 0
    out = {
        "duration_s": round(duration, 1),
        "speech_s": round(speech_s, 1),
        "silence_ratio": round(1 - speech_s / duration, 2) if duration else 0,
        "first_word_s": round(first * frame_s, 1) if first is not None else None,
        "long_pauses": long_pauses,
        "avg_pause_s": round(sum(pauses) / len(pauses), 2) if pauses else 0,
        "loudness_variation": round(cv, 2),   # high = shaky / trailing off, very low = flat
        "loudness_level": round(mean_v / peak, 2) if peak else 0,
    }
    if len(pitches) >= 8:
        st = [12 * math.log2(p / 100) for p in pitches]
        m = sum(st) / len(st)
        out["pitch_hz"] = round(sum(pitches) / len(pitches))
        out["pitch_variation_st"] = round(math.sqrt(sum((s - m) ** 2 for s in st) / len(st)), 2)
    return out


def analyze_wav(data: bytes) -> dict[str, Any]:
    """Voice signals from a WAV file (what st.audio_input returns). Empty dict if it cannot be read."""
    try:
        import numpy as np

        with wave.open(io.BytesIO(data)) as w:
            rate, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
            raw = w.readframes(n)
        if width != 2 or not n:
            return {}
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        if ch > 1:
            x = x.reshape(-1, ch).mean(axis=1)
        x /= 32768.0
        frames, fs = _frames(x, rate)
        rms = [float(np.sqrt((f ** 2).mean())) for f in frames]
        out = _summarise(rms, [], fs, len(x) / rate)
        if not out:
            return {}
        peak = max(rms) or 1.0
        pitches = []
        for f, r in zip(frames, rms):
            if r >= peak * 0.15:
                p = _pitch(f, rate)
                if p:
                    pitches.append(p)
        return _summarise(rms, pitches, fs, len(x) / rate) if pitches else out
    except Exception:  # noqa: BLE001 - analysis is optional; never block an answer
        return {}


def clean_live(metrics: dict | None) -> dict[str, Any]:
    """Validate numbers measured in the browser (they come from the client, so bound everything)."""
    if not isinstance(metrics, dict):
        return {}
    spec = {"duration_s": 3600, "speech_s": 3600, "silence_ratio": 1, "first_word_s": 600, "long_pauses": 500,
            "avg_pause_s": 60, "loudness_variation": 10, "loudness_level": 1, "pitch_hz": 1000,
            "pitch_variation_st": 24}
    out = {}
    for k, hi in spec.items():
        v = metrics.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= hi:
            out[k] = round(float(v), 2)
    return out


def combine(text: str, voice: dict | None = None, mode: str = "text") -> dict[str, Any]:
    """All signals for one answer, plus plain-language observations the coach can cite."""
    t = text_signals(text)
    v = dict(voice or {})
    if v.get("speech_s", 0) >= 3 and t["words"]:
        wpm = round(60 * t["words"] / v["speech_s"], 0)
        if 50 <= wpm <= 260:  # outside this range the text was typed or edited, so pace would mislead
            v["words_per_minute"] = wpm
    obs: list[str] = []
    if v:
        wpm = v.get("words_per_minute")
        if wpm and wpm > 175:
            obs.append(f"Fast pace ({wpm:.0f} words/min); calm interview pace is about 120-160.")
        elif wpm and wpm < 95:
            obs.append(f"Slow, careful pace ({wpm:.0f} words/min).")
        if v.get("first_word_s") is not None and v["first_word_s"] >= 4:
            obs.append(f"Took {v['first_word_s']:.0f}s before the first word.")
        if v.get("long_pauses", 0) >= 2:
            obs.append(f"{v['long_pauses']} long pauses (over 1.5s) while answering.")
        if v.get("loudness_variation", 0) >= 0.9:
            obs.append("Volume rose and fell a lot, which can sound like trailing off.")
        if v.get("loudness_level") is not None and v["loudness_level"] < 0.25:
            obs.append("Voice was quiet compared with your loudest moments.")
        pv = v.get("pitch_variation_st")
        if pv is not None and pv < 1.2:
            obs.append("Pitch stayed quite flat (little intonation).")
        elif pv is not None and pv > 5:
            obs.append("Pitch moved a lot, which can signal excitement or tension.")
    if t["fillers_per_100"] >= 5:
        obs.append(f"Filler words: {t['fillers_per_100']} per 100 words ({', '.join(list(t['fillers'])[:4])}).")
    if t["hedges_per_100"] >= 4:
        obs.append(f"Hedging phrases ({', '.join(list(t['hedges'])[:3])}) soften your point.")
    if t["apologies"]:
        obs.append(f"Apologised {t['apologies']}x during the answer.")
    if t["negative_self_talk"]:
        obs.append("Negative self-talk: " + ", ".join(f'"{x}"' for x in t["negative_self_talk"][:3]) + ".")
    if t["positive_ownership"]:
        obs.append("Clear ownership language: " + ", ".join(f'"{x}"' for x in t["positive_ownership"][:3]) + ".")
    if t["very_short"]:
        obs.append(f"Very short answer ({t['words']} words).")
    return {"mode": mode, "voice": v, "text": t, "observations": obs}

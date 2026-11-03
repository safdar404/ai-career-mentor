"""🔑 Bring-your-own API keys.

Keys typed here live only in this browser session's memory (st.session_state).
They are never written to the database, the disk, the logs or the page, and
they disappear when the tab is closed or the visitor clicks "Forget keys".
A server key set in Streamlit Secrets / .env is still used as a fallback.
"""
from __future__ import annotations

import streamlit as st

from config import SESSION_KEYS, base_settings, get_logger, key_source, remember_secret

log = get_logger(__name__)

PROVIDERS = {
    "anthropic": {"label": "Claude (Anthropic)", "emoji": "🟣", "prefix": "sk-ant-",
                  "url": "https://console.anthropic.com/settings/keys",
                  "gives": "All coaching, interviews and video presence feedback"},
    "openai": {"label": "OpenAI", "emoji": "🟢", "prefix": "sk-",
               "url": "https://platform.openai.com/api-keys",
               "gives": "Coaching, plus Whisper transcription and natural AI voice"},
}


def looks_valid(provider: str, key: str) -> str | None:
    """Cheap format check. Returns an error message or None."""
    key = (key or "").strip()
    if not key:
        return "Paste a key first."
    if any(c.isspace() for c in key):
        return "The key contains spaces. Copy it again without extra characters."
    if not key.startswith(PROVIDERS[provider]["prefix"]):
        return f"{PROVIDERS[provider]['label']} keys start with `{PROVIDERS[provider]['prefix']}`."
    if len(key) < 20:
        return "That key looks too short."
    return None


def verify(provider: str, key: str) -> str | None:
    """Make one free, read-only call to check the key. Returns an error message or None."""
    try:
        if provider == "anthropic":
            import anthropic

            anthropic.Anthropic(api_key=key, timeout=20).models.list(limit=1)
        else:
            import openai

            openai.OpenAI(api_key=key, timeout=20).models.list()
    except Exception as exc:  # noqa: BLE001 - SDK exception classes differ between versions
        kind = type(exc).__name__
        log.warning("Key check failed for %s: %s", provider, kind)
        if "Authentication" in kind or "PermissionDenied" in kind:
            return "The provider rejected this key. Check that it is active and copied in full."
        if "Connection" in kind or "Timeout" in kind:
            return "Could not reach the provider to check the key. Try again."
        return f"The key could not be checked ({kind})."
    return None


def _reset_ai_caches() -> None:
    for k in [k for k in st.session_state if str(k).startswith("orch::") or k == "tts_cache"]:
        del st.session_state[k]


def set_key(provider: str, key: str) -> None:
    keys = dict(st.session_state.get(SESSION_KEYS) or {})
    keys[provider] = key.strip()
    remember_secret(key.strip())
    st.session_state[SESSION_KEYS] = keys
    _reset_ai_caches()


def forget_keys() -> None:
    st.session_state.pop(SESSION_KEYS, None)
    _reset_ai_caches()


def status_line() -> str:
    parts = []
    for p, meta in PROVIDERS.items():
        src = key_source(p)
        mark = {"session": "✅ your key", "server": "✅ app key", "": "⚪ not set"}[src]
        parts.append(f"{meta['emoji']} {meta['label'].split(' ')[0]}: {mark}")
    return "  \n".join(parts)


def any_key() -> bool:
    return bool(key_source("anthropic") or key_source("openai"))


def key_form(where: str = "sidebar", check_online: bool = True) -> None:
    """The key entry form. `where` keeps widget keys unique when shown twice."""
    provider = st.radio("Provider", list(PROVIDERS), format_func=lambda p: f"{PROVIDERS[p]['emoji']} {PROVIDERS[p]['label']}",
                        horizontal=True, key=f"{where}-key-provider", label_visibility="collapsed")
    meta = PROVIDERS[provider]
    with st.form(f"{where}-key-form", clear_on_submit=True, border=False):
        key = st.text_input(f"{meta['label']} API key", type="password", placeholder=f"{meta['prefix']}...",
                            help=f"{meta['gives']}. Get one at {meta['url']}", autocomplete="off")
        save = st.form_submit_button("🔐 Connect key", type="primary", width="stretch")
    if save:
        err = looks_valid(provider, key)
        if not err and check_online:
            with st.spinner("Checking the key..."):
                err = verify(provider, key.strip())
        if err:
            st.error(err)
        else:
            set_key(provider, key)
            st.toast(f"{meta['label']} connected for this session", icon="✅")
            st.rerun()
    st.caption(f"[Get a {meta['label']} key ↗]({meta['url']}) · {meta['gives']}.")


def sidebar_panel() -> None:
    connected = any_key()
    with st.expander("🔑 API keys" + ("" if connected else "  ·  needed for AI"), expanded=not connected):
        st.markdown(status_line())
        key_form("sidebar")
        st.caption("🛡️ Kept only in this browser session's memory. Never saved to the database, logs or disk.")
        if st.session_state.get(SESSION_KEYS) and st.button("🧹 Forget my keys", width="stretch"):
            forget_keys()
            st.rerun()


def server_has_keys() -> bool:
    return base_settings.any_llm

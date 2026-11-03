import streamlit as st

from orchestrator import DIFFICULTIES
from topics import TOPIC_GROUPS
from components import bullet_list, gaps_found, page_header, run_safely, scorecard, topic_label

TOPICS = (list(TOPIC_GROUPS["python"]) + list(TOPIC_GROUPS["python_libs"]) +
          ["genai.rag", "genai.vector_db", "genai.llm_apis", "agentic.tool_calling", "app.rest_fastapi",
           "app.error_handling", "auto.triggers_webhooks"])


def _reset() -> None:
    for k in ("code_sid", "code_ch", "code_res"):
        st.session_state.pop(k, None)


def render(user, orch_getter) -> None:
    page_header("🐍 Python Coding Lab",
                "AI-generated challenges with a senior-engineer code review. Your code is syntax-checked, then "
                "reviewed. It is not executed, so run the test cases yourself.")
    orch = orch_getter()
    if orch is None:
        return

    if not st.session_state.get("code_sid"):
        with st.form("code-setup"):
            c1, c2 = st.columns(2)
            topic = c1.selectbox("Topic", TOPICS, format_func=topic_label)
            difficulty = c2.selectbox("Difficulty", DIFFICULTIES[:3])
            go = st.form_submit_button("⚡ Generate challenge", type="primary")
        if go:
            out = run_safely("Writing a challenge for you...", lambda: orch.start_coding(user.id, topic, difficulty))
            if out:
                st.session_state["code_sid"], st.session_state["code_ch"] = out
                st.rerun()
        return

    sid, ch_wrap = st.session_state["code_sid"], st.session_state["code_ch"]
    ch = ch_wrap["challenge"]
    st.markdown(f"### {ch['title']}")
    st.markdown(ch["problem"])
    bullet_list("Requirements", ch.get("requirements", []))
    if ch.get("test_cases"):
        st.markdown("**Test cases**")
        for t in ch["test_cases"]:
            st.code(f"{t.get('input')}\n# expected: {t.get('expected')}", language="python")
    if ch.get("hints"):
        with st.expander("Hints (try without them first)"):
            st.markdown("\n".join(f"- {h}" for h in ch["hints"]))

    code_key = f"code-{ch_wrap['id']}"
    st.session_state.setdefault(code_key, ch.get("starter_code", ""))
    st.text_area("Your solution", key=code_key, height=320)
    res = st.session_state.get("code_res")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Submit for review", type="primary"):
            out = run_safely("A senior engineer is reviewing your code...",
                             lambda: orch.submit_code(sid, ch_wrap["id"], st.session_state.get(code_key, "")))
            if out:
                st.session_state["code_res"] = out
                st.rerun()
    with c2:
        if st.button("🔄 New challenge"):
            _reset()
            st.rerun()

    if res:
        st.markdown("---")
        if res.get("syntax_error"):
            st.error(f"Syntax error at {res['syntax_error']}. Fix this first.")
        else:
            st.success("Syntax check passed. The code was not executed.")
        r = res["review"]
        scorecard(res["scores"], res["total"])
        st.caption("For code: correctness maps to technical accuracy, problem solving to conceptual understanding, "
                   "and code quality to practical knowledge.")
        st.markdown(r.get("summary", ""))
        if r.get("likely_test_results"):
            st.markdown("**Likely test results (static reasoning, not execution)**")
            for t in r["likely_test_results"]:
                mark = "likely passes" if t.get("likely_pass") else "likely fails"
                st.markdown(f"- `{t.get('test')}`: {mark}. {t.get('reason', '')}")
        if r.get("issues"):
            st.markdown("**Issues**")
            for i in r["issues"]:
                st.markdown(f"- **{str(i.get('severity', '')).title()}**: {i.get('issue')}  \n  Fix: {i.get('fix')}")
        bullet_list("What was good", r.get("what_was_good", []))
        if r.get("improved_code"):
            with st.expander("Improved version"):
                st.code(r["improved_code"], language="python")
        if r.get("next_step"):
            st.info(f"Next step: {r['next_step']}")
        st.markdown("**Weaknesses recorded**")
        gaps_found(res.get("gaps", []))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analytics, db
from components import SCORE_LABELS, page_header, run_safely

SECTION_TITLES = {
    "english_communication": "English communication", "technical_knowledge": "Technical knowledge",
    "interview_performance": "Interview performance", "strongest_areas": "Strongest areas",
    "weakest_areas": "Weakest areas", "frequent_grammar_mistakes": "Most frequent grammar mistakes",
    "vocabulary_development": "Vocabulary development", "confidence": "Confidence",
    "questions_still_unanswered": "Questions you still can't answer", "next_week_plan": "Next week's plan",
}


def render(user, orch_getter) -> None:
    page_header("📈 Performance Reports",
                "Area scores and weekly progress reports, written only from data stored in your training history.")

    groups = analytics.group_scores(user.id)
    comm = db.communication_skills(user.id)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Technical areas")
        if groups:
            fig = go.Figure(go.Bar(x=[g["score"] for g in groups], y=[g["group"] for g in groups], orientation="h",
                                   marker_color="#2EC5FF", text=[f"{g['answers']} answers" for g in groups]))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(range=[0, 100]),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#9AA3C2"))
            st.plotly_chart(fig, width="stretch")
        else:
            st.caption("No technical answers yet.")
    with c2:
        st.markdown("#### Communication")
        if comm:
            df = pd.DataFrame([{"Skill": SCORE_LABELS[c.dimension], "Score": round(c.score_avg * 10, 1),
                                "Answers": c.attempts} for c in comm])
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.caption("No communication data yet.")

    st.markdown("---")
    st.markdown("#### Weekly progress report")
    st.caption("Covers the last 7 days and compares with the 7 days before, when that data exists.")
    if st.button("📝 Generate this week's report", type="primary"):
        orch = orch_getter()
        if orch:
            out = run_safely("Your progress manager is writing the report...", lambda: orch.weekly_report(user.id))
            if out:
                st.rerun()

    reports = db.list_reports(user.id)
    if not reports:
        st.info("No reports yet.")
    for i, r in enumerate(reports):
        with st.expander(f"Report for {r.period_start} to {r.period_end}", expanded=i == 0):
            cur = r.stats.get("current", {})
            prev = r.stats.get("previous_period", {})
            cols = st.columns(3)
            cols[0].metric("Answers", cur.get("answers", 0))
            cols[1].metric("Average score", cur.get("average_total") if cur.get("average_total") is not None else "-",
                           delta=(round(cur["average_total"] - prev["average_total"], 1)
                                  if cur.get("average_total") is not None and prev.get("average_total") is not None else None))
            cols[2].metric("Sessions", cur.get("sessions", 0))
            for key, title in SECTION_TITLES.items():
                st.markdown(f"**{title}**")
                st.markdown(r.content.get(key, "Not enough data."))

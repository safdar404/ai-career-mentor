import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analytics, db
from components import chips, metric_card, page_header, topic_label

VIOLET, VOLT, MUTED = "#8B5CF6", "#2EC5FF", "#9AA3C2"


def _layout(fig: go.Figure, height: int = 300) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED, family="IBM Plex Sans"),
                      legend=dict(orientation="h", y=1.12), yaxis=dict(range=[0, 100], gridcolor="#1C2550"),
                      xaxis=dict(gridcolor="#1C2550"))
    return fig


def render(user, orch_getter) -> None:
    page_header(f"Welcome back, {user.name.split()[0]}",
                f"Your progress toward {user.target_role} interviews, calculated from every answer you have submitted.")
    metrics = analytics.dashboard_metrics(user.id)
    if all(m["value"] is None for m in metrics.values()):
        st.info("No answers evaluated yet. Start with a Live AI Interview or the English Communication Lab. "
                "Your scores will appear here after your first answer.")

    names = list(metrics)
    for row in (names[:4], names[4:]):
        cols = st.columns(4)
        for col, name in zip(cols, row):
            with col:
                m = metrics[name]
                metric_card(name, m["value"], m["n"])

    trend = analytics.daily_trend(user.id)
    week = analytics.week_comparison(user.id)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("#### Daily performance")
        if trend:
            df = pd.DataFrame(trend)
            fig = go.Figure()
            for col, color, name in (("overall", VIOLET, "Overall"), ("technical", VOLT, "Technical"),
                                     ("communication", "#C4B5FD", "English")):
                if df[col].notna().any():
                    fig.add_trace(go.Scatter(x=df["day"], y=df[col], name=name, mode="lines+markers",
                                             line=dict(color=color, width=2)))
            st.plotly_chart(_layout(fig), width="stretch")
        else:
            st.caption("Your daily trend appears after your first evaluated answer.")
    with c2:
        st.markdown("#### This week")
        if week["this_week"] is None:
            st.caption("No answers in the last 7 days.")
        else:
            change = ""
            if week["change"] is not None:
                change = f"{'+' if week['change'] >= 0 else ''}{week['change']} vs previous 7 days"
            else:
                change = "No data from the previous 7 days to compare."
            metric_card("Average score, last 7 days", week["this_week"], week["this_n"])
            st.caption(change)
        minutes = analytics.training_minutes(user.id)
        answers = sum(d["answers"] for d in trend)
        st.markdown(f"**Training time:** {minutes / 60:.1f} hours  \n**Exercises completed:** {answers}")

    c1, c2, c3 = st.columns(3)
    strongest, weakest = analytics.topic_strengths(user.id)
    with c1:
        st.markdown("#### Strongest topics")
        if strongest:
            for r in strongest:
                st.markdown(f"- {topic_label(r['topic'])}: **{r['score']:g}** ({r['attempts']})")
        else:
            st.caption("No topic above 60 yet.")
    with c2:
        st.markdown("#### Weakest topics")
        if weakest:
            for r in weakest:
                st.markdown(f"- {topic_label(r['topic'])}: **{r['score']:g}** ({r['attempts']})")
        else:
            st.caption("No weak topics recorded yet.")
    with c3:
        st.markdown("#### Repeated mistakes")
        rep = [g for g in db.list_gaps(user.id) if g.occurrences >= db.PRIORITY_THRESHOLD][:5]
        if rep:
            for g in rep:
                st.markdown(f"- {g.description} ({g.occurrences}x)")
        else:
            st.caption("Nothing repeated yet.")

    st.markdown("#### Interview history")
    hist = analytics.interview_history(user.id, limit=15)
    if hist:
        df = pd.DataFrame(hist).drop(columns=["id"])
        df.columns = ["Date", "Module", "Role", "Category", "Difficulty", "Answers", "Average", "Status"]
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.caption("No sessions yet.")

import datetime as dt

import streamlit as st

import analytics, db
from components import esc, page_header, run_safely


def _in_phase(day: int, days: str) -> bool:
    try:
        a, b = [int(x) for x in str(days).replace("Days", "").replace(" ", "").split("-")[:2]]
        return a <= day <= b
    except ValueError:
        return False


def render(user, orch_getter) -> None:
    page_header("Learning Roadmap",
                "A 90-day plan in six phases. Adjust it at any time and the mentor rewrites it from your real "
                "assessment results.")
    rm = db.active_roadmap(user.id)
    if rm is None:
        st.markdown("Your roadmap starts on the day you create it.")
        start = st.date_input("Day 1", value=dt.date.today())
        if st.button("Create my 90-day roadmap", type="primary"):
            db.save_roadmap(user.id, analytics.BASE_ROADMAP, "Starting plan, before any assessment.", start)
            st.rerun()
        return

    day = analytics.roadmap_day(rm.start_date)
    st.progress(day / 90, text=f"Day {day} of 90 (started {rm.start_date})")
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("Adjust to my results", type="primary",
                     help="The mentor rewrites the plan using your scores and weaknesses"):
            orch = orch_getter()
            if orch:
                if not db.evaluations_for_user(user.id):
                    st.warning("Complete some practice first. There are no results to adjust the plan to yet.")
                else:
                    out = run_safely("Your mentor is updating the plan...", lambda: orch.adjust_roadmap(user.id))
                    if out:
                        st.rerun()
        if st.button("Reset to the standard plan"):
            db.save_roadmap(user.id, analytics.BASE_ROADMAP, "Reset to the standard plan.", rm.start_date)
            st.rerun()
    with c1:
        if rm.rationale:
            st.caption(rm.rationale)

    for ph in rm.content.get("phases", []):
        now = _in_phase(day, ph.get("days", ""))
        goals = "".join(f"<li>{esc(g)}</li>" for g in ph.get("goals", []))
        acts = "".join(f"<li>{esc(a)}</li>" for a in ph.get("daily_activities", []))
        st.markdown(
            f'<div class="am-phase {"now" if now else ""}"><div class="days">Days {esc(ph.get("days"))}'
            f'{" | You are here" if now else ""}</div><h4>{esc(ph.get("phase"))}</h4>'
            f'<div style="color:#9AA3C2">{esc(ph.get("focus"))}</div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:8px">'
            f'<div><b>Goals</b><ul>{goals}</ul></div><div><b>Daily activities</b><ul>{acts}</ul></div></div>'
            f'<div><b>Milestone:</b> {esc(ph.get("milestone"))}</div></div>', unsafe_allow_html=True)

from datetime import date
from email.utils import parsedate_to_datetime

import altair as alt
import pandas as pd
import streamlit as st
from modules.api import api_get
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

if st.session_state.get('role') not in ('user', 'student'):
    st.error('You do not have access to this page.')
    st.stop()

USER_ID = st.session_state['user_id']

# Three open reports naming you escalates to the RA.
STRIKE_LIMIT = 3

# Validated against the light chart surface: protan ΔE 10.4, tritan 25.3, both above
# the 3:1 contrast floor. Colour marks who you are, but the axis label says so too, so
# the chart still reads without colour.
YOU_COLOR = "#00897B"
ROOMMATE_COLOR = "#B8632F"
AVG_RULE_COLOR = "#8A8A85"
GRID_COLOR = "#EDEAE4"
LABEL_INK = "#3C3C3B"


def to_date(value):
    """Flask serializes DATE/DATETIME columns as RFC 2822."""
    return parsedate_to_datetime(value).date() if value else None


st.title('My Standing')
st.caption("How close you are to an RA conversation, and what is driving it.")

standing = api_get(f"/room_report/users/{USER_ID}/standing")
if standing is None:
    st.stop()

open_strikes = standing.get('open_strikes', 0)
completion = standing.get('completion_pct')
suite_avg = standing.get('suite_avg_pct')
room_id = standing.get('RoomID')
today = date.today()

# The side panel holds a fixed width and stays against the right edge. The main column
# stretches into whatever is left, so widening the window feeds the strike track and the
# roommate chart rather than padding out the summary lists.
layout = st.container(horizontal=True, gap="medium")
main = layout.container(width="stretch")
side = layout.container(width=260)

with main:
    # ---- The strike track from the wireframe: three steps, filled as they land ----
    st.write("### Strike track")

    track = st.columns(STRIKE_LIMIT)
    for i in range(STRIKE_LIMIT):
        filled = i < open_strikes
        is_last = i == STRIKE_LIMIT - 1
        # Marker on its own line, label beneath it. Keeping them on one line made the
        # card depend on "RA notified" fitting the column, which it did not.
        marker = ":red[●]" if filled else ":gray[○]"
        label = "RA notified" if is_last and not filled else f"Strike {i + 1}"
        with track[i]:
            with st.container(border=True):
                st.markdown(f"### {marker}")
                st.markdown(f"**{label}**")

    remaining = STRIKE_LIMIT - open_strikes
    if remaining <= 0:
        # Nothing here notifies an RA -- the only path to one is the resident opening
        # Ask My RA. The strike-track label above says "RA notified" as the name of
        # the third step, not as a claim that a message went out.
        st.error("This is RA-conversation territory. Contesting a strike is the way back.")
    elif remaining == 1:
        st.warning("One more open report and this goes to your RA.")
    else:
        st.info(f"{remaining} strikes clear before this reaches your RA.")

    # ---- Score against the suite ---------------------------------------------
    st.write("### Completion rate")

    score_cols = st.columns(3)
    if completion is None:
        score_cols[0].metric("You", "—")
    else:
        delta = f"{completion - suite_avg:+.1f}" if suite_avg is not None else None
        score_cols[0].metric("You", f"{completion:.0f}%", delta=delta)
    score_cols[1].metric("Suite average",
                         "—" if suite_avg is None else f"{suite_avg:.0f}%")
    score_cols[2].metric("Tasks done / missed",
                         f"{standing.get('TasksCompleted', 0)} / "
                         f"{standing.get('TasksMissed', 0)}")

    roommates = standing.get('roommates') or []
    if roommates:
        frame = pd.DataFrame([
            {
                "Name": (f"{m['First_Name']} (you)" if m['UserID'] == USER_ID
                         else m['First_Name']),
                "Completion": m['completion_pct'] or 0.0,
                "Who": "You" if m['UserID'] == USER_ID else "Roommate",
            }
            for m in roommates
        ])

        # An explicit order keeps every layer on the same row sequence -- sorting each
        # layer by its own x would put the track and the bars in different orders.
        row_order = frame.sort_values("Completion", ascending=False)["Name"].tolist()
        frame["Track"] = 100.0

        y_axis = alt.Y(
            "Name:N",
            title=None,
            sort=row_order,
            axis=alt.Axis(domain=False, ticks=False, labelPadding=10,
                          labelColor=LABEL_INK, labelLimit=140),
        )

        # A full-width track behind each bar. Without it a resident on 0% renders as a
        # bare axis label with no row, which is exactly the case this chart exists to show.
        track = alt.Chart(frame).mark_bar(
            cornerRadiusEnd=4, height=22, color=GRID_COLOR,
        ).encode(
            x=alt.X("Track:Q", title="Completion rate (%)",
                    scale=alt.Scale(domain=[0, 100]),
                    axis=alt.Axis(grid=False, domain=False, tickCount=5,
                                  labelColor=LABEL_INK)),
            y=y_axis,
        )

        bars = alt.Chart(frame).mark_bar(cornerRadiusEnd=4, height=22).encode(
            x=alt.X("Completion:Q", scale=alt.Scale(domain=[0, 100])),
            y=y_axis,
            color=alt.Color(
                "Who:N",
                scale=alt.Scale(domain=["You", "Roommate"],
                                range=[YOU_COLOR, ROOMMATE_COLOR]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("Name:N", title="Resident"),
                alt.Tooltip("Completion:Q", title="Completion", format=".1f"),
            ],
        )

        value_labels = alt.Chart(frame).mark_text(
            align="left", dx=8, color=LABEL_INK, fontSize=12,
        ).encode(
            x=alt.X("Completion:Q", scale=alt.Scale(domain=[0, 100])),
            y=y_axis,
            text=alt.Text("Completion:Q", format=".0f"),
        )

        layers = [track, bars, value_labels]
        if suite_avg is not None:
            layers.append(
                alt.Chart(pd.DataFrame({"avg": [suite_avg]})).mark_rule(
                    color=AVG_RULE_COLOR, strokeDash=[4, 3], size=2,
                ).encode(x=alt.X("avg:Q", scale=alt.Scale(domain=[0, 100])))
            )

        st.altair_chart(
            alt.layer(*layers).properties(height=46 * len(frame) + 50),
            use_container_width=True,
        )
        if suite_avg is not None:
            st.caption(f"Dashed line marks the suite average, {suite_avg:.0f}%.")

    # ---- The strikes themselves ----------------------------------------------
    st.write("### Reports naming you")
    st.caption(
        "A strike is an open report about a chore assigned to you. Ask for one to be "
        "cleared and your roommates or RA decide."
    )

    strikes = api_get(f"/room_report/users/{USER_ID}/room_reports",
                      params={"role": "named"}, quiet=True) or []

    if not strikes:
        st.success("No reports name you. Nothing to clear.")

    for report in strikes:
        report_id = report['ReportID']
        filed = to_date(report['Time_Reported'])
        is_open = report['Status'] == 'open'

        header = f"{report.get('Task_Name') or 'Report'} · {report['Status'].title()}"
        if filed:
            header += f" · {filed.strftime('%b %d, %Y')}"

        with st.expander(header, expanded=is_open):
            # The detail route carries the full linked task, which the list view only
            # projects a name from.
            detail = api_get(f"/room_report/room_reports/{report_id}",
                             quiet=True) or report

            st.badge(report['Status'].title(),
                     color="red" if is_open else "gray")
            st.write(detail.get('Description') or "_No description given_")

            task = detail.get('task')
            if task and task.get('due_date'):
                st.caption(
                    f"Chore: {task['Task_Name']} · was due "
                    f"{to_date(task['due_date']).strftime('%B %d, %Y')}"
                )

            if not is_open:
                st.caption("This report is already closed out.")
                continue

            if st.button("Ask for this to be cleared", key=f"expunge_{report_id}",
                         type="primary"):
                # Requests carry no direct report foreign key from this side -- the
                # link is made when the request is resolved -- so the report is named
                # in the reason text.
                st.session_state['prefill_request'] = {
                    "type": "expunction",
                    "reason": (
                        f"Requesting report #{report_id} "
                        f"({detail.get('Description') or 'no description'}) be cleared."
                    ),
                }
                st.switch_page('pages/03_My_Requests.py')


# ---- Side panel: chores, requests, away, and the rules being measured against ----

with side:
    st.write("### Open chores")
    todo = (api_get(f"/user/users/{USER_ID}/tasks/todo", quiet=True)
            or {}).get('todo_tasks', [])
    if not todo:
        st.caption("Nothing outstanding.")
    for task in todo[:5]:
        due = to_date(task.get('due_date'))
        with st.container(border=True):
            st.write(task['Task_Name'])
            if due:
                st.caption(
                    f"Overdue · {due.strftime('%b %d')}" if due < today
                    else f"Due {due.strftime('%b %d')}"
                )

    # Shorter than the landing page's "Waiting on a decision" -- that heading wraps in
    # this narrower rail.
    st.write("### Pending requests")
    pending = api_get(f"/request/users/{USER_ID}/requests",
                      params={"status": "open"}, quiet=True) or []
    if not pending:
        st.caption("No open requests.")
    for req in pending[:5]:
        st.write(f"- {req['Request_Type'].replace('_', ' ').title()}")

    st.write("### Away dates")
    away = api_get(f"/away/users/{USER_ID}/away", quiet=True) or []
    upcoming = [a for a in away if to_date(a['End_Date']) >= today]
    if not upcoming:
        st.caption("None set. Marking dates keeps the rotation off your back.")
    for period in upcoming[:3]:
        st.write(
            f"- {to_date(period['Start_Date']).strftime('%b %d')} – "
            f"{to_date(period['End_Date']).strftime('%b %d')}"
        )

    if room_id:
        ra = (api_get(f"/room/rooms/{room_id}/ra", quiet=True) or {}).get('ra')
        if ra:
            st.write("### Who gets notified")
            st.write(f"{ra['First_Name']} {ra['Last_Name']}")
            st.caption(ra['Email'])

        rules = api_get("/rule/rules", params={"room_id": room_id}, quiet=True) or []
        if rules:
            with st.expander(f"House rules ({len(rules)})"):
                for rule in rules:
                    # Read each rule on its own so the panel shows the current text
                    # rather than whatever the list query happened to return.
                    current = api_get(f"/rule/rules/{rule['RuleID']}",
                                      quiet=True) or rule
                    st.write(f"- {current['Descr']}")

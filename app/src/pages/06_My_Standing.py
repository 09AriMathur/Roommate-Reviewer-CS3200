from datetime import date
from email.utils import parsedate_to_datetime

import altair as alt
import pandas as pd
import streamlit as st
from modules.api import api_get, api_write
from modules.labels import (INTERVENTION_STATUS_BADGES, REPORT_STATUS_BADGES,
                            REQUEST_IN_FLIGHT, REQUEST_STATUS_COLORS, by_due_date,
                            chore_state, to_due_date)
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

if st.session_state.get('role') != 'resident':
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
dorm_id = standing.get('DormID')
room_number = standing.get('Room_Number')
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
        "A strike is an open report about a chore assigned to you. Three of them and "
        "it reaches your RA. Only your RA can clear one."
    )

    all_reports = api_get(f"/room_report/users/{USER_ID}/room_reports",
                          params={"role": "named"}, quiet=True) or []

    # The strike track above counts open reports only. Listing every report of every
    # status underneath it meant a resident with a clean slate still read a column of
    # reports, and the reviewed and closed ones were never coming back.
    strikes = [r for r in all_reports if r['Status'] == 'open']
    settled = [r for r in all_reports if r['Status'] != 'open']

    if not strikes:
        st.success("No open reports name you. Nothing to clear.")

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

            st.caption(
                "Your RA decides this one. If they agree, the report closes and the "
                "strike comes off."
            )

            # One appeal per strike. Asking twice does not make an RA rule twice -- it
            # used to put a second copy on their desk that pointed at nothing, so
            # approving it cleared no strike and errored on the way out.
            if report.get('appeal_status') in REQUEST_IN_FLIGHT:
                st.info("You have already asked for this one. Your RA still has it.")
            elif st.button("Ask for this to be cleared", key=f"expunge_{report_id}",
                           type="primary"):
                # Filed straight from here and pointed at the report it is about in the
                # same call, so the appeal and the strike it names cannot come apart.
                # 409 is the server saying this strike already has an appeal in flight,
                # or has been ruled on since the page loaded.
                status, body = api_write("POST", "/request/requests", {
                    "Request_Type": "expunction",
                    "Requested_By_UserID": USER_ID,
                    "ReportID": report_id,
                    "Reason": (
                        f"Asking for this strike to be cleared: "
                        f"{detail.get('Description') or 'no description given'}"
                    ),
                }, expected=(409,))
                if status == 201:
                    st.toast("Sent to your RA.")
                    st.rerun()
                elif status == 409:
                    st.warning((body or {}).get(
                        "error", "That strike cannot be appealed right now."))

    # Reports an RA has already ruled on. They no longer count against the strike track,
    # but they are the record of what happened, so they stay readable.
    if settled:
        with st.expander(f"Already settled ({len(settled)})"):
            for report in settled:
                label, color = REPORT_STATUS_BADGES.get(
                    report['Status'], (report['Status'].title(), 'gray'))
                reviewed = to_date(report.get('Reviewed_At'))
                with st.container(border=True):
                    st.write(report.get('Task_Name') or 'Report')
                    st.badge(label, color=color)
                    if reviewed:
                        st.caption(f"Reviewed {reviewed.strftime('%b %d, %Y')}")


# ---- Side panel: chores, requests, away, and the rules being measured against ----

with side:
    st.write("### Open chores")
    todo = (api_get(f"/user/users/{USER_ID}/tasks/todo", quiet=True)
            or {}).get('todo_tasks', [])
    if not todo:
        st.caption("Nothing outstanding.")
    # Same five chores the landing page shows, in the same order, with the same colour.
    # This rail used to take whatever five rows MySQL happened to return first and drop
    # the state colour, so the two pages disagreed about what was next.
    for task in by_due_date(todo)[:5]:
        due = to_due_date(task)
        label, color = chore_state(task, today)
        with st.container(border=True):
            st.write(task['Task_Name'])
            st.badge(f"{label} · {due.strftime('%b %d')}" if due else label, color=color)

    # Shorter than the landing page's "Waiting on a decision" -- that heading wraps in
    # this narrower rail.
    st.write("### Pending requests")
    pending = [r for r in (api_get(f"/request/users/{USER_ID}/requests", quiet=True)
                           or [])
               if r['Status'] in REQUEST_IN_FLIGHT]
    if not pending:
        st.caption("No requests waiting on a decision.")
    else:
        st.caption("Longest waiting first — these are the ones to chase.")

    # A bare type told a resident nothing: five bullets reading "Extension, Expunction,
    # Dispute, Swap, Extension" name the form that was filled in, not what was asked for
    # or how long it has been sitting. Oldest first, because the useful question here is
    # which one has been ignored longest.
    for req in sorted(pending, key=lambda r: to_date(r['Created_At']) or today)[:5]:
        filed = to_date(req.get('Created_At'))
        waited = (today - filed).days if filed else None
        with st.container(border=True):
            type_col, age_col = st.columns([2, 1])
            type_col.badge(req['Request_Type'].replace('_', ' ').title(),
                           color=REQUEST_STATUS_COLORS.get(req['Status'], "gray"))
            if waited is not None:
                age_col.caption("today" if waited == 0 else f"{waited}d ago")
            st.caption(req.get('Reason') or "_No reason given_")
            if req['Status'] == 'in_progress':
                st.caption(":gray[Someone said they would sort this out and has not "
                           "decided it yet.]")

    st.write("### Away dates")
    away = api_get(f"/away/users/{USER_ID}/away", quiet=True) or []
    # The API hands these back newest first, so the nearest period is at the end. Taking
    # the first three off the raw list showed the three furthest out.
    upcoming = sorted([a for a in away if to_date(a['End_Date']) >= today],
                      key=lambda a: to_date(a['Start_Date']))
    if not upcoming:
        st.caption("None set. Marking dates keeps the rotation off your back.")
    for period in upcoming[:3]:
        st.write(
            f"- {to_date(period['Start_Date']).strftime('%b %d')} – "
            f"{to_date(period['End_Date']).strftime('%b %d')}"
        )

    # An RA case is the sharpest thing there is about a resident's standing, and this
    # page -- the one called My Standing -- did not read them at all. A resident could
    # have an active intervention open against them and see nothing about it here.
    st.write("### RA cases")
    my_interventions = api_get("/intervention/interventions",
                               params={"user_id": USER_ID}, quiet=True) or []
    ongoing = [i for i in my_interventions if i['Status'] != 'closed']
    if not ongoing:
        st.caption("No open cases with your RA.")
    for case in ongoing:
        label, color = INTERVENTION_STATUS_BADGES.get(
            case['Status'], (case['Status'].title(), 'gray'))
        with st.container(border=True):
            st.badge(label, color=color)
            st.caption(case.get('Description') or "No description given.")

    if dorm_id is not None and room_number is not None:
        ra = (api_get(f"/room/dorms/{dorm_id}/rooms/{room_number}/ra",
                      quiet=True) or {}).get('ra')
        if ra:
            st.write("### Who gets notified")
            st.write(f"{ra['First_Name']} {ra['Last_Name']}")
            st.caption(ra['Email'])

        rules = api_get("/rule/rules",
                        params={"dorm_id": dorm_id, "room_number": room_number},
                        quiet=True) or []
        if rules:
            with st.expander(f"House rules ({len(rules)})"):
                for rule in rules:
                    # Read each rule on its own so the panel shows the current text
                    # rather than whatever the list query happened to return.
                    current = api_get(f"/rule/rules/{rule['RuleID']}",
                                      quiet=True) or rule
                    st.write(f"- {current['Descr']}")

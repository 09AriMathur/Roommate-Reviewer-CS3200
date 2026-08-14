from datetime import datetime, date, timedelta
from email.utils import parsedate_to_datetime

import altair as alt
import pandas as pd
import streamlit as st
from modules.api import api_get, api_write
from modules.labels import REPORT_STATUS_BADGES, chore_state, is_reportable
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

if st.session_state.get('role') != 'resident':
    st.error('You do not have access to this page.')
    st.stop()

USER_ID = st.session_state['user_id']

# Freeze the "new report" timestamp for this session so it reflects when the
# user opened the form, not the time of the most recent rerun.
if 'report_draft_time' not in st.session_state:
    st.session_state['report_draft_time'] = datetime.now()

user = api_get(f"/user/users/{USER_ID}")
if user is None:
    st.stop()

roommates = (api_get(f"/user/users/{USER_ID}/roommates", quiet=True)
             or {}).get('roommates', [])

# Used only to put names on rows -- a report names a chore, and the chore names an
# assignee who is one of these people.
group = [user] + roommates
member_by_id = {member['UserID']: member for member in group}

today = date.today()

dorm_name = None
if user.get('DormID') is not None:
    dorm = api_get(f"/dorm/dorms/{user['DormID']}", quiet=True)
    dorm_name = (dorm or {}).get('Dorm_Name')

# Chores this resident has already reported, whatever became of that report. Filtering
# this to open reports only meant a chore came back onto the menu the moment the RA ruled
# on it -- so a dismissed report could be refiled immediately, against the ruling. The API
# refuses the second one, so offering it would only produce a 409.
already_reported = {
    report['TaskID']
    for report in (api_get(f"/room_report/users/{USER_ID}/room_reports",
                           params={"role": "filed"}, quiet=True) or [])
    if report.get('TaskID') is not None
}

# Only a roommate's chores are reportable -- never your own, which is why this loops
# over `roommates` and not `group`. Pulled per-member since assigned tasks are only
# exposed per-user.
open_tasks = []
for member in roommates:
    member_tasks = (api_get(f"/user/users/{member['UserID']}/tasks/assigned", quiet=True)
                     or {}).get('assigned_tasks', [])
    open_tasks.extend(t for t in member_tasks
                      if is_reportable(t, today) and t['Task_ID'] not in already_reported)

# Most recently due first. There is no recency window: an overdue chore stays reportable
# until it is done or marked missed, and a 14-day cut-off here hid chores the API would
# still accept a report on -- and hid the reports themselves from the list below while
# My Standing went on counting them as strikes.
open_tasks.sort(
    key=lambda t: parsedate_to_datetime(t['due_date']).date() if t.get('due_date') else date.min,
    reverse=True,
)

# Reports this resident filed. This page is where you report someone, so the list under
# it is the record of what you have reported and where each one got to. It used to show
# every report naming anyone in the suite, which meant your own strikes were listed here
# as well -- and those already have a home on My Standing, under a strike track that
# explains what they cost you. Two pages showing the same rows meant neither said clearly
# what it was for.
reports = api_get(f"/room_report/users/{USER_ID}/room_reports",
                  params={"role": "filed"}, quiet=True) or []

# Most recent first. No recency window: a report stands until an RA rules on it.
reports.sort(key=lambda r: parsedate_to_datetime(r['Time_Reported']), reverse=True)


def format_task_option(task):
    assignee = member_by_id.get(task['Assigned_UserID'])
    who = f"{assignee['First_Name']} {assignee['Last_Name']}" if assignee else "Unassigned"
    due = parsedate_to_datetime(task['due_date']).strftime('%b %d') if task.get('due_date') else "no due date"
    return f"{task['Task_Name']} — {who} — Due {due} — {chore_state(task, today)[0]}"


def format_report_time(raw):
    reported_at = parsedate_to_datetime(raw)
    return reported_at.strftime('%b %d, %I:%M %p')


def render_report_row(report):
    assignee = member_by_id.get(report.get('Assigned_UserID'))
    assignee_name = f"{assignee['First_Name']} {assignee['Last_Name']}" if assignee else "Unknown"

    with st.container(border=True):
        name_col, time_col = st.columns([3, 2])
        with name_col:
            st.markdown(f"**{report.get('Task_Name', 'Untitled task')}**")
            label, color = REPORT_STATUS_BADGES.get(report['Status'], (report['Status'], 'gray'))
            st.badge(label, color=color)
        with time_col:
            # Three different dates hang off one report -- when the chore was due, when
            # the report was filed, and when it was reviewed. Showing one unlabelled left
            # a reviewed report looking as though the review predated the deadline.
            st.markdown(f"Filed {format_report_time(report['Time_Reported'])}")
            if report.get('due_date'):
                st.caption(
                    f"Chore was due "
                    f"{parsedate_to_datetime(report['due_date']).strftime('%b %d, %Y')}"
                )
            if report.get('Reviewed_At'):
                st.caption(
                    f"Reviewed {format_report_time(report['Reviewed_At'])}"
                )
            st.caption(f"Assigned to {assignee_name}")
        if report.get('Description'):
            st.caption(report['Description'])


st.title("Chore Reports")
st.caption(
    f"{dorm_name + ' — ' if dorm_name else ''}Flag a roommate's chore that did not "
    "happen. Your RA rules on it. Reports naming *you* are on My Standing."
)

reports_col, new_report_col = st.columns([2, 3])

with reports_col:
    with st.container(border=True):
        st.subheader("Reports you have filed")

        # Split by where each report got to, rather than one scroll of mixed statuses.
        # The three mean different things to the person who filed them -- open is still
        # waiting on the RA, reviewed is a ruling that went your way, closed is done
        # with -- and a single list sorted by date buried the ones still outstanding
        # among months of settled ones.
        by_status = {name: [r for r in reports if r['Status'] == name]
                     for name in ('open', 'reviewed', 'closed')}
        # Anything with a status outside the three (there should be none) still has to
        # appear somewhere rather than vanishing out of the list.
        other = [r for r in reports
                 if r['Status'] not in by_status]

        if not reports:
            st.markdown(":gray[*No reports yet*]")
        else:
            st.caption(
                "**Open** is still waiting on your RA. **Reviewed** means they agreed "
                "with you. **Closed** is settled either way."
            )
            tab_names = ('open', 'reviewed', 'closed')
            tabs = st.tabs([
                f"{REPORT_STATUS_BADGES[name][0]} ({len(by_status[name])})"
                for name in tab_names
            ] + ([f"Other ({len(other)})"] if other else []))

            for tab, name in zip(tabs, tab_names):
                with tab:
                    if not by_status[name]:
                        st.markdown(f":gray[*Nothing {name}.*]")
                        continue
                    with st.container(height=440):
                        for report in by_status[name]:
                            render_report_row(report)

            if other:
                with tabs[-1], st.container(height=440):
                    for report in other:
                        render_report_row(report)

with new_report_col:
    with st.container(border=True):
        draft_time = st.session_state['report_draft_time']
        st.subheader(f"New Report @ {draft_time.strftime('%b %d, %I:%M %p')}")

        if not open_tasks:
            # Everything the server would refuse is already absent from the list, so say
            # what the list is rather than what went wrong.
            st.markdown(
                ":gray[*Nothing to report. Only your roommates' chores count, only once "
                "the due date has passed, and a chore you have already reported is not "
                "offered twice.*]"
            )
        else:
            selected_task = st.selectbox(
                "Main Report",
                options=open_tasks,
                format_func=format_task_option,
                help="Which of your roommates' overdue chores wasn't done?",
            )
            # Keyed on the draft, which is discarded once a report is filed. Without a
            # key the box kept its text through the rerun, so the next report opened
            # pre-filled with the reason for the last one -- against a different chore.
            details = st.text_area(
                "Other details...", label_visibility="collapsed",
                placeholder="Other details...",
                key=f"report_details_{draft_time.isoformat()}",
            )

            if st.button("Create Report", type="primary", use_container_width=True):
                # 409 covers the rules the server owns: reporting yourself, reporting
                # a chore that isn't due, and filing a second open report on one chore.
                # The dropdown should already prevent all three, so if one comes back
                # the data moved underneath us -- show what the API said.
                status, body = api_write("POST", "/room_report/room_reports", {
                    "TaskID": selected_task['Task_ID'],
                    "UserID": USER_ID,
                    "Description": details or f"{selected_task['Task_Name']} was not completed.",
                }, expected=(409,))
                if status == 201:
                    st.session_state.pop('report_draft_time', None)
                    st.rerun()
                elif status == 409:
                    st.warning((body or {}).get("error", "That chore can't be reported."))

with st.container(border=True):
    st.subheader("Your reports this week")

    week_start = today - timedelta(days=today.weekday())  # Monday
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    counts_by_day = {day: 0 for day in week_days}
    for report in reports:
        reported_date = parsedate_to_datetime(report['Time_Reported']).date()
        if reported_date in counts_by_day:
            counts_by_day[reported_date] += 1

    day_labels = [day.strftime('%a').upper() for day in week_days]
    chart_df = pd.DataFrame({
        "Day": day_labels,
        "Reports": [counts_by_day[day] for day in week_days],
    })

    # st.line_chart rotates the x-axis labels when they don't fit; build the
    # chart directly so the day names stay horizontal.
    week_chart = (
        alt.Chart(chart_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("Day", sort=day_labels, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Reports", title="Reports"),
        )
    )
    st.altair_chart(week_chart, use_container_width=True)

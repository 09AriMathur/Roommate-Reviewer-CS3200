from datetime import datetime, date, timedelta
from email.utils import parsedate_to_datetime

import altair as alt
import pandas as pd
import requests
import streamlit as st
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

# Hardcoded for now -- there is no real login flow yet, so we always
# show the dashboard for this UserID.
USER_ID = st.session_state['user_id']

USER_API_URL = "http://web-api:4000/user"
ROOM_API_URL = "http://web-api:4000/room"
DORM_API_URL = "http://web-api:4000/dorm"
ROOM_REPORT_API_URL = "http://web-api:4000/room_report"

# Freeze the "new report" timestamp for this session so it reflects when the
# user opened the form, not the time of the most recent rerun.
if 'report_draft_time' not in st.session_state:
    st.session_state['report_draft_time'] = datetime.now()

try:
    user_response = requests.get(f"{USER_API_URL}/users/{USER_ID}")
    user_response.raise_for_status()
    user = user_response.json()

    roommates_response = requests.get(f"{USER_API_URL}/users/{USER_ID}/roommates")
    roommates_response.raise_for_status()
    roommates = roommates_response.json().get('roommates', [])
except requests.exceptions.RequestException as e:
    st.error(f"Could not reach the API: {e}")
    st.stop()

# The whole suite: everyone whose incomplete tasks and reports should be
# visible on this page, not just the tasks/reports belonging to USER_ID.
group = [user] + roommates
member_by_id = {member['UserID']: member for member in group}

today = date.today()
cutoff = today - timedelta(days=14)

dorm_name = None
if user.get('RoomID'):
    try:
        room_response = requests.get(f"{ROOM_API_URL}/rooms/{user['RoomID']}")
        room_response.raise_for_status()
        room = room_response.json()

        dorm_response = requests.get(f"{DORM_API_URL}/dorms/{room['DormID']}")
        dorm_response.raise_for_status()
        dorm_name = dorm_response.json().get('Dorm_Name')
    except requests.exceptions.RequestException:
        dorm_name = None

# A report has to name a task, so only tasks that aren't done yet are
# reportable. Pulled per-member since assigned tasks are only exposed per-user.
open_tasks = []
try:
    for member in group:
        tasks_response = requests.get(f"{USER_API_URL}/users/{member['UserID']}/tasks/assigned")
        tasks_response.raise_for_status()
        for task in tasks_response.json().get('assigned_tasks', []):
            if task['status'] != 'done':
                open_tasks.append(task)
except requests.exceptions.RequestException as e:
    st.error(f"Could not reach the API: {e}")
    st.stop()

# Drop stale tasks (no due date can't be judged as "old", so those stay) and
# show the most recently due tasks first.
open_tasks = [
    task for task in open_tasks
    if not task.get('due_date') or parsedate_to_datetime(task['due_date']).date() >= cutoff
]
open_tasks.sort(
    key=lambda t: parsedate_to_datetime(t['due_date']).date() if t.get('due_date') else date.min,
    reverse=True,
)

# Reports naming anyone in the suite -- this is what makes a report visible to
# the whole roommate group, not just the person who filed it.
reports = []
try:
    for member in group:
        reports_response = requests.get(
            f"{ROOM_REPORT_API_URL}/users/{member['UserID']}/room_reports",
            params={"role": "named"},
        )
        reports_response.raise_for_status()
        reports.extend(reports_response.json())
except requests.exceptions.RequestException as e:
    st.error(f"Could not reach the API: {e}")
    st.stop()

# Most recent first, and drop anything older than the 14-day window.
reports = [
    r for r in reports
    if parsedate_to_datetime(r['Time_Reported']).date() >= cutoff
]
reports.sort(key=lambda r: parsedate_to_datetime(r['Time_Reported']), reverse=True)


TASK_STATUS_LABELS = {
    'todo': 'To Do',
    'in_progress': 'In Progress',
    'missed': 'Missed',
}


def format_task_option(task):
    assignee = member_by_id.get(task['Assigned_UserID'])
    who = f"{assignee['First_Name']} {assignee['Last_Name']}" if assignee else "Unassigned"
    status_label = TASK_STATUS_LABELS.get(task['status'], task['status'])
    due = parsedate_to_datetime(task['due_date']).strftime('%b %d') if task.get('due_date') else "no due date"
    return f"{task['Task_Name']} — {who} — Due {due} — {status_label}"


def format_report_time(raw):
    reported_at = parsedate_to_datetime(raw)
    return f"{reported_at.strftime('%a')} @ {reported_at.strftime('%I:%M %p')}"


REPORT_STATUS_BADGES = {
    'open': ('Open', 'red'),
    'reviewed': ('Reviewed', 'blue'),
    'closed': ('Closed', 'green'),
}


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
            st.markdown(format_report_time(report['Time_Reported']))
            st.caption(f"Assigned to {assignee_name}")
        if report.get('Description'):
            st.caption(report['Description'])


st.title("Reports")
st.caption(f"{dorm_name + ' — ' if dorm_name else ''}Chore reports for your roommate group")

reports_col, new_report_col = st.columns([2, 3])

with reports_col:
    with st.container(border=True):
        st.subheader("Reports")
        with st.container(height=500):
            if not reports:
                st.markdown(":gray[*No reports yet*]")
            else:
                for report in reports:
                    render_report_row(report)

with new_report_col:
    with st.container(border=True):
        draft_time = st.session_state['report_draft_time']
        st.subheader(f"New Report @ {draft_time.strftime('%b %d, %I:%M %p')}")

        if not open_tasks:
            st.markdown(":gray[*Nothing to report — every task is done!*]")
        else:
            selected_task = st.selectbox(
                "Main Report",
                options=open_tasks,
                format_func=format_task_option,
                help="Which task did you notice wasn't done?",
            )
            details = st.text_area("Other details...", label_visibility="collapsed", placeholder="Other details...")

            if st.button("Create Report", type="primary", use_container_width=True):
                create_response = requests.post(
                    f"{ROOM_REPORT_API_URL}/room_reports",
                    json={
                        "TaskID": selected_task['Task_ID'],
                        "UserID": USER_ID,
                        "Description": details or f"{selected_task['Task_Name']} was not completed.",
                    },
                )
                create_response.raise_for_status()
                st.session_state.pop('report_draft_time', None)
                st.rerun()

with st.container(border=True):
    st.subheader("Reports This Week")

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

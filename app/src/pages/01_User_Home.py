from datetime import datetime, date, timedelta
from email.utils import parsedate_to_datetime

import requests
import streamlit as st
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

# Hardcoded for now -- there is no real login flow yet, so we always
# show the dashboard for this UserID.
USER_ID = st.session_state['user_id']

USER_API_URL = "http://web-api:4000/user"
TASK_API_URL = "http://web-api:4000/task"

# Record the moment this user session landed on the page. Only set it
# once so it reflects login time, not the time of the most recent rerun.
if 'login_time' not in st.session_state:
    st.session_state['login_time'] = datetime.now()

login_time = st.session_state['login_time']

try:
    user_response = requests.get(f"{USER_API_URL}/users/{USER_ID}")
    user_response.raise_for_status()
    user = user_response.json()

    tasks_response = requests.get(f"{USER_API_URL}/users/{USER_ID}/tasks/assigned")
    tasks_response.raise_for_status()
    assigned_tasks = tasks_response.json().get('assigned_tasks', [])

    roommates_response = requests.get(f"{USER_API_URL}/users/{USER_ID}/roommates")
    roommates_response.raise_for_status()
    roommates = roommates_response.json().get('roommates', [])
except requests.exceptions.RequestException as e:
    st.error(f"Could not reach the API: {e}")
    st.stop()

assignee_options = [user] + roommates

st.title(f"Welcome Back, {user['First_Name']}.")
st.caption(f"Logged in on {login_time.strftime('%A, %B %d, %Y at %I:%M %p')}")

today = date.today()

# Sunday-to-Saturday window containing today. date.weekday() is Monday=0..Sunday=6,
# so this shifts the index to make Sunday the first day of the week.
week_start = today - timedelta(days=(today.weekday() + 1) % 7)
week_end = week_start + timedelta(days=6)
week_days = [week_start + timedelta(days=i) for i in range(7)]

tasks_by_day = {day: [] for day in week_days}
for task in assigned_tasks:
    if not task.get('due_date'):
        continue
    due_date = parsedate_to_datetime(task['due_date']).date()
    task['due_date'] = due_date
    if due_date in tasks_by_day:
        tasks_by_day[due_date].append(task)

for day in week_days:
    tasks_by_day[day].sort(key=lambda t: t['Task_Name'])


STATUS_BADGES = {
    'todo': ('To Do', 'gray'),
    'in_progress': ('In Progress', 'blue'),
    'done': ('Done', 'green'),
    'missed': ('Missed', 'red'),
}


def render_task_row(task):
    is_done = task['status'] == 'done'
    is_overdue = task['due_date'] < today and task['status'] not in ('done', 'missed')

    with st.container(border=True):
        name_col, status_col, check_col = st.columns([5, 2, 1])
        with name_col:
            if is_overdue:
                st.markdown(
                    f"<span style='color:#b00020;background-color:#fdecea;"
                    f"padding:2px 8px;border-radius:4px;font-weight:600;'>"
                    f"{task['Task_Name']}</span>",
                    unsafe_allow_html=True,
                )
            else:
                task_label = f"~~{task['Task_Name']}~~" if is_done else task['Task_Name']
                st.markdown(task_label)
        with status_col:
            if is_overdue:
                st.badge("Overdue", color="red")
            else:
                label, color = STATUS_BADGES.get(task['status'], (task['status'], 'gray'))
                st.badge(label, color=color)
        with check_col:
            checked = st.checkbox(
                "Done",
                value=is_done,
                key=f"task_done_{task['Task_ID']}",
                label_visibility="collapsed",
            )
            if checked != is_done:
                requests.put(
                    f"{TASK_API_URL}/tasks/{task['Task_ID']}",
                    json={"Status": "done" if checked else "todo"},
                )
                st.rerun()


@st.dialog("New Task")
def open_new_task_dialog():
    new_task_name = st.text_input("Task name")
    new_due_date = st.date_input("Due date", value=today, min_value=week_start, max_value=week_end)
    assignee = st.selectbox(
        "Assign to",
        options=assignee_options,
        index=0,
        format_func=lambda u: "Myself" if u['UserID'] == USER_ID else f"{u['First_Name']} {u['Last_Name']}",
    )

    if st.button("New Task +", use_container_width=True):
        if not new_task_name:
            st.error("Please enter a task name.")
        else:
            create_response = requests.post(
                f"{TASK_API_URL}/tasks",
                json={
                    "Task_Name": new_task_name,
                    "due_date": new_due_date.isoformat(),
                    "Created_UserID": USER_ID,
                },
            )
            create_response.raise_for_status()
            new_task_id = create_response.json()["TaskID"]

            requests.put(
                f"{TASK_API_URL}/tasks/{new_task_id}",
                json={"Assigned_UserID": assignee['UserID']},
            )
            st.rerun()


tasks_col, roommates_col = st.columns([3, 1])

with tasks_col:
    with st.container(border=True, gap="xsmall"):
        week_range = f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
        st.subheader(f"This Week ({week_range})")

        for day in week_days:
            st.markdown(f"**{day.strftime('%A, %b %d')}**")
            day_tasks = tasks_by_day[day]
            if not day_tasks:
                st.markdown(":gray[*No tasks*]")
            else:
                for task in day_tasks:
                    render_task_row(task)
            st.divider()

        if st.button("New Task +", use_container_width=True):
            open_new_task_dialog()

with roommates_col:
    with st.container(border=True):
        st.subheader("Roommates")
        if not roommates:
            st.markdown(":gray[*No roommates*]")
        else:
            for roommate in roommates:
                st.markdown(f"{roommate['First_Name']} {roommate['Last_Name']}")

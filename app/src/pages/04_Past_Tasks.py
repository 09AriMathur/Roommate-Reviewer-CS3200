from datetime import date
from email.utils import parsedate_to_datetime

import requests
import streamlit as st
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

USER_ID = st.session_state['user_id']

USER_API_URL = "http://web-api:4000/user"
ROOM_API_URL = "http://web-api:4000/room"
TASK_API_URL = "http://web-api:4000/task"

try:
    user_response = requests.get(f"{USER_API_URL}/users/{USER_ID}")
    user_response.raise_for_status()
    user = user_response.json()
except requests.exceptions.RequestException as e:
    st.error(f"Could not reach the API: {e}")
    st.stop()

room_number = None
room_users = []
if user.get('RoomID'):
    try:
        room_response = requests.get(f"{ROOM_API_URL}/rooms/{user['RoomID']}")
        room_response.raise_for_status()
        room_number = room_response.json().get('Room_Number')

        room_users_response = requests.get(f"{ROOM_API_URL}/rooms/{user['RoomID']}/users")
        room_users_response.raise_for_status()
        room_users = room_users_response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Could not reach the API: {e}")
        st.stop()

member_by_id = {member['UserID']: member for member in room_users}

# Tasks are only exposed per-user, so pull each roommate's created and assigned
# tasks and flatten them into one room-scoped list. A task can be created by
# one roommate and assigned to another, so dedupe by Task_ID to avoid
# double-counting it.
tasks_by_id = {}
try:
    for member in room_users:
        tasks_response = requests.get(f"{USER_API_URL}/users/{member['UserID']}/tasks")
        tasks_response.raise_for_status()
        member_tasks = tasks_response.json()
        for task in member_tasks.get('created_tasks', []) + member_tasks.get('assigned_tasks', []):
            tasks_by_id[task['Task_ID']] = task
except requests.exceptions.RequestException as e:
    st.error(f"Could not reach the API: {e}")
    st.stop()

today = date.today()

# This view is a history of finished business. "Done" tasks show up as soon
# as they're completed, regardless of due date. "Missed" tasks only belong
# here once their due date has actually passed.
tasks = [
    t for t in tasks_by_id.values()
    if t['status'] == 'done'
    or (
        t['status'] == 'missed'
        and t.get('due_date')
        and parsedate_to_datetime(t['due_date']).date() < today
    )
]

STATUS_LABELS = {
    'done': 'Done',
    'missed': 'Missed',
}

st.title("Past Tasks")
st.caption(f"{'Room ' + str(room_number) + ' — ' if room_number else ''}Every task created or assigned by your roommates")

if not room_users:
    st.warning("You aren't assigned to a room yet, so there's no task history to show.")
    st.stop()

filter_col, search_col = st.columns([2, 3])
with filter_col:
    selected_statuses = st.multiselect(
        "Status",
        options=list(STATUS_LABELS.keys()),
        default=list(STATUS_LABELS.keys()),
        format_func=lambda s: STATUS_LABELS.get(s, s),
    )
with search_col:
    search_term = st.text_input("Search by task name", placeholder="Search by task name...")

filtered_tasks = [
    t for t in tasks
    if t['status'] in selected_statuses
    and (not search_term or search_term.lower() in t['Task_Name'].lower())
]


def sort_key(task):
    return parsedate_to_datetime(task['due_date']) if task.get('due_date') else parsedate_to_datetime(task['Created_At'])


filtered_tasks.sort(key=sort_key, reverse=True)

metric_cols = st.columns(3)
metric_cols[0].metric("Total Tasks", len(tasks))
metric_cols[1].metric("Done", sum(1 for t in tasks if t['status'] == 'done'))
metric_cols[2].metric("Missed", sum(1 for t in tasks if t['status'] == 'missed'))

COLUMN_WIDTHS = [3, 2, 2, 2, 2, 2, 1]

header_cols = st.columns(COLUMN_WIDTHS)
for col, label in zip(header_cols, ["Task", "Created By", "Assigned To", "Status", "Due Date", "Created", ""]):
    col.markdown(f"**{label}**")

for task in filtered_tasks:
    assignee = member_by_id.get(task.get('Assigned_UserID'))
    assignee_name = f"{assignee['First_Name']} {assignee['Last_Name']}" if assignee else "Unassigned"

    creator = member_by_id.get(task.get('Created_UserID'))
    creator_name = f"{creator['First_Name']} {creator['Last_Name']}" if creator else "Unknown"

    due_date_label = parsedate_to_datetime(task['due_date']).strftime('%b %d, %Y') if task.get('due_date') else "—"
    created_label = parsedate_to_datetime(task['Created_At']).strftime('%b %d, %Y')

    row_cols = st.columns(COLUMN_WIDTHS)
    row_cols[0].markdown(task['Task_Name'])
    row_cols[1].markdown(creator_name)
    row_cols[2].markdown(assignee_name)
    row_cols[3].markdown(STATUS_LABELS.get(task['status'], task['status']))
    row_cols[4].markdown(due_date_label)
    row_cols[5].markdown(created_label)
    if row_cols[6].button("🗑️", key=f"delete_task_{task['Task_ID']}", help="Delete this task"):
        delete_response = requests.delete(f"{TASK_API_URL}/tasks/{task['Task_ID']}")
        if delete_response.ok:
            st.rerun()
        else:
            st.error("Could not delete task.")

if not filtered_tasks:
    st.markdown(":gray[*No tasks match the current filters*]")

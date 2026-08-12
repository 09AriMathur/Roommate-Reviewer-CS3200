from datetime import date, timedelta
from email.utils import parsedate_to_datetime

import streamlit as st
from modules.api import api_get, api_write
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

if st.session_state.get('role') != 'student':
    st.error('You do not have access to this page.')
    st.stop()

USER_ID = st.session_state['user_id']

STATUS_BADGES = {
    'todo': ('To Do', 'gray'),
    'in_progress': ('In Progress', 'blue'),
    'done': ('Done', 'green'),
    'missed': ('Missed', 'red'),
}


def to_date(value):
    """Flask serializes DATE columns as RFC 2822."""
    return parsedate_to_datetime(value).date() if value else None


st.title('My Chores')
st.caption(
    "Everything on your rotation. If a chore isn't going to happen, ask before the "
    "due date rather than after."
)

today = date.today()

# One call per status rather than one call filtered client-side, so each tab shows
# exactly what the API considers to be in that state.
todo = (api_get(f"/user/users/{USER_ID}/tasks/todo") or {}).get('todo_tasks', [])
missed = (api_get(f"/user/users/{USER_ID}/tasks/missed", quiet=True)
          or {}).get('missed_tasks', [])
completed = (api_get(f"/user/users/{USER_ID}/tasks/completed", quiet=True)
             or {}).get('completed_tasks', [])
created = (api_get(f"/user/users/{USER_ID}/tasks/created", quiet=True)
           or {}).get('created_tasks', [])

roommates = (api_get(f"/user/users/{USER_ID}/roommates", quiet=True)
             or {}).get('roommates', [])


@st.dialog("Ask for help with this chore")
def ask_about(task):
    st.write(f"**{task['Task_Name']}**")
    due = to_date(task.get('due_date'))
    if due:
        st.caption(f"Currently due {due.strftime('%B %d, %Y')}")

    request_type = st.radio(
        "What do you need?",
        ["extension", "swap", "dispute"],
        format_func=lambda t: {
            "extension": "More time on it",
            "swap": "Someone to take it",
            "dispute": "To contest being marked down for it",
        }[t],
    )

    proposed = None
    if request_type == "extension":
        default = max(due, today) + timedelta(days=3) if due else today + timedelta(days=3)
        proposed = st.date_input("New due date", value=default)

    if request_type == "swap" and roommates:
        target = st.selectbox(
            "Who are you asking?",
            [r['UserID'] for r in roommates],
            format_func=lambda uid: next(
                f"{r['First_Name']} {r['Last_Name']}"
                for r in roommates if r['UserID'] == uid
            ),
        )
        who = next(r['First_Name'] for r in roommates if r['UserID'] == target)
        st.caption(
            "A swap request records the chore you're giving up. Say what you'd take "
            "in return below -- that part lives in the reason."
        )
        default_reason = f"Asking {who} to take this one; happy to cover a later chore."
    else:
        default_reason = ""

    reason = st.text_area("Reason", value=default_reason, height=100)

    if st.button("Send request", type="primary", use_container_width=True):
        if not reason.strip():
            st.error("Give a reason so your roommates know what they're deciding on.")
            return

        # Unlike the seeded disputes, which challenge a report and carry no task, a
        # dispute raised from a chore is about that chore's incomplete mark, so the
        # Task_ID is set here for all three types.
        payload = {
            "Request_Type": request_type,
            "Requested_By_UserID": USER_ID,
            "Reason": reason.strip(),
            "Task_ID": task['Task_ID'],
        }
        if proposed:
            payload["Proposed_Due_Date"] = proposed.strftime("%Y-%m-%d")

        status, _ = api_write("POST", "/request/requests", payload)
        if status == 201:
            st.rerun()


def render_task(task, actionable):
    """One chore row. actionable rows can be completed or negotiated."""
    due = to_date(task.get('due_date'))
    overdue = due and due < today and task['status'] not in ('done', 'missed')

    with st.container(border=True):
        name_col, due_col, action_col = st.columns([4, 2, 3])

        with name_col:
            if task['status'] == 'done':
                st.markdown(f"~~{task['Task_Name']}~~")
            else:
                st.write(task['Task_Name'])

        with due_col:
            if overdue:
                st.badge(f"Overdue · {due.strftime('%b %d')}", color="red")
            elif due:
                label, color = STATUS_BADGES.get(task['status'],
                                                 (task['status'], 'gray'))
                st.badge(f"{label} · {due.strftime('%b %d')}", color=color)
            else:
                label, color = STATUS_BADGES.get(task['status'],
                                                 (task['status'], 'gray'))
                st.badge(label, color=color)

        if not actionable:
            return

        with action_col:
            done_col, ask_col = st.columns(2)
            if done_col.button("Mark done", key=f"done_{task['Task_ID']}",
                               use_container_width=True):
                status, _ = api_write("PUT", f"/task/tasks/{task['Task_ID']}",
                                      {"Status": "done"})
                if status == 200:
                    st.rerun()
            if ask_col.button("Ask", key=f"ask_{task['Task_ID']}",
                              use_container_width=True):
                ask_about(task)


todo_tab, missed_tab, done_tab, created_tab = st.tabs([
    f"To do ({len(todo)})",
    f"Missed ({len(missed)})",
    f"Completed ({len(completed)})",
    f"Created ({len(created)})",
])

with todo_tab:
    if not todo:
        st.success("Nothing outstanding. Enjoy it.")
    for task in sorted(todo, key=lambda t: to_date(t.get('due_date')) or date.max):
        render_task(task, actionable=True)

with missed_tab:
    if not missed:
        st.success("No missed chores on your record.")
    else:
        st.caption(
            "A missed chore can still be contested if you think it was marked unfairly."
        )
    for task in sorted(missed, key=lambda t: to_date(t.get('due_date')) or date.max):
        render_task(task, actionable=True)

with done_tab:
    if not completed:
        st.caption("Nothing completed yet.")
    for task in sorted(completed, key=lambda t: to_date(t.get('due_date')) or date.max,
                       reverse=True):
        render_task(task, actionable=False)

with created_tab:
    st.caption("Chores you set up, whoever ended up assigned to them.")
    if not created:
        st.caption("You haven't created any chores.")
    for task in sorted(created, key=lambda t: to_date(t.get('due_date')) or date.max):
        render_task(task, actionable=False)

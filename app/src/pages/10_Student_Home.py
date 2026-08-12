from datetime import date
from email.utils import parsedate_to_datetime

import streamlit as st
from modules.api import api_get
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

# The sidebar only hides links; it does not stop another role from reaching this URL.
if st.session_state.get('role') != 'student':
    st.error('You do not have access to this page.')
    st.stop()

USER_ID = st.session_state['user_id']

# The three strikes that trigger an RA conversation. Used here and on My Standing.
STRIKE_LIMIT = 3

user = api_get(f"/user/users/{USER_ID}")
if user is None:
    st.stop()

room_id = user.get('RoomID')

# Room, dorm and RA are all optional context -- a resident with no room assignment
# should still get a working page, so these stay quiet on failure.
room = api_get(f"/room/rooms/{room_id}", quiet=True) if room_id else None
dorm = api_get(f"/dorm/dorms/{room['DormID']}", quiet=True) if room else None
ra_response = api_get(f"/room/rooms/{room_id}/ra", quiet=True) if room_id else None
ra = (ra_response or {}).get('ra')

standing = api_get(f"/room_report/users/{USER_ID}/standing", quiet=True) or {}
open_requests = api_get(f"/request/users/{USER_ID}/requests",
                        params={"status": "open"}, quiet=True) or []
away_periods = api_get(f"/away/users/{USER_ID}/away", quiet=True) or []
todo = (api_get(f"/user/users/{USER_ID}/tasks/todo", quiet=True) or {}).get('todo_tasks', [])

st.title(f"Hi, {user['First_Name']}.")

context = []
if dorm:
    context.append(dorm['Dorm_Name'])
if room:
    context.append(f"Room {room['Room_Number']}")
if ra:
    context.append(f"RA {ra['First_Name']} {ra['Last_Name']}")
st.caption(" · ".join(context) if context else "No room assignment on file")

today = date.today()


def to_date(value):
    """Flask serializes DATE columns as RFC 2822, e.g. 'Wed, 13 Aug 2026 00:00:00 GMT'."""
    return parsedate_to_datetime(value).date() if value else None


# ---- The numbers that decide whether Frank is in trouble ---------------------

completion = standing.get('completion_pct')
suite_avg = standing.get('suite_avg_pct')
open_strikes = standing.get('open_strikes', 0)

with st.container(border=True):
    cols = st.columns(4)

    # A resident with no tasks at all has no percentage, which is different from 0%.
    if completion is None:
        cols[0].metric("Completion rate", "—")
    else:
        delta = None
        if suite_avg is not None:
            delta = f"{completion - suite_avg:+.1f} vs suite"
        cols[0].metric("Completion rate", f"{completion:.0f}%", delta=delta)

    cols[1].metric(
        "Open strikes",
        f"{open_strikes} of {STRIKE_LIMIT}",
        help="Three open reports naming you escalates to your RA.",
    )
    cols[2].metric("Open requests", len(open_requests))

    current_away = [
        a for a in away_periods
        if to_date(a['Start_Date']) <= today <= to_date(a['End_Date'])
    ]
    upcoming_away = [a for a in away_periods if to_date(a['Start_Date']) > today]
    if current_away:
        away_label = "Away now"
    elif upcoming_away:
        away_label = to_date(upcoming_away[-1]['Start_Date']).strftime('%b %d')
    else:
        away_label = "None set"
    cols[3].metric("Away dates", away_label)

if open_strikes >= STRIKE_LIMIT:
    st.error(
        f"You have {open_strikes} open strikes. Your RA has been notified. "
        "Contesting one is the fastest way back."
    )
elif open_strikes == STRIKE_LIMIT - 1:
    st.warning(
        f"You are one strike away from an RA conversation. "
        f"You currently have {open_strikes}."
    )

# ---- What is coming up, and what is already in flight ------------------------

left, right = st.columns(2)

with left:
    st.write("### Due next")
    dated = sorted(
        (t for t in todo if t.get('due_date')),
        key=lambda t: to_date(t['due_date']),
    )
    if not dated:
        st.caption("Nothing on your list right now.")
    for task in dated[:5]:
        due = to_date(task['due_date'])
        with st.container(border=True):
            name_col, due_col = st.columns([3, 2])
            name_col.write(task['Task_Name'])
            if due < today:
                due_col.badge(f"Overdue · {due.strftime('%b %d')}", color="red")
            else:
                due_col.badge(due.strftime('%b %d'), color="gray")

with right:
    st.write("### Waiting on a decision")
    if not open_requests:
        st.caption("You have no open requests.")
    for req in open_requests[:5]:
        with st.container(border=True):
            type_col, reason_col = st.columns([1, 3])
            type_col.badge(req['Request_Type'].replace('_', ' ').title(), color="blue")
            reason_col.write(req.get('Reason') or "_No reason given_")

st.write('### What would you like to do?')

nav_cols = st.columns(4)
if nav_cols[0].button('My Chores', type='primary', use_container_width=True):
    st.switch_page('pages/11_My_Chores.py')
if nav_cols[1].button('My Requests', type='primary', use_container_width=True):
    st.switch_page('pages/12_My_Requests.py')
if nav_cols[2].button('Away Dates', type='primary', use_container_width=True):
    st.switch_page('pages/13_My_Away.py')
if nav_cols[3].button('My Standing', type='primary', use_container_width=True):
    st.switch_page('pages/14_My_Standing.py')

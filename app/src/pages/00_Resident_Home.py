from datetime import datetime, date
from email.utils import parsedate_to_datetime

import streamlit as st
from modules.api import api_get
from modules.labels import chore_state, is_overdue
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

# The sidebar only hides links; it does not stop another role from reaching this URL.
if st.session_state.get('role') not in ('user', 'student'):
    st.error('You do not have access to this page.')
    st.stop()

USER_ID = st.session_state['user_id']

# The three strikes that trigger an RA conversation. Used here and on My Standing.
STRIKE_LIMIT = 3

# Record the moment this user session landed on the page. Only set it
# once so it reflects login time, not the time of the most recent rerun.
if 'login_time' not in st.session_state:
    st.session_state['login_time'] = datetime.now()

login_time = st.session_state['login_time']

user = api_get(f"/user/users/{USER_ID}")
if user is None:
    st.stop()

st.session_state['first_name'] = user['First_Name']

# A room is identified by its dorm plus its number, so the resident record carries
# both halves and there is no separate room id to look up.
dorm_id = user.get('DormID')
room_number = user.get('Room_Number')
has_room = dorm_id is not None and room_number is not None

# Dorm and RA are optional context -- a resident with no room assignment should still
# get a working page, so these stay quiet on failure.
dorm = api_get(f"/dorm/dorms/{dorm_id}", quiet=True) if has_room else None
ra_response = (api_get(f"/room/dorms/{dorm_id}/rooms/{room_number}/ra", quiet=True)
               if has_room else None)
ra = (ra_response or {}).get('ra')

standing = api_get(f"/room_report/users/{USER_ID}/standing", quiet=True) or {}
open_requests = api_get(f"/request/users/{USER_ID}/requests",
                        params={"status": "open"}, quiet=True) or []
away_periods = api_get(f"/away/users/{USER_ID}/away", quiet=True) or []
todo = (api_get(f"/user/users/{USER_ID}/tasks/todo", quiet=True) or {}).get('todo_tasks', [])

st.title(f"Welcome, {user['First_Name']}.")
st.caption(f"Logged in on {login_time.strftime('%A, %B %d, %Y at %I:%M %p')}")

context = []
if dorm:
    context.append(dorm['Dorm_Name'])
if has_room:
    context.append(f"Room {room_number}")
if ra:
    context.append(f"RA {ra['First_Name']} {ra['Last_Name']}")
if context:
    st.caption(" · ".join(context))

today = date.today()


def to_date(value):
    """Flask serializes DATE columns as RFC 2822, e.g. 'Wed, 13 Aug 2026 00:00:00 GMT'."""
    return parsedate_to_datetime(value).date() if value else None


# ---- The numbers that decide how this resident is doing -----------------------

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
    # Careful with the wording: nothing in the app actually notifies an RA at this
    # threshold. The only thing that reaches one is the resident opening Ask My RA
    # themselves, so this says what is true rather than claiming a message was sent.
    st.error(
        f"You have {open_strikes} open strikes, which is RA-conversation territory. "
        "Contest one, or raise it with your RA yourself."
    )
elif open_strikes == STRIKE_LIMIT - 1:
    st.warning(
        f"You are one strike away from an RA conversation. "
        f"You currently have {open_strikes}."
    )

# ---- What is coming up, and what is already in flight --------------------------

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
        label, color = chore_state(task, today)
        with st.container(border=True):
            name_col, due_col = st.columns([3, 2])
            name_col.write(task['Task_Name'])
            due_col.badge(f"{label} · {due.strftime('%b %d')}", color=color)

with right:
    st.write("### Waiting on a decision")
    if not open_requests:
        st.caption("You have no open requests.")
    for req in open_requests[:5]:
        with st.container(border=True):
            type_col, reason_col = st.columns([1, 3])
            type_col.badge(req['Request_Type'].replace('_', ' ').title(), color="blue")
            reason_col.write(req.get('Reason') or "_No reason given_")

# ---- Who else lives here, and what they still owe -------------------------------

# A resident could previously see their own list and nothing else, which makes a shared
# rotation impossible to judge -- there was no way to tell whether the suite was pulling
# its weight without opening Chore Reports and reading the reportable list.
st.write("### Around the suite")

roommates = (api_get(f"/user/users/{USER_ID}/roommates", quiet=True)
             or {}).get('roommates', [])

if not roommates:
    st.caption("You have no roommates on file.")
else:
    st.caption(
        "What your suitemates still have open. An overdue chore is the one thing you can "
        "file a report about, on the Chore Reports page."
    )

for mate in roommates:
    # Chores in play only. Their finished ones are their business, and a count that
    # included them would not say anything about what is outstanding.
    mate_tasks = (api_get(f"/user/users/{mate['UserID']}/tasks/assigned",
                          params={"status": "todo,in_progress"}, quiet=True)
                  or {}).get('assigned_tasks', [])
    mate_due = sorted(to_date(t['due_date']) for t in mate_tasks if t.get('due_date'))
    overdue_count = sum(1 for t in mate_tasks if is_overdue(t, today))

    with st.container(border=True):
        name_col, count_col, due_col = st.columns([3, 2, 2])
        name_col.write(f"{mate['First_Name']} {mate['Last_Name']}")
        count_col.write(f"{len(mate_tasks)} open")

        if overdue_count:
            due_col.badge(f"{overdue_count} overdue · {mate_due[0].strftime('%b %d')}",
                          color="red")
        elif mate_due:
            due_col.badge(f"Next {mate_due[0].strftime('%b %d')}", color="gray")
        elif mate_tasks:
            due_col.caption("No due dates set")
        else:
            due_col.caption("All clear")


# ---- Everywhere else a resident can go -----------------------------------------

st.write('### What would you like to do today?')

# Bordered columns give each row of cards a matching height, which keeps the
# buttons level -- but only while the descriptions all wrap to the same number
# of lines. Keep them to one short line each.
top_row = st.columns(3, gap='medium', border=True)
top_cards = [
    ("My Chores", "Your rotation, day by day.", "pages/01_My_Chores.py", "go_chores"),
    ("Chore Reports", "Flag a skipped chore.", "pages/02_Chore_Reports.py", "go_reports"),
    ("My Requests", "Extensions, swaps, disputes.", "pages/03_My_Requests.py", "go_requests"),
]
for col, (label, caption, page, key) in zip(top_row, top_cards):
    with col:
        st.markdown(f"**{label}**")
        st.caption(caption)
        if st.button("Open", type="primary", use_container_width=True, key=key):
            st.switch_page(page)

bottom_row = st.columns(3, gap='medium', border=True)
bottom_cards = [
    ("Ask My RA", "Ask your RA to step in.", "pages/04_Ask_My_RA.py", "go_ra"),
    ("Away Dates", "Mark the days you'll be gone.", "pages/05_My_Away.py", "go_away"),
    ("My Standing", "How close you are to an RA conversation.", "pages/06_My_Standing.py", "go_standing"),
]
for col, (label, caption, page, key) in zip(bottom_row, bottom_cards):
    with col:
        st.markdown(f"**{label}**")
        st.caption(caption)
        if st.button("Open", type="primary", use_container_width=True, key=key):
            st.switch_page(page)

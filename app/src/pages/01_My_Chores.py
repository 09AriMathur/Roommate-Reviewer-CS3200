from datetime import date, timedelta

import streamlit as st
from modules.api import api_get, api_write
from modules.labels import bucket_chores, by_due_date, chore_state, to_due_date
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

if st.session_state.get('role') != 'resident':
    st.error('You do not have access to this page.')
    st.stop()

USER_ID = st.session_state['user_id']


today = date.today()

# Every tab on this page means "assigned to me", so they all come out of one fetch and
# one split. Asking the API a separate question per tab is how "Created" ended up in the
# tab strip: it answers about chores this resident wrote for other people, so the counts
# described two different sets of chores and never added up.
user = api_get(f"/user/users/{USER_ID}")
if user is None:
    st.stop()

assigned = (api_get(f"/user/users/{USER_ID}/tasks/assigned")
            or {}).get('assigned_tasks', [])
buckets = bucket_chores(assigned, today)

roommates = (api_get(f"/user/users/{USER_ID}/roommates", quiet=True)
             or {}).get('roommates', [])
roommate_by_id = {r['UserID']: r for r in roommates}

# Roster order for the rotation: the room's residents by id, the same order the API
# hands them back and the same one the rotation walks when it hands out weeks.
roster = sorted([user] + roommates, key=lambda u: u['UserID'])


def name_for(user_id):
    if user_id == USER_ID:
        return "You"
    mate = roommate_by_id.get(user_id)
    return mate['First_Name'] if mate else "Unassigned"


@st.dialog("New chore")
def open_new_task_dialog():
    new_task_name = st.text_input("Task name")
    new_due_date = st.date_input("Due date", value=today + timedelta(days=1), min_value=today)
    assignee_id = st.selectbox(
        "Assign to",
        options=[USER_ID] + list(roommate_by_id.keys()),
        format_func=lambda uid: "Myself" if uid == USER_ID else (
            f"{roommate_by_id[uid]['First_Name']} {roommate_by_id[uid]['Last_Name']}"
        ),
    )

    repeat_weeks = st.slider("Repeat weekly for", 1, 4, 1,
                             format="%d week(s)")
    rotate = st.checkbox(
        "Pass it round the suite",
        value=repeat_weeks > 1,
        disabled=repeat_weeks == 1 or not roommates,
        help="Each week goes to the next roommate, skipping anyone whose away dates "
             "cover that day.",
    )

    # What the rotation will actually do, before committing to it. The server decides
    # for real -- this asks it the same question it will ask itself, one date at a time,
    # so the two cannot disagree about who is around.
    if repeat_weeks > 1:
        st.caption("Whose turn each week")
        previous_id = assignee_id
        preview_cols = st.columns(repeat_weeks)
        for week in range(repeat_weeks):
            due_on = new_due_date + timedelta(weeks=week)
            owner_id = previous_id

            if rotate and week > 0:
                available = (api_get(
                    f"/away/dorms/{user['DormID']}/rooms/{user['Room_Number']}/available",
                    params={"on_date": due_on.isoformat()}, quiet=True,
                ) or {}).get('available', [])
                here = {u['UserID'] for u in available}
                ids = [u['UserID'] for u in roster]
                start = ids.index(previous_id) + 1 if previous_id in ids else 0
                owner_id = next(
                    (ids[(start + step) % len(ids)] for step in range(len(ids))
                     if ids[(start + step) % len(ids)] in here),
                    ids[start % len(ids)],
                )

            with preview_cols[week]:
                st.caption(due_on.strftime('%b %d'))
                st.badge(name_for(owner_id),
                         color="violet" if owner_id != assignee_id else "green")
            previous_id = owner_id

    if st.button("Create chore", type="primary", use_container_width=True):
        if not new_task_name:
            st.error("Please enter a task name.")
            return

        # One call now assigns as it creates. It used to POST unassigned and then PUT
        # the assignee, so a failed second call left a chore on nobody's list.
        status, _ = api_write("POST", "/task/tasks", {
            "Task_Name": new_task_name,
            "due_date": new_due_date.isoformat(),
            "Created_UserID": USER_ID,
            "Assigned_UserID": assignee_id,
            "repeat_weeks": repeat_weeks,
            "rotate": rotate,
        })
        if status == 201:
            st.rerun()


title_col, new_task_col = st.columns([5, 1], vertical_alignment="bottom")
with title_col:
    st.title('My Chores')
    st.caption(
        "The four tabs are the chores assigned to you, each one in exactly one of them. "
        "The whole suite's rotation is further down. If a chore isn't going to happen, "
        "ask before the due date rather than after."
    )
with new_task_col:
    if st.button("New chore +", type="primary", use_container_width=True):
        open_new_task_dialog()


@st.dialog("Ask for help with this chore")
def ask_about(task):
    st.write(f"**{task['Task_Name']}**")
    due = to_due_date(task)
    if due:
        st.caption(f"Currently due {due.strftime('%B %d, %Y')}")

    # What can be asked for depends on where the chore stands. A missed chore has already
    # been marked down, so the only thing left is to contest that; more time on a deadline
    # that has already been ruled on is not a thing to ask for. An open chore has not been
    # marked down yet, so there is nothing to dispute.
    options = (["dispute"] if task['status'] == 'missed'
               else ["extension", "swap"])

    request_type = st.radio(
        "What do you need?",
        options,
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

        # All three types here are about the chore this dialog was opened from -- a
        # dispute contests that chore's missed mark -- so Task_ID is set on each of them.
        # Only an expunction, filed from My Standing against a report, carries none.
        payload = {
            "Request_Type": request_type,
            "Requested_By_UserID": USER_ID,
            "Reason": reason.strip(),
            "Task_ID": task['Task_ID'],
        }
        if proposed:
            payload["Proposed_Due_Date"] = proposed.strftime("%Y-%m-%d")

        # 409 is the server saying this chore already has a request of this kind waiting
        # on a decision. That is a normal thing to run into from here -- the Ask button
        # sits on every chore whether or not you have asked about it before -- so it
        # reads as a note rather than a failure.
        status, body = api_write("POST", "/request/requests", payload,
                                 expected=(409,))
        if status == 201:
            st.rerun()
        elif status == 409:
            st.warning((body or {}).get("error", "That request has already been filed."))


def render_task(task, can_complete=False, can_ask=False):
    """One chore row.

    The two permissions are separate because a missed chore is not completable --
    it has already been marked down, and letting a resident quietly flip it to done
    erases the record. Contesting it is the proper route, so Ask stays available.
    """
    due = to_due_date(task)
    label, color = chore_state(task, today)

    with st.container(border=True):
        name_col, due_col, action_col = st.columns([4, 2, 3])

        with name_col:
            if task['status'] == 'done':
                st.markdown(f"~~{task['Task_Name']}~~")
            else:
                st.write(task['Task_Name'])

        with due_col:
            st.badge(f"{label} · {due.strftime('%b %d')}" if due else label,
                     color=color)

        if not (can_complete or can_ask):
            return

        with action_col:
            done_col, ask_col = st.columns(2)
            if can_complete and done_col.button(
                    "Mark done", key=f"done_{task['Task_ID']}",
                    use_container_width=True):
                status, _ = api_write("PUT", f"/task/tasks/{task['Task_ID']}",
                                      {"Status": "done"})
                if status == 200:
                    st.rerun()
            if can_ask and ask_col.button("Ask", key=f"ask_{task['Task_ID']}",
                                          use_container_width=True):
                ask_about(task)


# Four buckets, every chore assigned to this resident in exactly one of them, so the
# counts add up to the list the API returned.
todo_tab, overdue_tab, missed_tab, done_tab = st.tabs([
    f"To do ({len(buckets['upcoming'])})",
    f"Overdue ({len(buckets['overdue'])})",
    f"Missed ({len(buckets['missed'])})",
    f"Completed ({len(buckets['completed'])})",
])

with todo_tab:
    if not buckets['upcoming']:
        st.success("Nothing coming up. Enjoy it.")
    for task in by_due_date(buckets['upcoming']):
        render_task(task, can_complete=True, can_ask=True)

with overdue_tab:
    # Overdue used to sit inside To do, visible only as a red badge, while roommates
    # were already being offered these same chores to report.
    if not buckets['overdue']:
        st.success("Nothing past its due date.")
    else:
        st.caption(
            "Past the deadline and still open. Your roommates can file a report on any "
            "of these, so finish it or ask for more time."
        )
    for task in by_due_date(buckets['overdue']):
        render_task(task, can_complete=True, can_ask=True)

with missed_tab:
    if not buckets['missed']:
        st.success("No missed chores on your record.")
    else:
        st.caption(
            "A missed chore can still be contested if you think it was marked unfairly."
        )
    # No Mark done here: the chore is already on the record, and quietly flipping it
    # to done would erase a miss your roommates may have reported. Ask -> dispute.
    for task in by_due_date(buckets['missed']):
        render_task(task, can_ask=True)

with done_tab:
    if not buckets['completed']:
        st.caption("Nothing completed yet.")
    for task in by_due_date(buckets['completed'], reverse=True):
        render_task(task)




# ---- Missed chores the room can still cover -------------------------------------

# A missed chore is a mark on somebody's record, and that mark is permanent -- but the
# room still needs the thing done. Covering creates a *fresh* chore for whoever
# volunteers rather than reassigning the missed one: reassigning would carry the miss
# across to the volunteer and wipe it from the person who actually earned it.
st.write("### Needs covering")

dorm_id = user.get('DormID')
room_number = user.get('Room_Number')
room_tasks = (api_get(f"/room/dorms/{dorm_id}/rooms/{room_number}/tasks", quiet=True)
              if dorm_id is not None and room_number is not None else None) or []

# A chore name already open in the room is either the next turn coming round or a cover
# somebody has taken, so it does not need covering again.
open_names = {t['Task_Name'] for t in room_tasks
              if t['status'] in ('todo', 'in_progress')}

# Your own missed chores are not here: the mark is yours and covering your own would be
# marking your own homework. This is what a roommate can do about a miss besides report it.
theirs_missed = [t for t in room_tasks
                 if t['status'] == 'missed' and t['Assigned_UserID'] != USER_ID]

uncovered = [t for t in theirs_missed if t['Task_Name'] not in open_names]

# The same chore missed twice is two marks on a record but one job for the room, so the
# rows are folded by name -- the oldest miss leads, and the count says how many there
# were. Folding them silently was why this list could show fewer chores than the Missed
# column of the chart above, with nothing on the page accounting for the difference.
covering = {}
for task in by_due_date(uncovered):
    covering.setdefault(task['Task_Name'], []).append(task)

# What the two rules above took out. Both are deliberate, and neither was visible: a
# resident counting missed chores on the suite chart and then counting cards here had no
# way to know why the two numbers disagreed.
back_on_board = sorted({t['Task_Name'] for t in theirs_missed} & open_names)
mine_missed = sum(1 for t in room_tasks
                  if t['status'] == 'missed' and t['Assigned_UserID'] == USER_ID)

if not uncovered:
    st.caption("Nothing outstanding in the room that isn't already on someone's list.")
else:
    st.caption(
        "Chores a roommate was marked down for. The mark stays on their record either "
        "way -- covering one just means the room gets it done."
    )

if back_on_board or mine_missed:
    hidden = []
    if back_on_board:
        hidden.append(
            f"{len(back_on_board)} already back on the board this rotation "
            f"({', '.join(back_on_board)})"
        )
    if mine_missed:
        hidden.append(
            f"{mine_missed} of your own, which only you can answer for"
        )
    st.caption(f":gray[Not listed: {'; '.join(hidden)}.]")

for name, group in sorted(covering.items(), key=lambda kv: to_due_date(kv[1][0]) or today):
    task = group[0]
    due = to_due_date(task)
    with st.container(border=True):
        name_col, who_col, act_col = st.columns([3, 2, 2])
        name_col.write(task['Task_Name'])
        who_col.caption(
            f"{task.get('First_Name', 'A roommate')} · missed"
            + (f" {due.strftime('%b %d')}" if due else "")
            + (f" · {len(group)} times" if len(group) > 1 else "")
        )
        if act_col.button("Cover this", key=f"cover_{task['Task_ID']}",
                          use_container_width=True):
            status, _ = api_write("POST", "/task/tasks", {
                "Task_Name": task['Task_Name'],
                "due_date": (today + timedelta(days=3)).isoformat(),
                "Created_UserID": USER_ID,
                "Assigned_UserID": USER_ID,
            })
            if status == 201:
                st.toast(f"{task['Task_Name']} is yours, due in three days.")
                st.rerun()


# ---- The rotation, as a week-by-week chart --------------------------------------

# "Created" used to be a fifth tab here, which is what made this page unreadable: it
# listed chores this resident wrote for their roommates alongside three tabs about chores
# they owe, so a resident with none of their own missed chores still saw missed chores on
# the page.
#
# What replaced it is the shape the rotation actually has. A rotation is not stored
# anywhere -- each turn is a plain Tasks row and nothing links one week to the next -- so
# it can only be seen by laying the room's chores out one week per row, one roommate per
# column. Read down a column and you have one person's record; read across and you have
# whose turn it was. A blank cell is a week that person carried nothing.
st.write("### The suite's rotation")

# How much of the chart to show at once. Far enough back to see the pattern hold, far
# enough forward to see whose turn is coming.
WEEKS_BACK, WEEKS_AHEAD = 4, 3


def week_of(day):
    """The Monday that starts the week a date falls in."""
    return day - timedelta(days=day.weekday())


if not roster or not room_tasks:
    st.caption("No chores on the board for this room yet.")
else:
    st.caption(
        "One week per row, one roommate per column. Each cell is the chore that person "
        "was given that week -- an empty cell means the chart gave them nothing that "
        "week, not that they skipped anything."
    )
    with st.expander("What the colours mean"):
        st.markdown(
            "- **To Do** — assigned, deadline still ahead.\n"
            "- **In Progress** — started, deadline still ahead.\n"
            "- **Overdue** — past its deadline and still open. It can still be finished, "
            "and finishing it is the only way it stops counting against you. Your "
            "roommates can file a report on it from here on.\n"
            "- **Missed** — a roommate reported it and your RA agreed. This is final: "
            "it stays on your record, it cannot be marked done, and **nobody else "
            "picks it up**. The next turn of that chore goes to the next person as "
            "normal. If you think it was unfair, contest it from the Missed tab.\n"
            "- **Done** — finished."
        )

    # Chores land on scattered weekdays, so they are grouped by the week they fall in
    # rather than by the day -- the rotation turns over weekly, not daily.
    by_week = {}
    for task in room_tasks:
        due = to_due_date(task)
        if due is None:
            continue
        by_week.setdefault(week_of(due), {}).setdefault(task['Assigned_UserID'], []).append(task)

    this_week = week_of(today)
    weeks = sorted(w for w in by_week
                   if this_week - timedelta(weeks=WEEKS_BACK)
                   <= w <= this_week + timedelta(weeks=WEEKS_AHEAD))

    if not weeks:
        st.caption("Nothing scheduled in this stretch of weeks.")
    else:
        widths = [1] + [3] * len(roster)

        # Every week gets its own outline, so a row reads as one week across all three
        # columns -- without them the chart was a field of chore names with nothing
        # holding a row together, and the only way to tell which week a cell belonged
        # to was to trace back to the date on the left. The current week carries a
        # heavier one, which is the part st.container cannot express on its own: border
        # is a boolean, so the weight comes from here.
        #
        # st.container(key=...) puts an st-key-<key> class on the block it renders,
        # which is the same element the border sits on, so these two rules are the
        # whole of it. The colour is primaryColor from .streamlit/config.toml --
        # Streamlit compiles the theme into hashed class names rather than CSS
        # variables, so there is nothing to read it from at runtime. If the theme
        # changes, change it here too.
        st.markdown(
            """
            <style>
            .st-key-rotation-week-now {
                border-width: 2px;
                border-color: #2C6E63;
            }
            .st-key-rotation-header {
                border-color: transparent;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        # The header goes in a bordered container of its own with that border made
        # invisible: a bordered container pads its contents, so a bare header above
        # boxed rows left the column titles 17px to the left of the cells they title.
        with st.container(border=True, key="rotation-header"):
            header = st.columns(widths, vertical_alignment="bottom")
            header[0].caption("Week of")
            for col, member in zip(header[1:], roster):
                mine = member['UserID'] == USER_ID
                col.markdown(f"**{'You' if mine else member['First_Name']}**")

        for week_start in weeks:
            is_now = week_start == this_week
            with st.container(
                border=True,
                key=("rotation-week-now" if is_now
                     else f"rotation-week-{week_start.isoformat()}"),
            ):
                cells = st.columns(widths, vertical_alignment="top")
                cells[0].markdown(
                    f"**{week_start.strftime('%b %d')}**" if is_now
                    else week_start.strftime('%b %d')
                )
                if is_now:
                    cells[0].caption("this week")

                for col, member in zip(cells[1:], roster):
                    theirs = by_week[week_start].get(member['UserID'], [])
                    if not theirs:
                        col.caption("—")
                        continue
                    for task in by_due_date(theirs):
                        due = to_due_date(task)
                        label, color = chore_state(task, today)
                        col.write(task['Task_Name'])
                        col.badge(f"{due.strftime('%a %d')} · {label}", color=color)

from collections import OrderedDict
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


# ---- The rotation itself ---------------------------------------------------------

# "Created" used to be a fifth tab here, which is what made this page unreadable: it
# listed chores this resident wrote for their roommates alongside three tabs about
# chores they owe, so a resident with none of their own missed chores still saw missed
# chores on the page. The suite's chores belong to the suite, so they live under their
# own heading, with the name of whoever is holding each one.
st.write("### The suite's rotation")

dorm_id = user.get('DormID')
room_number = user.get('Room_Number')
room_tasks = (api_get(f"/room/dorms/{dorm_id}/rooms/{room_number}/tasks", quiet=True)
              if dorm_id is not None and room_number is not None else None) or []

if not room_tasks:
    st.caption("No chores on the board for this room yet.")
else:
    st.caption(
        "Each chore and the roommates it has passed through, oldest first. This is what "
        "the rotation looks like from the outside."
    )

    # A rotation is one chore name coming round again on a different person, which is
    # exactly how the rows are shaped -- so grouping by name recovers it without the
    # schema having to record it.
    rotations = OrderedDict()
    for task in by_due_date(room_tasks):
        rotations.setdefault(task['Task_Name'], []).append(task)

    def next_in_roster(after_user_id):
        """Whoever follows this resident in the room's order, wrapping at the end."""
        ids = [u['UserID'] for u in roster]
        if after_user_id not in ids:
            return None
        return roster[(ids.index(after_user_id) + 1) % len(ids)]

    # Chores whose next turn is soonest are the ones worth reading first.
    def soonest_open(instances):
        upcoming = [to_due_date(t) for t in instances
                    if t['status'] in ('todo', 'in_progress') and to_due_date(t)]
        return min(upcoming) if upcoming else date.max

    for name, instances in sorted(rotations.items(), key=lambda kv: soonest_open(kv[1])):
        with st.container(border=True):
            st.markdown(f"**{name}**")

            # Four turns is enough to read the cycle without the page becoming a wall.
            shown = instances[-4:]
            cols = st.columns(len(shown) + 1)
            for col, task in zip(cols, shown):
                label, color = chore_state(task, today)
                due = to_due_date(task)
                who = ("You" if task['Assigned_UserID'] == USER_ID
                       else task.get('First_Name', 'Unassigned'))
                with col:
                    st.caption(f"{who} · {due.strftime('%b %d') if due else 'no date'}")
                    st.badge(label, color=color)

            # Nobody holds this chore right now, so say whose turn it would be. The
            # rotation is only implied by the rows until someone creates the next one.
            open_now = [t for t in instances if t['status'] in ('todo', 'in_progress')]
            if not open_now:
                nxt = next_in_roster(instances[-1]['Assigned_UserID'])
                if nxt:
                    who = "you" if nxt['UserID'] == USER_ID else nxt['First_Name']
                    cols[-1].caption("Next up")
                    cols[-1].badge(who.title(), color="violet")

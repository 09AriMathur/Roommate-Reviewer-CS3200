from collections import Counter
from datetime import date, timedelta
from email.utils import parsedate_to_datetime

import streamlit as st
from modules.api import api_get, api_write
from modules.labels import REQUEST_IN_FLIGHT, REQUEST_STATUS_COLORS
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

if st.session_state.get('role') != 'resident':
    st.error('You do not have access to this page.')
    st.stop()

USER_ID = st.session_state['user_id']

# The API accepts several request types, but maintenance and room_change are older
# vocabulary that still appears in existing rows. Only the four that belong to this
# persona are offered when filing; the lists below render anything.
FILEABLE_TYPES = ["extension", "dispute", "expunction", "swap"]

# Which types point at a specific chore. A dispute contests a chore having been marked
# missed, so it is about that chore and carries its Task_ID -- which is what My Chores
# has always sent. An expunction challenges a report rather than a chore, so it does not.
TYPES_NEEDING_TASK = {"extension", "swap", "dispute"}

# Roommates rule on the chore chart; the RA rules on the record. An expunction asks for a
# strike to come off and a dispute contests a chore being marked missed -- both are about
# reports, which only an RA can close.
PEER_DECIDED = {"swap", "extension"}

# Accepting one of these means taking the chore on, not just approving a request.
# 'chore_swap' was a second spelling of 'swap' in the seed data, which every page
# handling a swap had to know about; the rows now say 'swap' like the form does.
SWAP_TYPES = {"swap"}

def to_date(value):
    """Flask serializes DATE/DATETIME columns as RFC 2822."""
    return parsedate_to_datetime(value).date() if value else None


def pretty(value):
    return str(value).replace('_', ' ').title()


st.title('My Requests')
st.caption(
    # "dispute a report" was wrong and was the thing that made these two read as one:
    # a dispute contests a *chore* being marked missed. It is an expunction that is
    # about a report.
    "Ask for an extension, offer a chore swap, contest a chore you were marked down "
    "for, or ask for a strike on your record to be cleared."
)

my_requests = api_get(f"/request/users/{USER_ID}/requests")
if my_requests is None:
    st.stop()

# Which chores a request can be attached to depends on what is being asked for, and the
# two sets do not overlap. More time or a swap is about a chore still in play; a dispute
# contests a chore that has already been marked missed, so offering only the open ones
# left a resident unable to contest the very thing disputes exist for.
open_chores = (api_get(f"/user/users/{USER_ID}/tasks/assigned",
                       params={"status": "todo,in_progress"}, quiet=True)
               or {}).get('assigned_tasks', [])
missed_chores = (api_get(f"/user/users/{USER_ID}/tasks/missed", quiet=True)
                 or {}).get('missed_tasks', [])

CHORES_FOR_TYPE = {
    "extension": open_chores,
    "swap": open_chores,
    "dispute": missed_chores,
}

# The other half of a swap: what your roommates are currently holding. A swap could only
# name the chore you were giving up, so what you wanted back lived in the reason text --
# which meant a swap could be accepted without anyone agreeing what came the other way.
roommates = (api_get(f"/user/users/{USER_ID}/roommates", quiet=True)
             or {}).get('roommates', [])
roommate_names = {r['UserID']: r['First_Name'] for r in roommates}

their_chores = []
for mate in roommates:
    their_chores.extend(
        (api_get(f"/user/users/{mate['UserID']}/tasks/assigned",
                 params={"status": "todo,in_progress"}, quiet=True)
         or {}).get('assigned_tasks', [])
    )

task_labels = {t['Task_ID']: t['Task_Name']
               for t in open_chores + missed_chores + their_chores}
task_by_id = {t['Task_ID']: t for t in open_chores + missed_chores + their_chores}
task_owner = {t['Task_ID']: t.get('Assigned_UserID') for t in their_chores}

# A rotation runs the same chore name round the room week after week, so a resident
# behind on several weeks has "Take out trash" in this list three times over. Picking
# one from a list of bare names is guesswork; the deadline is what tells them apart.
def chore_label(task_id):
    task = task_by_id.get(task_id)
    if task is None:
        return f"Task {task_id}"
    due = to_date(task.get('due_date'))
    return task['Task_Name'] + (f" — was due {due.strftime('%b %d')}" if due else "")


# Chores this resident already has a request of the same kind in flight on. Asking twice
# does not get two answers -- it puts a second row in front of whoever decides, and
# whichever they act on, the other is left pointing at a chore that has already moved.
# The server refuses the second one; offering it here would only produce a 409.
in_flight_on = {}
for pending_request in my_requests:
    if (pending_request['Status'] in REQUEST_IN_FLIGHT
            and pending_request.get('Task_ID') is not None):
        in_flight_on.setdefault(pending_request['Request_Type'], set()).add(
            pending_request['Task_ID'])


# ---- Filing a new request ----------------------------------------------------

@st.dialog("File a request")
def file_request(default_type="extension", default_reason=""):
    request_type = st.selectbox(
        "What are you asking for?",
        FILEABLE_TYPES,
        index=FILEABLE_TYPES.index(default_type),
        format_func=pretty,
    )

    task_id = None
    eligible = CHORES_FOR_TYPE.get(request_type, [])
    already_asked = in_flight_on.get(request_type, set())
    choosable = [t for t in eligible if t['Task_ID'] not in already_asked]
    waiting = len(eligible) - len(choosable)

    if request_type in TYPES_NEEDING_TASK:
        if not choosable:
            if waiting:
                st.warning(
                    f"Every chore you could ask about already has an open "
                    f"{request_type} request waiting on a decision."
                )
            else:
                st.warning(
                    "You have no missed chores to contest." if request_type == "dispute"
                    else "You have no open chores to attach a request to."
                )
        else:
            task_id = st.selectbox(
                "Which chore?",
                [t['Task_ID'] for t in choosable],
                format_func=chore_label,
            )
            if waiting:
                st.caption(
                    f"{waiting} more not shown -- you already have an open "
                    f"{request_type} request on {'them' if waiting > 1 else 'it'}."
                )

    # An extension or a swap is a request about a specific chore. Filing one with no
    # chore attached used to be possible -- only the reason was checked -- and produced a
    # request nobody could act on, since there was nothing to move or reschedule. With
    # nothing to attach, the rest of the form has nothing to describe, so it comes out
    # disabled rather than accepting input that cannot be submitted.
    blocked = request_type in TYPES_NEEDING_TASK and task_id is None

    proposed = None
    if request_type == "extension":
        proposed = st.date_input("New due date", value=date.today() + timedelta(days=3),
                                 disabled=blocked)

    offered_task_id = None
    if request_type == "swap" and not blocked:
        if not their_chores:
            st.caption("Your roommates have nothing open to trade for right now.")
        else:
            want_back = st.checkbox("Ask for one of theirs in return", value=True)
            if want_back:
                offered_task_id = st.selectbox(
                    "Which of theirs do you want?",
                    [t['Task_ID'] for t in their_chores],
                    format_func=lambda tid: (
                        f"{chore_label(tid)} — "
                        f"{roommate_names.get(task_owner.get(tid), 'a roommate')}"
                    ),
                )

        # Spelled out, because a trade agreed in free text is a trade nobody can enforce.
        if offered_task_id:
            st.info(
                f"You give **{task_labels.get(task_id, '—')}** and take "
                f"**{task_labels.get(offered_task_id)}** from "
                f"{roommate_names.get(task_owner.get(offered_task_id), 'them')}."
            )
        else:
            st.caption(
                f"You give **{task_labels.get(task_id, '—')}** and ask for nothing back."
            )

    reason = st.text_area("Reason", value=default_reason, height=110, disabled=blocked)

    if st.button("Submit request", type="primary", use_container_width=True,
                 disabled=blocked):
        if not reason.strip():
            st.error("Give a reason so your roommates know what they're deciding on.")
            return

        # The button is disabled in this case, so this is a guard against the chore
        # disappearing between the dialog opening and the press, not a normal path.
        if request_type in TYPES_NEEDING_TASK and task_id is None:
            st.error("Pick the chore this request is about.")
            return

        payload = {
            "Request_Type": request_type,
            "Requested_By_UserID": USER_ID,
            "Reason": reason.strip(),
        }
        if offered_task_id:
            payload["Offered_Task_ID"] = offered_task_id
        if task_id:
            payload["Task_ID"] = task_id
        if proposed:
            payload["Proposed_Due_Date"] = proposed.strftime("%Y-%m-%d")

        status, _ = api_write("POST", "/request/requests", payload)
        if status == 201:
            st.rerun()


if st.button("File a new request", type="primary"):
    file_request()


# ---- My own totals, then the building for context ----------------------------

# /request/requests/stats is an ungrouped count over the whole Requests table. Three
# of these tiles used to read from it while sitting under a heading that says "My
# Requests", so a resident with two requests saw "Resolved 190" as if it were theirs.
# The tiles that describe you are now counted from your own rows.
mine_by_status = Counter(r['Status'] for r in my_requests)

with st.container(border=True):
    cols = st.columns(4)
    cols[0].metric("Requests I've filed", len(my_requests))
    # 'in_progress' had no tile, so the other three never added up to the first one --
    # a request someone had picked up simply stopped being counted anywhere.
    cols[1].metric(
        "Mine still waiting",
        sum(mine_by_status.get(s, 0) for s in REQUEST_IN_FLIGHT),
        help="Filed and not yet decided, whether or not someone has picked it up.",
    )
    cols[2].metric("Mine resolved", mine_by_status.get('resolved', 0))
    cols[3].metric("Mine rejected", mine_by_status.get('rejected', 0))

stats = api_get("/request/requests/stats", quiet=True)
if stats:
    by_status = {row['Status']: row['total'] for row in stats.get('by_status', [])}
    st.caption(
        f"Across the building: {stats.get('total', 0)} requests, "
        f"{by_status.get('open', 0)} still open."
    )


# ---- My requests -------------------------------------------------------------

# With no requests at all there is nothing to filter, and showing an empty filter
# followed by "nothing matches" reads as though something was hidden.
if my_requests:
    statuses = sorted({r['Status'] for r in my_requests})
    chosen = st.multiselect("Filter by status", statuses, default=statuses,
                            format_func=pretty)
else:
    chosen = []

visible = [r for r in my_requests if r['Status'] in chosen]

if not my_requests:
    st.info("You haven't filed any requests yet.")
elif not visible:
    st.info("Nothing matches that filter.")

for req in visible:
    rid = req['Request_ID']
    created = to_date(req['Created_At'])
    header = f"{pretty(req['Request_Type'])} · {pretty(req['Status'])}"
    if created:
        header += f" · filed {created.strftime('%b %d')}"

    with st.expander(header):
        # The detail route is what resolves the linked chore, so the row can show what
        # the request is actually about rather than a bare Task_ID.
        detail = api_get(f"/request/requests/{rid}", quiet=True) or req
        task = detail.get('task')

        st.badge(pretty(req['Status']),
                 color=REQUEST_STATUS_COLORS.get(req['Status'], "gray"))
        st.write(req.get('Reason') or "_No reason given_")

        if task:
            st.caption(f"About: {task['Task_Name']}")
        if req.get('Proposed_Due_Date'):
            st.caption(
                f"Proposed new due date: "
                f"{to_date(req['Proposed_Due_Date']).strftime('%B %d, %Y')}"
            )

        st.divider()

        if req['Status'] == 'open':
            new_reason = st.text_area("Amend your reason",
                                      value=req.get('Reason') or "",
                                      key=f"reason_{rid}", height=90)
            amend_col, withdraw_col = st.columns(2)

            if amend_col.button("Save changes", key=f"amend_{rid}",
                                use_container_width=True):
                status, _ = api_write("PUT", f"/request/requests/{rid}",
                                      {"Reason": new_reason.strip()})
                if status == 200:
                    st.rerun()
        else:
            # Withdraw stays available even here. The rule about which requests can be
            # pulled back lives on the server, and a status can change between this page
            # loading and the button being pressed, so let the API be the one to say no.
            st.caption("This request has moved on from open, so there's nothing to amend.")
            withdraw_col = st

        if withdraw_col.button("Withdraw", key=f"withdraw_{rid}",
                               use_container_width=True):
            # The API answers 409 when the request has already moved off 'open'.
            # That is a normal outcome here, not a failure worth an error banner.
            status, _ = api_write("DELETE", f"/request/requests/{rid}", expected=(409,))
            if status == 200:
                st.rerun()
            elif status == 409:
                st.warning(
                    "This request has already been acted on, so it can no longer be "
                    "withdrawn."
                )


# ---- What roommates have asked for -------------------------------------------

st.write("### Around the suite")

if not roommates:
    st.caption("You have no roommates on file.")
else:
    # One call for every request, filtered down to this suite. Cheaper than asking the
    # API once per roommate, and it keeps the suite view to a single round trip.
    all_requests = api_get("/request/requests", quiet=True) or []

    # Roommates decide the two kinds of request that are about the chore chart -- taking
    # a chore on, or giving someone longer. Disputes and expunctions are about the record
    # of a strike, which is the RA's to rule on, so they go to their queue instead of
    # sitting here collecting an Approve that used to change nothing at all.
    suite = [r for r in all_requests
             if r['Requested_By_UserID'] in roommate_names
             and r['Request_Type'] in PEER_DECIDED]

    if not suite:
        st.caption("Nobody else in your suite is waiting on you.")
    else:
        st.caption(
            "Swaps and extensions from your roommates. Whoever answers first decides it. "
            "Disputes and strike appeals go to your RA, not to you."
        )

    for req in suite[:10]:
        request_id = req['Request_ID']
        asker = roommate_names[req['Requested_By_UserID']]
        # Anything resolved or rejected is history; everything still in flight is up for
        # decision. Testing for 'open' alone left in_progress requests as dead cards --
        # they read "you would take this chore" with no way to take it, while the tile at
        # the top of this page counted them as still waiting on someone. Nothing in the
        # app moves a request into in_progress, so the only ones that exist say a
        # roommate picked it up and never came back to it.
        undecided = req['Status'] in REQUEST_IN_FLIGHT
        is_swap = (req['Request_Type'] in SWAP_TYPES
                   and req.get('Task_ID') is not None)
        # Who has the chore now, which is the only thing that says whether a decided
        # request actually did anything.
        holder = req.get('given_owner')
        given = req.get('given_name') or 'their chore'

        with st.container(border=True):
            who_col, what_col, status_col = st.columns([1, 3, 1])
            who_col.write(f"**{asker}**")
            what_col.write(
                f"{pretty(req['Request_Type'])} — {req.get('Reason') or 'No reason given'}"
            )
            status_col.badge(pretty(req['Status']),
                             color=REQUEST_STATUS_COLORS.get(req['Status'], "gray"))

            # Both halves of the trade, named. The list route carries the chore names so
            # this does not need a call per row.
            #
            # Tense follows the status. Every row used to be written as an offer -- "you
            # would take this", "approving moves that" -- including the ones already
            # decided weeks ago, so a resolved swap read as though the chore were on its
            # way to you while the suite chart still had it on the roommate who asked.
            if req['Status'] == 'resolved':
                if is_swap:
                    taker = ("you" if holder == USER_ID
                             else roommate_names.get(holder, "someone else"))
                    trade = (f" {asker} took **{req['wanted_name']}** in return."
                             if req.get('wanted_name') else "")
                    st.caption(f"Agreed — **{given}** went to {taker}.{trade}")
                elif req.get('Proposed_Due_Date'):
                    st.caption(
                        f"Agreed — **{given}** moved to "
                        f"{to_date(req['Proposed_Due_Date']).strftime('%b %d')}."
                    )
            elif req['Status'] == 'rejected':
                st.caption(f"Turned down — **{given}** stayed with {asker}.")
            elif is_swap:
                if req.get('wanted_name'):
                    st.caption(
                        f"You would take **{given}** and hand over "
                        f"**{req['wanted_name']}**."
                    )
                else:
                    st.caption(
                        f"You would take **{given}**, with nothing asked in return."
                    )
            elif req['Request_Type'] == 'extension' and req.get('Proposed_Due_Date'):
                moved_to = to_date(req['Proposed_Due_Date'])
                st.caption(
                    f"Approving moves **{given}** to {moved_to.strftime('%b %d')}."
                )

            if not undecided:
                continue

            if req['Status'] == 'in_progress':
                st.caption(
                    ":gray[In Progress means a roommate said they would sort this out "
                    "and never approved or declined it. It still counts as undecided, so "
                    "you can answer it.]"
                )

            # A chore already done or missed has nothing left to hand over.
            if is_swap and req.get('given_name') is None:
                st.caption("The chore behind this request has gone.")
                continue

            accept_col, decline_col, _ = st.columns([1, 1, 3])
            accept_label = "Take this chore" if is_swap else "Approve"

            if accept_col.button(accept_label, key=f"accept_{request_id}",
                                 type="primary", use_container_width=True):
                # One call. The API carries the request out -- moving the deadline, or
                # trading the chores both ways -- inside the same transaction, so there
                # is no window where the request reads resolved and nothing moved.
                status, body = api_write(
                    "PUT", f"/request/requests/{request_id}",
                    {"Status": "resolved", "accepted_by": USER_ID},
                )
                if status == 200:
                    if (body or {}).get('effect'):
                        st.toast(body['effect'].capitalize())
                    st.rerun()

            if decline_col.button("Decline", key=f"decline_{request_id}",
                                  use_container_width=True):
                status, _ = api_write("PUT", f"/request/requests/{request_id}",
                                      {"Status": "rejected"})
                if status == 200:
                    st.rerun()

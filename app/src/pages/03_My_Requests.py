from collections import Counter
from datetime import date, timedelta
from email.utils import parsedate_to_datetime

import streamlit as st
from modules.api import api_get, api_write
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

if st.session_state.get('role') not in ('user', 'student'):
    st.error('You do not have access to this page.')
    st.stop()

USER_ID = st.session_state['user_id']

# The API accepts seven request types, but three of them (maintenance, chore_swap,
# room_change) are older vocabulary that still appears in existing rows. Only the four
# that belong to this persona are offered when filing; the lists below render anything.
FILEABLE_TYPES = ["extension", "dispute", "expunction", "swap"]

# Which types point at a specific chore. A dispute challenges a report and an expunction
# challenges a strike, so neither carries a Task_ID.
TYPES_NEEDING_TASK = {"extension", "swap"}

# Accepting one of these means taking the chore on, not just approving a request.
# 'chore_swap' is the older spelling of the same thing and is still in the seed data.
SWAP_TYPES = {"swap", "chore_swap"}

STATUS_COLORS = {
    "open": "blue",
    "in_progress": "orange",
    "resolved": "green",
    "rejected": "red",
}


def to_date(value):
    """Flask serializes DATE/DATETIME columns as RFC 2822."""
    return parsedate_to_datetime(value).date() if value else None


def pretty(value):
    return str(value).replace('_', ' ').title()


st.title('My Requests')
st.caption(
    "Ask for an extension, offer a chore swap, dispute a report, or ask for an old "
    "strike to be cleared."
)

my_requests = api_get(f"/request/users/{USER_ID}/requests")
if my_requests is None:
    st.stop()

# Only chores still in play. "Assigned" on its own includes everything this resident has
# ever held, so the picker offered extensions and swaps on chores already marked done --
# three options against the single chore the My Chores To do tab was showing.
assigned = (api_get(f"/user/users/{USER_ID}/tasks/assigned",
                    params={"status": "todo,in_progress"}, quiet=True)
            or {}).get('assigned_tasks', [])
task_labels = {t['Task_ID']: t['Task_Name'] for t in assigned}


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
    if request_type in TYPES_NEEDING_TASK:
        if not assigned:
            st.warning("You have no assigned chores to attach a request to.")
        else:
            task_id = st.selectbox(
                "Which chore?",
                [t['Task_ID'] for t in assigned],
                format_func=lambda tid: task_labels.get(tid, f"Task {tid}"),
            )

    proposed = None
    if request_type == "extension":
        proposed = st.date_input("New due date", value=date.today() + timedelta(days=3))

    if request_type == "swap":
        st.caption(
            "Name the chore you'd take in return in your reason -- a swap request "
            "records the chore you're giving up, and your roommates agree to the rest."
        )

    reason = st.text_area("Reason", value=default_reason, height=110)

    if st.button("Submit request", type="primary", use_container_width=True):
        if not reason.strip():
            st.error("Give a reason so your roommates know what they're deciding on.")
            return

        payload = {
            "Request_Type": request_type,
            "Requested_By_UserID": USER_ID,
            "Reason": reason.strip(),
        }
        if task_id:
            payload["Task_ID"] = task_id
        if proposed:
            payload["Proposed_Due_Date"] = proposed.strftime("%Y-%m-%d")

        status, _ = api_write("POST", "/request/requests", payload)
        if status == 201:
            st.rerun()


# The My Standing page sends people here with an expunction half-written. Popping it
# rather than reading it means the dialog opens once instead of on every rerun.
prefill = st.session_state.pop('prefill_request', None)
if prefill:
    file_request(prefill.get('type', 'extension'), prefill.get('reason', ''))

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
    cols[1].metric("Mine still open", mine_by_status.get('open', 0))
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
                 color=STATUS_COLORS.get(req['Status'], "gray"))
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

roommates = (api_get(f"/user/users/{USER_ID}/roommates", quiet=True)
             or {}).get('roommates', [])
roommate_names = {r['UserID']: r['First_Name'] for r in roommates}

if not roommates:
    st.caption("You have no roommates on file.")
else:
    # One call for every request, filtered down to this suite. Cheaper than asking the
    # API once per roommate, and it keeps the suite view to a single round trip.
    all_requests = api_get("/request/requests", quiet=True) or []
    suite = [r for r in all_requests if r['Requested_By_UserID'] in roommate_names]

    if not suite:
        st.caption("Nobody else in your suite has filed a request.")
    else:
        st.caption(
            "Requests your roommates are waiting on. Whoever answers first decides it."
        )

    for req in suite[:10]:
        request_id = req['Request_ID']
        asker = roommate_names[req['Requested_By_UserID']]
        # Only an open request is still up for decision. Anything already resolved or
        # rejected is history, and the API would take a second answer without
        # complaint, so the buttons come off once it has been decided.
        undecided = req['Status'] == 'open'
        # A swap hands over a specific chore, so taking it on means reassigning that
        # chore. Without a Task_ID there is nothing to move and it is a plain approval.
        # Both spellings count: VALID_REQUEST_TYPES carries the legacy 'chore_swap'
        # alongside 'swap', and seeded rows use both for the same thing.
        is_swap = (req['Request_Type'] in SWAP_TYPES
                   and req.get('Task_ID') is not None)

        with st.container(border=True):
            who_col, what_col, status_col = st.columns([1, 3, 1])
            who_col.write(f"**{asker}**")
            what_col.write(
                f"{pretty(req['Request_Type'])} — {req.get('Reason') or 'No reason given'}"
            )
            status_col.badge(pretty(req['Status']),
                             color=STATUS_COLORS.get(req['Status'], "gray"))

            if not undecided:
                continue

            swap_task = None
            if is_swap:
                swap_detail = api_get(f"/request/requests/{request_id}", quiet=True) or {}
                swap_task = swap_detail.get('task')

                # A chore already marked done or missed has nothing left to hand over,
                # and reassigning one moves its count onto whoever pressed the button --
                # taking a finished chore would credit you with completing it.
                if (swap_task or {}).get('status') not in ('todo', 'in_progress'):
                    st.caption(
                        "This chore has already been closed out, so there is nothing "
                        "left to take on."
                    )
                    continue

                st.caption(f"Taking this on moves **{swap_task['Task_Name']}** to you.")

            accept_col, decline_col, _ = st.columns([1, 1, 3])
            accept_label = "Take this chore" if is_swap else "Approve"

            if accept_col.button(accept_label, key=f"accept_{request_id}",
                                 type="primary", use_container_width=True):
                ok = True
                if is_swap:
                    # Move the chore first. If that fails the request stays open, which
                    # is recoverable; resolving first could leave a settled request
                    # whose chore never actually changed hands.
                    #
                    # Status goes back to 'todo' in the same call. A chore taken over is
                    # a chore you now have to do, so it belongs in your To do tab -- and
                    # an in_progress chore inherited mid-way would claim you had started
                    # work you have not.
                    status, _ = api_write(
                        "PUT", f"/task/tasks/{req['Task_ID']}",
                        {"Assigned_UserID": USER_ID, "Status": "todo"},
                    )
                    ok = status == 200

                if ok:
                    status, _ = api_write("PUT", f"/request/requests/{request_id}",
                                          {"Status": "resolved"})
                    if status == 200:
                        st.rerun()

            if decline_col.button("Decline", key=f"decline_{request_id}",
                                  use_container_width=True):
                status, _ = api_write("PUT", f"/request/requests/{request_id}",
                                      {"Status": "rejected"})
                if status == 200:
                    st.rerun()

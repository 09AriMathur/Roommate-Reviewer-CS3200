import logging
logger = logging.getLogger(__name__)

from email.utils import parsedate_to_datetime

import pandas as pd
import requests
import streamlit as st
from modules.api import api_write
from modules.labels import REPORT_STATUS_BADGES, chore_state
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

# Show appropriate sidebar links for the role of the currently logged in user
SideBarLinks()

# The sidebar only hides links; it does not stop another role from reaching
# this URL. Without this, arriving without a session raised a KeyError on
# first_name rather than saying the page was off limits.
if st.session_state.get('role') != 'ra':
    st.error('You do not have access to this page.')
    st.stop()

st.title('Room Reports')
st.write(f"### Hi, {st.session_state['first_name']}.")

API_URL = "http://web-api:4000"

# Interventions are only "ongoing" while they haven't been closed out
ONGOING_INTERVENTION_STATUSES = ("pending", "active")


def api_get(path, quiet_404=False):
    """GET a backend endpoint and return the parsed JSON, or None on failure."""
    try:
        response = requests.get(f"{API_URL}{path}")
        if response.status_code == 200:
            return response.json()
        if response.status_code == 404 and quiet_404:
            return None
        st.error(f"API error on GET {path}: {response.status_code}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to the API: {e}")
        return None


def completion_score(tasks_completed, tasks_missed):
    """A user's completion score: tasks completed / (tasks completed + tasks missed).
    None (rather than 0) when a user has no completed-or-missed tasks yet, so an
    empty record doesn't get averaged in as a zero."""
    total = tasks_completed + tasks_missed
    return tasks_completed / total if total > 0 else None


def format_score(score):
    return f"{score:.0%}" if score is not None else "N/A"


# ---------------------------------------------------------------------------
# The reports themselves. This page has been called Room Reports since it was
# written and never read the Room_Reports table: a resident could file a report
# and it reached no RA surface anywhere in the app, so nothing could ever be
# ruled on and every report stayed open for ever.
# ---------------------------------------------------------------------------

RA_ID = st.session_state.get('user_id')

st.write('#### Reports on your rooms')
st.caption(
    "A resident filed these about a chore in one of your rooms. Upholding one marks "
    "that chore missed, which is what moves the resident's completion rate and their "
    "strike count."
)

report_filter = st.radio(
    "Show", ["Open", "Reviewed", "Closed"], horizontal=True,
    label_visibility="collapsed",
)

reports = api_get(
    f"/room_report/room_reports?ra_id={RA_ID}&status={report_filter.lower()}"
) or []

if not reports:
    st.success(f"No {report_filter.lower()} reports on your rooms.")

for report in reports:
    report_id = report['ReportID']
    accused = f"{report.get('accused_first') or '?'} {report.get('accused_last') or ''}".strip()
    filer = f"{report.get('filer_first') or '?'} {report.get('filer_last') or ''}".strip()
    label, color = REPORT_STATUS_BADGES.get(report['Status'],
                                            (report['Status'].title(), 'gray'))

    def when(raw):
        return parsedate_to_datetime(raw).strftime('%b %d, %Y') if raw else None

    with st.container(border=True):
        head_col, badge_col = st.columns([4, 1])
        head_col.write(
            f"**{report.get('Task_Name') or 'Report'}** — {accused}, "
            f"Room {report.get('Room_Number')}"
        )
        badge_col.badge(label, color=color)

        st.caption(
            f"Filed by {filer} on {when(report.get('Time_Reported'))}"
            + (f" · chore was due {when(report.get('due_date'))}"
               if report.get('due_date') else "")
            + (f" · reviewed {when(report.get('Reviewed_At'))}"
               if report.get('Reviewed_At') else "")
        )
        st.write(report.get('Description') or "_No description given_")

        if report['Status'] == 'open':
            # The chore's own state decides what upholding can mean. One already
            # finished cannot be marked missed without taking the credit back off
            # whoever did it, so that button goes away rather than silently doing
            # something different from what it says.
            already_settled = report.get('task_status') in ('done', 'missed')
            if report.get('task_status') == 'done':
                st.caption("This chore has since been marked done, so there is "
                           "nothing left to mark missed.")
            elif report.get('task_status') == 'missed':
                st.caption("This chore is already marked missed.")

            uphold_col, dismiss_col, _ = st.columns([1, 1, 2])
            if uphold_col.button(
                    "Uphold", key=f"uphold_{report_id}", type="primary",
                    use_container_width=True, disabled=already_settled,
                    help="Agree the chore was skipped and mark it missed."):
                status, body = api_write(
                    "PUT", f"/room_report/room_reports/{report_id}",
                    {"Status": "reviewed", "uphold": True, "ra_id": RA_ID},
                )
                if status == 200:
                    if (body or {}).get('chore_marked_missed'):
                        st.toast(f"{accused}'s chore marked missed.")
                    st.rerun()

            if dismiss_col.button(
                    "Dismiss", key=f"dismiss_{report_id}", use_container_width=True,
                    help="Close it without marking the chore down."):
                status, _ = api_write("PUT", f"/room_report/room_reports/{report_id}",
                                      {"Status": "closed", "ra_id": RA_ID})
                if status == 200:
                    st.rerun()
        else:
            if st.button("Reopen", key=f"reopen_{report_id}"):
                status, _ = api_write("PUT", f"/room_report/room_reports/{report_id}",
                                      {"Status": "open", "ra_id": RA_ID})
                if status == 200:
                    st.rerun()


# ---------------------------------------------------------------------------
# Rooms overview: every room's ID, number, dorm, whether it has an ongoing
# RA intervention, and the average completion score across its residents.
# ---------------------------------------------------------------------------

st.write('#### Rooms Overview')

# The rooms this RA is responsible for. The overview used to list all 68 rooms in the
# building, which is not a caseload -- it is a directory.
building_wide = st.toggle(
    "Show every room in the building",
    help="Off, this is the rooms you are responsible for.",
)

rooms = api_get("/room/rooms") if building_wide else api_get(f"/ra/ras/{RA_ID}/rooms")

if rooms is not None:
    # One call instead of one per RA in the building.
    users_with_intervention = {
        i["UserID"]
        for i in (api_get("/intervention/interventions") or [])
        if i["Status"] in ONGOING_INTERVENTION_STATUSES
    }

    dorm_names = {d["DormID"]: d["Dorm_Name"] for d in (api_get("/dorm/dorms") or [])}

    overview_rows = []
    for room in rooms:
        room_users = api_get(
            f"/room/dorms/{room['DormID']}/rooms/{room['Room_Number']}/users") or []

        scores = [
            completion_score(u["TasksCompleted"], u["TasksMissed"])
            for u in room_users
        ]
        scores = [s for s in scores if s is not None]
        avg_score = sum(scores) / len(scores) if scores else None

        has_intervention = any(u["UserID"] in users_with_intervention for u in room_users)

        overview_rows.append({
            "Dorm": dorm_names.get(room["DormID"], f"Dorm {room['DormID']}"),
            "Room Number": room["Room_Number"],
            "Ongoing Intervention": "Yes" if has_intervention else "No",
            "Avg Completion Score": format_score(avg_score),
        })

    if overview_rows:
        overview_df = pd.DataFrame(overview_rows).sort_values(["Dorm", "Room Number"])
        st.dataframe(overview_df, use_container_width=True, hide_index=True)
    else:
        st.info("No rooms found.")
else:
    st.error("Could not load room data from the API.")

st.divider()

# ---------------------------------------------------------------------------
# Room search: look up a single room for a detailed breakdown of its residents,
# tasks, and rules. A room is keyed by its dorm and its number, which is also the
# only way an RA would describe one -- "South Hall 201", never an internal id.
# ---------------------------------------------------------------------------

st.write('#### Look Up a Room')

all_dorms = api_get("/dorm/dorms") or []

with st.form("room_search_form"):
    dorm_col, number_col = st.columns([2, 1])
    selected_dorm = dorm_col.selectbox(
        "Building",
        options=[d["DormID"] for d in all_dorms],
        format_func=lambda did: next(
            (d["Dorm_Name"] for d in all_dorms if d["DormID"] == did), str(did)
        ),
        key="room_search_dorm",
    )
    room_number_input = number_col.text_input("Room number", key="room_search_number")
    submitted = st.form_submit_button("Search")

if submitted:
    if not room_number_input.strip().isdigit():
        st.error("Room number must be a number.")
    else:
        dorm_id = selected_dorm
        room_number = int(room_number_input)
        dorm_label = next(
            (d["Dorm_Name"] for d in all_dorms if d["DormID"] == dorm_id), f"Dorm {dorm_id}"
        )
        room = api_get(f"/room/dorms/{dorm_id}/rooms/{room_number}", quiet_404=True)

        if room is None:
            st.error(f"No room {room_number} in {dorm_label}.")
        else:
            st.write(f"### {dorm_label}, Room {room['Room_Number']}")

            # Shared name lookups, used to resolve who created/is assigned a task
            # and who made a rule, without a separate call per task or rule
            all_users = api_get("/user/users") or []
            user_names = {u["UserID"]: f"{u['First_Name']} {u['Last_Name']}" for u in all_users}
            ra_names = {ra["RA_ID"]: f"{ra['First_Name']} {ra['Last_Name']}"
                        for ra in (api_get("/ra/ras") or [])}

            room_users = api_get(
                f"/room/dorms/{dorm_id}/rooms/{room_number}/users") or []
            room_user_ids = {u["UserID"] for u in room_users}

            # --- Residents ---------------------------------------------------
            st.write("##### Residents")
            resident_rows = []
            for u in room_users:
                away_periods = api_get(f"/away/users/{u['UserID']}/away") or []
                away_str = "; ".join(
                    f"{a['Start_Date']} to {a['End_Date']}" for a in away_periods
                ) if away_periods else "None"

                resident_rows.append({
                    "Name": f"{u['First_Name']} {u['Last_Name']}",
                    "User ID": u["UserID"],
                    "Email": u["Email"],
                    "Completion Score": format_score(
                        completion_score(u["TasksCompleted"], u["TasksMissed"])
                    ),
                    "Away Period": away_str,
                })

            if resident_rows:
                st.dataframe(pd.DataFrame(resident_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No residents assigned to this room.")

            # --- Tasks ---------------------------------------------------------
            st.write("##### Tasks")
            # Asked of the room directly. This used to pull every task row in the
            # building and filter it in the browser to find one room's worth.
            room_tasks = api_get(
                f"/room/dorms/{dorm_id}/rooms/{room_number}/tasks") or []

            task_rows = [{
                "Task Name": t["Task_Name"],
                "Created By": user_names.get(t["Created_UserID"], "Unknown"),
                "Assigned To": user_names.get(t["Assigned_UserID"], "Unassigned"),
                "Due Date": t["due_date"],
                # Same wording the residents see on their own chores, rather than the
                # raw enum value.
                "Status": chore_state(t)[0],
                "Created At": t["Created_At"],
            } for t in room_tasks]

            if task_rows:
                st.dataframe(pd.DataFrame(task_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No tasks assigned to residents of this room.")

            # --- Rules -----------------------------------------------------------
            st.write("##### Rules")
            room_rules = api_get(
                f"/room/dorms/{dorm_id}/rooms/{room_number}/rules") or []

            rule_rows = [{
                "Rule ID": r["RuleID"],
                "Description": r["Descr"],
                "Made By": ra_names.get(r["RA_ID"]) or user_names.get(r["UserID"], "Unknown"),
            } for r in room_rules]

            if rule_rows:
                st.dataframe(pd.DataFrame(rule_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No rules on file for this room.")

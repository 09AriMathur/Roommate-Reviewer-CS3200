import logging
logger = logging.getLogger(__name__)

import pandas as pd
import requests
import streamlit as st
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

# Show appropriate sidebar links for the role of the currently logged in user
SideBarLinks()

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
# Rooms overview: every room's ID, number, dorm, whether it has an ongoing
# RA intervention, and the average completion score across its residents.
# ---------------------------------------------------------------------------

st.write('#### Rooms Overview')

rooms = api_get("/room/rooms")
ras = api_get("/ra/ras") or []
dorms = api_get("/dorm/dorms") or []
dorm_names = {d["DormID"]: d["Dorm_Name"] for d in dorms}

if rooms is not None:
    # RA_Intervention is only exposed per-RA, so gather every user currently
    # under an open (pending/active) intervention by looping over each RA.
    users_with_intervention = set()
    for ra in ras:
        interventions = api_get(f"/ra/ras/{ra['RA_ID']}/interventions") or []
        for intervention in interventions:
            if intervention["Status"] in ONGOING_INTERVENTION_STATUSES:
                users_with_intervention.add(intervention["UserID"])

    overview_rows = []
    for room in rooms:
        room_users = api_get(f"/room/rooms/{room['RoomID']}/users") or []

        scores = [
            completion_score(u["TasksCompleted"], u["TasksMissed"])
            for u in room_users
        ]
        scores = [s for s in scores if s is not None]
        avg_score = sum(scores) / len(scores) if scores else None

        has_intervention = any(u["UserID"] in users_with_intervention for u in room_users)

        overview_rows.append({
            "Room Number": room["Room_Number"],
            "Dorm Name": dorm_names.get(room["DormID"], "Unknown"),
            "Ongoing Intervention": "Yes" if has_intervention else "No",
            "Avg Completion Score": format_score(avg_score),
        })

    if overview_rows:
        overview_df = pd.DataFrame(overview_rows).sort_values(["Dorm Name", "Room Number"])
        st.dataframe(overview_df, use_container_width=True, hide_index=True)
    else:
        st.info("No rooms found.")
else:
    st.error("Could not load room data from the API.")

st.divider()

# ---------------------------------------------------------------------------
# Room search: look up a single room by dorm + room number for a detailed
# breakdown of its residents, tasks, and rules.
# ---------------------------------------------------------------------------

st.write('#### Look Up a Room')

dorm_name_to_id = {d["Dorm_Name"]: d["DormID"] for d in dorms}

with st.form("room_search_form"):
    search_dorm_name = st.selectbox("Dorm", list(dorm_name_to_id.keys()))
    room_number_input = st.text_input("Room Number", key="room_search_number")
    submitted = st.form_submit_button("Search")

if submitted:
    if not room_number_input.strip().isdigit():
        st.error("Room Number must be a number.")
    else:
        room_number = int(room_number_input)
        search_dorm_id = dorm_name_to_id[search_dorm_name]
        room = next(
            (r for r in (rooms or [])
             if r["DormID"] == search_dorm_id and r["Room_Number"] == room_number),
            None,
        )

        if room is None:
            st.error(f"No room numbered {room_number} found in {search_dorm_name}.")
        else:
            room_id = room["RoomID"]
            st.write(f"### Room {room['Room_Number']} ({dorm_names.get(room['DormID'], 'Unknown')})")

            # Shared name lookups, used to resolve who created/is assigned a task
            # and who made a rule, without a separate call per task or rule
            all_users = api_get("/user/users") or []
            user_names = {u["UserID"]: f"{u['First_Name']} {u['Last_Name']}" for u in all_users}
            ra_names = {ra["RA_ID"]: f"{ra['First_Name']} {ra['Last_Name']}" for ra in ras}

            room_users = api_get(f"/room/rooms/{room_id}/users") or []
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
            all_tasks = api_get("/task/tasks") or []
            room_tasks = [t for t in all_tasks if t["Assigned_UserID"] in room_user_ids]

            task_rows = [{
                "Task Name": t["Task_Name"],
                "Created By": user_names.get(t["Created_UserID"], "Unknown"),
                "Assigned To": user_names.get(t["Assigned_UserID"], "Unassigned"),
                "Due Date": t["due_date"],
                "Status": t["status"],
                "Created At": t["Created_At"],
            } for t in room_tasks]

            if task_rows:
                st.dataframe(pd.DataFrame(task_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No tasks assigned to residents of this room.")

            # --- Rules -----------------------------------------------------------
            st.write("##### Rules")
            room_rules = api_get(f"/room/rooms/{room_id}/rules") or []

            rule_rows = [{
                "Rule ID": r["RuleID"],
                "Description": r["Descr"],
                "Made By": ra_names.get(r["RA_ID"]) or user_names.get(r["UserID"], "Unknown"),
            } for r in room_rules]

            if rule_rows:
                st.dataframe(pd.DataFrame(rule_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No rules on file for this room.")

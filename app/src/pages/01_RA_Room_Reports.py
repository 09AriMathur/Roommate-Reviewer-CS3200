import logging
logger = logging.getLogger(__name__)

import pandas as pd
import requests
import streamlit as st
from modules.labels import chore_state
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

if rooms is not None:
    # RA_Intervention is only exposed per-RA, so gather every user currently
    # under an open (pending/active) intervention by looping over each RA.
    users_with_intervention = set()
    for ra in ras:
        interventions = api_get(f"/ra/ras/{ra['RA_ID']}/interventions") or []
        for intervention in interventions:
            if intervention["Status"] in ONGOING_INTERVENTION_STATUSES:
                users_with_intervention.add(intervention["UserID"])

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
            ra_names = {ra["RA_ID"]: f"{ra['First_Name']} {ra['Last_Name']}" for ra in ras}

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
            all_tasks = api_get("/task/tasks") or []
            room_tasks = [t for t in all_tasks if t["Assigned_UserID"] in room_user_ids]

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

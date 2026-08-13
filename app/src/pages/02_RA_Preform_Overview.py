import logging
logger = logging.getLogger(__name__)

import requests
import streamlit as st
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

# Show appropriate sidebar links for the role of the currently logged in user
SideBarLinks()

st.title('Performance Overview')
st.write(f"### Hi, {st.session_state['first_name']}.")

API_URL = "http://web-api:4000"


def api_get(path):
    """GET a backend endpoint and return the parsed JSON, or None on failure."""
    try:
        response = requests.get(f"{API_URL}{path}")
        if response.status_code == 200:
            return response.json()
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


rooms = api_get("/room/rooms")
ras = api_get("/ra/ras") or []
dorms = api_get("/dorm/dorms") or []
dorm_names = {d["DormID"]: d["Dorm_Name"] for d in dorms}

if rooms is not None:
    # --- Interventions, gathered by looping over each RA since RA_Intervention
    # is only exposed per-RA (no "all interventions" route exists) -------------
    all_interventions = []
    for ra in ras:
        all_interventions += api_get(f"/ra/ras/{ra['RA_ID']}/interventions") or []

    total_interventions = len(all_interventions)
    completed_interventions = sum(1 for i in all_interventions if i["Status"] == "closed")

    # --- Per-room stats: total completed/missed tasks and each room's average
    # completion score across its residents ------------------------------------
    total_completed = 0
    total_missed = 0
    room_scores = []  # (avg_score, room) for rooms with at least one scoreable user

    for room in rooms:
        room_users = api_get(
            f"/room/dorms/{room['DormID']}/rooms/{room['Room_Number']}/users") or []

        scores = []
        for u in room_users:
            total_completed += u["TasksCompleted"]
            total_missed += u["TasksMissed"]
            score = completion_score(u["TasksCompleted"], u["TasksMissed"])
            if score is not None:
                scores.append(score)

        if scores:
            room_scores.append((sum(scores) / len(scores), room))

    avg_score_across_rooms = (
        sum(s for s, _ in room_scores) / len(room_scores) if room_scores else None
    )
    best_room = max(room_scores, key=lambda pair: pair[0]) if room_scores else None
    worst_room = min(room_scores, key=lambda pair: pair[0]) if room_scores else None

    # --- Interventions ----------------------------------------------------------
    st.write('#### Interventions')
    col1, col2 = st.columns(2)
    col1.metric("Total Interventions", total_interventions)
    col2.metric("Completed Interventions", completed_interventions)

    st.divider()

    # --- Tasks & completion ------------------------------------------------------
    st.write('#### Tasks & Completion')
    col1, col2, col3 = st.columns(3)
    col1.metric("Completed Tasks (All Rooms)", total_completed)
    col2.metric("Missed Tasks (All Rooms)", total_missed)
    col3.metric("Avg Completion Score (All Rooms)", format_score(avg_score_across_rooms))

    st.divider()

    # --- Room spotlight -----------------------------------------------------------
    st.write('#### Room Spotlight')
    col1, col2 = st.columns(2)
    with col1:
        if best_room:
            score, room = best_room
            st.metric(
                "Best Performing Room",
                f"Room {room['Room_Number']} ({dorm_names.get(room['DormID'], 'Unknown')})",
                f"{format_score(score)} completion",
            )
        else:
            st.info("No room has a scoreable resident yet.")
    with col2:
        if worst_room:
            score, room = worst_room
            st.metric(
                "Worst Performing Room",
                f"Room {room['Room_Number']} ({dorm_names.get(room['DormID'], 'Unknown')})",
                f"{format_score(score)} completion",
                delta_color="inverse",
            )
        else:
            st.info("No room has a scoreable resident yet.")
else:
    st.error("Could not load room data from the API.")

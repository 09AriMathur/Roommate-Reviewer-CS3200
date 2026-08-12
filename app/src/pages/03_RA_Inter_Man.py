import logging
logger = logging.getLogger(__name__)

import pandas as pd
import requests
import streamlit as st
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

# Show appropriate sidebar links for the role of the currently logged in user
SideBarLinks()

st.title('Intervention Manager')
st.write(f"### Hi, {st.session_state['first_name']}.")

API_URL = "http://web-api:4000"

# 'pending' interventions haven't been closed out yet, so they're grouped with
# 'active' under the same header rather than getting a third table of their own
ACTIVE_STATUSES = ("pending", "active")


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


def render_interventions(rows):
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No interventions here.")


ras = api_get("/ra/ras") or []
users = api_get("/user/users") or []
rooms = api_get("/room/rooms") or []

if ras:
    ra_names = {ra["RA_ID"]: f"{ra['First_Name']} {ra['Last_Name']}" for ra in ras}
    room_by_id_of_user = {u["UserID"]: u["RoomID"] for u in users}
    room_by_room_id = {r["RoomID"]: r for r in rooms}

    # RA_Intervention is only exposed per-RA, so gather every intervention by
    # looping over each RA (no "all interventions" route exists)
    all_interventions = []
    for ra in ras:
        all_interventions += api_get(f"/ra/ras/{ra['RA_ID']}/interventions") or []

    active_rows = []
    closed_rows = []
    for i in all_interventions:
        room_id = room_by_id_of_user.get(i["UserID"])
        room = room_by_room_id.get(room_id)
        room_label = f"Room {room['Room_Number']} (Dorm {room['DormID']})" if room else "Unassigned"

        row = {
            "ID": i["RequestID"],
            "Description": i["Description"],
            "Made By": ra_names.get(i["RA"], "Unknown"),
            "Room": room_label,
            "Status": i["Status"],
        }

        if i["Status"] in ACTIVE_STATUSES:
            active_rows.append(row)
        else:
            closed_rows.append(row)

    st.write('#### Ongoing Interventions')
    render_interventions(active_rows)

    st.divider()

    st.write('#### Closed Interventions')
    render_interventions(closed_rows)
else:
    st.error("Could not load RA data from the API.")

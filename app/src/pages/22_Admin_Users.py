import logging
logger = logging.getLogger(__name__)

import streamlit as st
import requests
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')
SideBarLinks()

API = "http://web-api:4000"

st.title("User Accounts")
st.caption("Every resident's account, with drill-down into their full profile.")

# ---- Full roster --------------------------------------------------------
try:
    users = requests.get(f"{API}/user/users").json()
except requests.exceptions.RequestException as e:
    st.error(f"Could not load users from the API: {e}")
    st.stop()

st.write(f"**{len(users)}** users on record")
st.dataframe(users, use_container_width=True)

st.divider()

# ---- Drill into one profile --------------------------------------------
st.write("### Inspect a profile")

options = {
    f'{u.get("First_Name", "")} {u.get("Last_Name", "")} (ID {u["UserID"]})': u["UserID"]
    for u in users
}
if not options:
    st.info("No users to inspect.")
    st.stop()

choice = st.selectbox("Pick a user", list(options.keys()))
user_id = options[choice]

try:
    detail = requests.get(f"{API}/user/users/{user_id}").json()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tasks completed", detail.get("TasksCompleted", 0))
    c2.metric("Tasks missed", detail.get("TasksMissed", 0))
    c3.metric("Room ID", detail.get("RoomID") if detail.get("RoomID") is not None else "—")
    c4.metric("RA ID", detail.get("RA") if detail.get("RA") is not None else "—")
    st.write(f"**Email:** {detail.get('Email', '—')}")

    # Roommates (same room)
    st.write("#### Roommates")
    rm = requests.get(f"{API}/user/users/{user_id}/roommates").json()
    roommates = rm.get("roommates", []) if isinstance(rm, dict) else []
    st.dataframe(roommates, use_container_width=True) if roommates else st.info("No roommates on record.")

    # Tasks assigned to / created by this user
    tasks = requests.get(f"{API}/user/users/{user_id}/tasks").json()
    st.write("#### Tasks assigned to them")
    assigned = tasks.get("assigned_tasks", []) if isinstance(tasks, dict) else []
    st.dataframe(assigned, use_container_width=True) if assigned else st.info("None.")
    st.write("#### Tasks they created")
    created = tasks.get("created_tasks", []) if isinstance(tasks, dict) else []
    st.dataframe(created, use_container_width=True) if created else st.info("None.")

except requests.exceptions.RequestException as e:
    st.error(f"Could not load this user's profile: {e}")

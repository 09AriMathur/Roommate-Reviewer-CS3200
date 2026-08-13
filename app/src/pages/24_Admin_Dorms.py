import logging
logger = logging.getLogger(__name__)

import streamlit as st
import requests
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')
SideBarLinks()

API = "http://web-api:4000"

st.title("Dorms & Occupancy")
st.caption("Every residence hall, its activity stats, and who lives there.")

# ---- All dorms ----------------------------------------------------------
try:
    dorms = requests.get(f"{API}/dorm/dorms").json()
except requests.exceptions.RequestException as e:
    st.error(f"Could not load dorms from the API: {e}")
    st.stop()

st.write(f"**{len(dorms)}** dorms")
st.dataframe(dorms, use_container_width=True)

st.divider()

# ---- Drill into one dorm ------------------------------------------------
st.write("### Inspect a dorm")

options = {f'{d.get("Dorm_Name", "")} (ID {d["DormID"]})': d["DormID"] for d in dorms}
if not options:
    st.info("No dorms to inspect.")
    st.stop()

choice = st.selectbox("Pick a dorm", list(options.keys()))
dorm_id = options[choice]

try:
    stats = requests.get(f"{API}/dorm/dorms/{dorm_id}/stats").json()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rooms", stats.get("room_count", 0))
    c2.metric("Residents", stats.get("resident_count", 0))
    c3.metric("Open requests", stats.get("open_request_count", 0))
    c4.metric("Open reports", stats.get("open_report_count", 0))

    st.write("#### Activity by room")
    by_room = stats.get("by_room", [])
    if by_room:
        st.dataframe(by_room, use_container_width=True)
    else:
        st.info("No rooms.")

    st.write("#### Residents")
    residents = requests.get(f"{API}/dorm/dorms/{dorm_id}/users").json()
    if residents:
        st.dataframe(residents, use_container_width=True)
    else:
        st.info("None.")
except requests.exceptions.RequestException as e:
    st.error(f"Could not load this dorm's detail: {e}")

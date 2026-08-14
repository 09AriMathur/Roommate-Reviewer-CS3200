import logging
logger = logging.getLogger(__name__)

import streamlit as st
import requests
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')
SideBarLinks()

# The sidebar only hides links; it does not stop another role from reaching
# this URL. Without this, arriving without a session raised a KeyError on
# first_name rather than saying the page was off limits.
if st.session_state.get('role') != 'admin':
    st.error('You do not have access to this page.')
    st.stop()

API = "http://web-api:4000"

st.title("System Administrator")
st.write(f"### Welcome, {st.session_state.get('first_name', 'Admin')}")
st.caption(
    "You have a read-across view of the whole building. "
    "Use the sidebar to jump into any area."
)

# Headline numbers pulled live from the API so the landing page reflects reality
try:
    users = requests.get(f"{API}/user/users").json()
    ras = requests.get(f"{API}/ra/ras").json()
    dorms = requests.get(f"{API}/dorm/dorms").json()
    req_stats = requests.get(f"{API}/request/requests/stats").json()
    open_requests = {r["Status"]: r["total"] for r in req_stats.get("by_status", [])}.get("open", 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Residents", len(users))
    c2.metric("Resident Advisors", len(ras))
    c3.metric("Dorms", len(dorms))
    c4.metric("Open requests", open_requests)
except requests.exceptions.RequestException as e:
    st.error(f"Could not reach the API: {e}")

st.divider()
st.write("#### What you can do here")
st.markdown(
    "- **🧾 Activity Log** — review every recorded action, and add or remove log entries\n"
    "- **👥 User Accounts** — browse residents and open any profile\n"
    "- **🧑‍🏫 Resident Advisors** — see each RA's residents and interventions\n"
    "- **🏢 Dorms & Occupancy** — per-dorm stats and who lives where"
)

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

# All log routes live under the /log prefix (this admin's own blueprint)
API = "http://web-api:4000/log"
ADMIN_ID = st.session_state.get("user_id", 1)

st.title("Activity Log")
st.caption(
    "Every recorded action across the building. As admin you can add entries, "
    "mark them reviewed, and remove them."
)

# ---- Add a new log entry  (POST /log/logs) ------------------------------
with st.expander("➕ Record a new log entry"):
    with st.form("new_log", clear_on_submit=True):
        col1, col2 = st.columns([1, 3])
        user_id = col1.number_input("User ID", min_value=1, step=1, value=1)
        action = col2.text_input("Action", placeholder="e.g. Reviewed missed-chore report #4")
        submitted = st.form_submit_button("Add log entry", type="primary")
    if submitted:
        if not action.strip():
            st.warning("Action can't be empty.")
        else:
            resp = requests.post(f"{API}/logs", json={"UserId": int(user_id), "Action": action.strip()})
            if resp.status_code == 201:
                st.success(f"Log entry created (ID {resp.json().get('Log_Id')}).")
                st.rerun()
            else:
                st.error(f"Could not create: {resp.json().get('error', resp.text)}")

st.divider()

# ---- Filter + list  (GET /log/logs) -------------------------------------
user_filter = st.text_input("Filter by User ID (blank = everyone)", value="")
params = {}
if user_filter.strip().isdigit():
    params["user_id"] = user_filter.strip()

try:
    logs = requests.get(f"{API}/logs", params=params).json()
except requests.exceptions.RequestException as e:
    st.error(f"Could not load the activity log: {e}")
    st.stop()

st.write(f"**{len(logs)}** entries")
st.dataframe(logs, use_container_width=True)

# ---- Review (PUT) / Remove (DELETE) a specific entry --------------------
if logs:
    st.divider()
    st.write("#### Manage an entry")
    ids = [l["Log_Id"] for l in logs]
    chosen = st.selectbox("Pick a log entry (by Log_Id)", ids)

    a1, a2 = st.columns(2)
    # PUT /log/logs/<id>  — stamp this entry as reviewed by the signed-in admin
    if a1.button("Mark as reviewed by me", use_container_width=True):
        resp = requests.put(f"{API}/logs/{chosen}", json={"ReviewerID": int(ADMIN_ID)})
        if resp.status_code == 200:
            st.success("Marked as reviewed.")
            st.rerun()
        else:
            st.error(resp.json().get("error", resp.text))
    # DELETE /log/logs/<id>
    if a2.button("Delete this entry", type="secondary", use_container_width=True):
        resp = requests.delete(f"{API}/logs/{chosen}")
        if resp.status_code == 200:
            st.success("Deleted.")
            st.rerun()
        else:
            st.error(resp.json().get("error", resp.text))

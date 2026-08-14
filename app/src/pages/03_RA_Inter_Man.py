import logging
logger = logging.getLogger(__name__)

import pandas as pd
import requests
import streamlit as st
from modules.api import api_write
from modules.labels import INTERVENTION_STATUS_BADGES
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


ra_id = st.session_state.get('user_id')

# One call, scoped to this RA, with the resident's name and room already joined. The
# page used to fetch every intervention for all 31 RAs and match ids in Python, so Carol
# was reading the whole building's caseload to find her own.
all_interventions = api_get(f"/intervention/interventions?ra_id={ra_id}") or []
dorm_names = {d["DormID"]: d["Dorm_Name"] for d in (api_get("/dorm/dorms") or [])}


def room_label(row):
    if row.get("Room_Number") is None:
        return "Unassigned"
    return f"{dorm_names.get(row.get('DormID'), 'Dorm')} {row['Room_Number']}"


active = [i for i in all_interventions if i["Status"] in ACTIVE_STATUSES]
closed = [i for i in all_interventions if i["Status"] not in ACTIVE_STATUSES]

st.write('#### Ongoing Interventions')
st.caption(
    "A resident asked you to step in. Move it to Active while you are working on it, "
    "then Close it -- closing is what counts towards your settled total."
)

if not active:
    st.success("Nothing ongoing on your rooms.")

for i in active:
    with st.container(border=True):
        head, badge = st.columns([4, 1])
        head.write(
            f"**{i.get('First_Name', '')} {i.get('Last_Name', '')}** — {room_label(i)}"
        )
        label, color = INTERVENTION_STATUS_BADGES.get(
            i["Status"], (i["Status"].title(), "gray"))
        badge.badge(label, color=color)
        st.write(i.get("Description") or "_No description given_")

        # Nothing here could write before this: the table had no PUT at all, so a case a
        # resident filed stayed 'pending' however much work went into it.
        act_col, close_col, _ = st.columns([1, 1, 2])
        if i["Status"] == "pending" and act_col.button(
                "Start working", key=f"activate_{i['RequestID']}",
                use_container_width=True):
            status, _ = api_write("PUT", f"/intervention/interventions/{i['RequestID']}",
                                  {"Status": "active"})
            if status == 200:
                st.rerun()

        if close_col.button("Close case", key=f"close_{i['RequestID']}",
                            type="primary", use_container_width=True):
            status, _ = api_write("PUT", f"/intervention/interventions/{i['RequestID']}",
                                  {"Status": "closed"})
            if status == 200:
                st.rerun()

st.divider()

st.write('#### Closed Interventions')
if not closed:
    st.caption("None closed yet.")
else:
    st.dataframe(
        pd.DataFrame([{
            "ID": i["RequestID"],
            "Resident": f"{i.get('First_Name', '')} {i.get('Last_Name', '')}".strip(),
            "Room": room_label(i),
            "Description": i["Description"],
        } for i in closed]),
        use_container_width=True, hide_index=True,
    )

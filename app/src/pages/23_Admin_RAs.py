import logging
logger = logging.getLogger(__name__)

import streamlit as st
import requests
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')
SideBarLinks()

API = "http://web-api:4000"

st.title("Resident Advisors")
st.caption("The RA roster, plus the residents and interventions each one manages.")

# ---- Full RA roster -----------------------------------------------------
try:
    ras = requests.get(f"{API}/ra/ras").json()
except requests.exceptions.RequestException as e:
    st.error(f"Could not load RAs from the API: {e}")
    st.stop()

st.write(f"**{len(ras)}** resident advisors")
st.dataframe(ras, use_container_width=True)

st.divider()

# ---- Drill into one RA --------------------------------------------------
st.write("### Inspect an RA")

# Key drill-downs on the RA's UserID (the primary key of the RAs table)
options = {
    f'{r.get("First_Name", "")} {r.get("Last_Name", "")} (ID {r["UserID"]})': r
    for r in ras
}
if not options:
    st.info("No RAs to inspect.")
    st.stop()

choice = st.selectbox("Pick an RA", list(options.keys()))
ra = options[choice]
ra_id = ra["UserID"]

c1, c2, c3 = st.columns(3)
c1.metric("Requests settled", ra.get("Settled_Reqs", 0))
c2.metric("Reports settled", ra.get("Settled_Reps", 0))
c3.metric("Year", ra.get("Year") if ra.get("Year") is not None else "—")

try:
    st.write("#### Residents under this RA")
    ra_users = requests.get(f"{API}/ra/ras/{ra_id}/users").json()
    if ra_users:
        st.dataframe(ra_users, use_container_width=True)
    else:
        st.info("None.")

    st.write("#### Interventions this RA is running")
    interventions = requests.get(f"{API}/ra/ras/{ra_id}/interventions").json()
    if interventions:
        st.dataframe(interventions, use_container_width=True)
    else:
        st.info("None.")
except requests.exceptions.RequestException as e:
    st.error(f"Could not load this RA's detail: {e}")

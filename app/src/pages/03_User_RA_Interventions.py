import requests
import streamlit as st
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

USER_ID = st.session_state['user_id']

USER_API_URL = "http://web-api:4000/user"
RA_API_URL = "http://web-api:4000/ra"

try:
    user_response = requests.get(f"{USER_API_URL}/users/{USER_ID}")
    user_response.raise_for_status()
    user = user_response.json()
except requests.exceptions.RequestException as e:
    st.error(f"Could not reach the API: {e}")
    st.stop()

assigned_ra = None
if user.get('RA'):
    try:
        ra_response = requests.get(f"{RA_API_URL}/ras/{user['RA']}")
        ra_response.raise_for_status()
        assigned_ra = ra_response.json()
    except requests.exceptions.RequestException:
        assigned_ra = None

my_interventions = []
if user.get('RA'):
    try:
        interventions_response = requests.get(f"{RA_API_URL}/ras/{user['RA']}/interventions")
        interventions_response.raise_for_status()
        my_interventions = [
            i for i in interventions_response.json() if i['UserID'] == USER_ID
        ]
    except requests.exceptions.RequestException as e:
        st.error(f"Could not reach the API: {e}")
        st.stop()

STATUS_BADGES = {
    'pending': ('Pending', 'orange'),
    'active': ('Active', 'blue'),
    'closed': ('Closed', 'green'),
}


def render_intervention_row(intervention):
    with st.container(border=True):
        label, color = STATUS_BADGES.get(intervention['Status'], (intervention['Status'], 'gray'))
        st.badge(label, color=color)
        st.caption(intervention.get('Description') or "No description provided.")


st.title("RA Interventions")
st.caption("Ask your RA to step in when the roommate agreement isn't being upheld")

if not assigned_ra:
    st.warning("You don't have an assigned RA on file, so a request can't be sent yet.")
    st.stop()

history_col, new_request_col = st.columns([2, 3])

with history_col:
    with st.container(border=True):
        st.subheader("Your Requests")
        with st.container(height=400):
            if not my_interventions:
                st.markdown(":gray[*No intervention requests yet*]")
            else:
                for intervention in my_interventions:
                    render_intervention_row(intervention)

with new_request_col:
    with st.container(border=True):
        st.subheader("New Intervention Request")
        st.caption(f"This will be sent to your assigned RA, {assigned_ra['First_Name']} {assigned_ra['Last_Name']}.")

        with st.form("new_intervention_form", clear_on_submit=True):
            description = st.text_area(
                "What's going on?",
                placeholder="Briefly describe the accountability or task-completion issue in your roommate group...",
            )
            submitted = st.form_submit_button("Submit Request", type="primary", use_container_width=True)

            if submitted:
                if not description.strip():
                    st.error("Please provide a short description of the issue.")
                else:
                    create_response = requests.post(
                        f"{RA_API_URL}/ras/interventions",
                        json={
                            "UserID": USER_ID,
                            "Description": description.strip(),
                        },
                    )
                    create_response.raise_for_status()
                    st.success("Your RA has been notified.")
                    st.rerun()

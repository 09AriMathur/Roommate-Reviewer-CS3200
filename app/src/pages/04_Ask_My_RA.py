import streamlit as st
from modules.api import api_get, api_write
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

if st.session_state.get('role') not in ('user', 'student'):
    st.error('You do not have access to this page.')
    st.stop()

USER_ID = st.session_state['user_id']

user = api_get(f"/user/users/{USER_ID}")
if user is None:
    st.stop()

assigned_ra = api_get(f"/ra/ras/{user['RA']}", quiet=True) if user.get('RA') else None

my_interventions = []
if user.get('RA'):
    interventions = api_get(f"/ra/ras/{user['RA']}/interventions", quiet=True) or []
    my_interventions = [i for i in interventions if i['UserID'] == USER_ID]

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


st.title("Ask My RA")
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
                    status, _ = api_write("POST", "/ra/ras/interventions", {
                        "UserID": USER_ID,
                        "Description": description.strip(),
                    })
                    if status == 201:
                        st.success("Your RA has been notified.")
                        st.rerun()

import requests
import streamlit as st
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

# Hardcoded for now -- there is no real login flow yet, so we always
# show this page for this UserID.
USER_ID = st.session_state['user_id']

USER_API_URL = "http://web-api:4000/user"

try:
    user_response = requests.get(f"{USER_API_URL}/users/{USER_ID}")
    user_response.raise_for_status()
    user = user_response.json()
except requests.exceptions.RequestException as e:
    st.error(f"Could not reach the API: {e}")
    st.stop()

st.session_state['first_name'] = user['First_Name']

st.title(f"Welcome, {st.session_state['first_name']}.")
st.write('### What would you like to do today?')

if st.button('View My Home (Tasks & Roommates)',
             type='primary',
             use_container_width=True):
    st.switch_page('pages/01_User_Home.py')

if st.button('File a Room Report',
             type='primary',
             use_container_width=True):
    st.switch_page('pages/02_User_Room_Reports.py')

if st.button('Request an RA Intervention',
             type='primary',
             use_container_width=True):
    st.switch_page('pages/03_User_RA_Interventions.py')

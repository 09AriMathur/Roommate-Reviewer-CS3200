import logging
logger = logging.getLogger(__name__)

import streamlit as st
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

# Show appropriate sidebar links for the role of the currently logged in user
SideBarLinks()

st.title(f"Welcome Residence Advisor, {st.session_state['first_name']}.")
st.write('### What would you like to do today?')

if st.button('View Reporting Rooms',
             type='primary',
             use_container_width=True):
    st.switch_page('pages/01_RA_Room_Reports.py')

if st.button('View Performance Overview',
             type='primary',
             use_container_width=True):
    st.switch_page('pages/02_RA_Preform_Overview.py')

if st.button('View Intervention Manager',
             type='primary',
             use_container_width=True):
    st.switch_page('pages/03_RA_Inter_Man.py')

if st.button('View Rules Manager',
             type='primary',
             use_container_width=True):
    st.switch_page('pages/04_RA_Rules_Man.py')

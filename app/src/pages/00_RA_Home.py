import logging
logger = logging.getLogger(__name__)

import streamlit as st
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

st.title(f"Hi, {st.session_state['first_name']}.")
st.caption('Residence Advisor')

st.write('### What would you like to do today?')

# Bordered columns give the four cards a matching height, which keeps the four
# buttons level -- but only while the descriptions all wrap to the same number
# of lines. Keep them to one short line each.
cards = st.columns(4, gap='medium', border=True)

with cards[0]:
    st.markdown('**Room Reports**')
    st.caption('Browse or look up a room.')
    if st.button('Open', type='primary', use_container_width=True, key='go_rooms'):
        st.switch_page('pages/01_RA_Room_Reports.py')

with cards[1]:
    st.markdown('**Performance**')
    st.caption('Counts and completion rates.')
    if st.button('Open', type='primary', use_container_width=True, key='go_perf'):
        st.switch_page('pages/02_RA_Preform_Overview.py')

with cards[2]:
    st.markdown('**Interventions**')
    st.caption('Ongoing and closed cases.')
    if st.button('Open', type='primary', use_container_width=True, key='go_inter'):
        st.switch_page('pages/03_RA_Inter_Man.py')

with cards[3]:
    st.markdown('**Rules**')
    st.caption('Add, edit or remove rules.')
    if st.button('Open', type='primary', use_container_width=True, key='go_rules'):
        st.switch_page('pages/04_RA_Rules_Man.py')

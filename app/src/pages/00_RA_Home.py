import logging
logger = logging.getLogger(__name__)

import streamlit as st
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

# Show appropriate sidebar links for the role of the currently logged in user
SideBarLinks()

st.title(f"Hi, {st.session_state['first_name']}.")
st.caption('Residence Advisor')

st.write('### What would you like to do today?')

# Bordered columns give the four cards a matching height without having to
# pin one, since none of them sit next to an empty spacer column.
cards = st.columns(4, gap='medium', border=True)

with cards[0]:
    st.markdown('**Room Reports**')
    st.caption('Browse every room, then look one up: residents, tasks and rules.')
    if st.button('Open', type='primary', use_container_width=True, key='go_rooms'):
        st.switch_page('pages/01_RA_Room_Reports.py')

with cards[1]:
    st.markdown('**Performance**')
    st.caption('Intervention counts, completion rates, and a room spotlight.')
    if st.button('Open', type='primary', use_container_width=True, key='go_perf'):
        st.switch_page('pages/02_RA_Preform_Overview.py')

with cards[2]:
    st.markdown('**Interventions**')
    st.caption('What is ongoing across your rooms, and what has been closed.')
    if st.button('Open', type='primary', use_container_width=True, key='go_inter'):
        st.switch_page('pages/03_RA_Inter_Man.py')

with cards[3]:
    st.markdown('**Rules**')
    st.caption('Add, edit or remove the rules that apply to a room.')
    if st.button('Open', type='primary', use_container_width=True, key='go_rules'):
        st.switch_page('pages/04_RA_Rules_Man.py')

import requests
import streamlit as st
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

# Hardcoded for now -- there is no real login flow yet, so we always
# show this page for this UserID.
USER_ID = st.session_state['user_id']

USER_API_URL = "http://web-api:4000/user"
ROOM_API_URL = "http://web-api:4000/room"
DORM_API_URL = "http://web-api:4000/dorm"

try:
    user_response = requests.get(f"{USER_API_URL}/users/{USER_ID}")
    user_response.raise_for_status()
    user = user_response.json()
except requests.exceptions.RequestException as e:
    st.error(f"Could not reach the API: {e}")
    st.stop()

st.session_state['first_name'] = user['First_Name']

room_number = None
dorm_name = None
if user.get('RoomID'):
    try:
        room_response = requests.get(f"{ROOM_API_URL}/rooms/{user['RoomID']}")
        room_response.raise_for_status()
        room = room_response.json()
        room_number = room.get('Room_Number')

        dorm_response = requests.get(f"{DORM_API_URL}/dorms/{room['DormID']}")
        dorm_response.raise_for_status()
        dorm_name = dorm_response.json().get('Dorm_Name')
    except requests.exceptions.RequestException:
        pass

st.title(f"Welcome, {st.session_state['first_name']}.")

with st.container(border=True):
    info_cols = st.columns(2)
    info_cols[0].metric("Dorm", dorm_name or "Not assigned")
    info_cols[1].metric("Room", room_number or "Not assigned")

st.write('### What would you like to do today?')

# Bordered columns give the four cards a matching height, which keeps the four
# buttons level -- but only while the descriptions all wrap to the same number
# of lines. Keep them to one short line each.
cards = st.columns(4, gap='medium', border=True)

with cards[0]:
    st.markdown('**This Week**')
    st.caption('Your chores, day by day.')
    if st.button('Open', type='primary', use_container_width=True, key='go_week'):
        st.switch_page('pages/01_User_Home.py')

with cards[1]:
    st.markdown('**Chore Reports**')
    st.caption('Flag a skipped chore.')
    if st.button('Open', type='primary', use_container_width=True, key='go_reports'):
        st.switch_page('pages/02_User_Room_Reports.py')

with cards[2]:
    st.markdown('**Ask My RA**')
    st.caption('Ask your RA to step in.')
    if st.button('Open', type='primary', use_container_width=True, key='go_ra'):
        st.switch_page('pages/03_User_RA_Interventions.py')

with cards[3]:
    st.markdown('**Task History**')
    st.caption('Everything, with filters.')
    if st.button('Open', type='primary', use_container_width=True, key='go_history'):
        st.switch_page('pages/04_Past_Tasks.py')

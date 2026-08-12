##################################################
# This is the main/entry-point file for the
# Roommate Reviewer application.
##################################################

# Set up basic logging infrastructure
import logging
logging.basicConfig(format='%(filename)s:%(lineno)s:%(levelname)s -- %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# import the main streamlit library as well
# as SideBarLinks function from src/modules folder
import streamlit as st
from modules.nav import SideBarLinks

# streamlit supports regular and wide layout (how the controls
# are organized/displayed on the screen).
st.set_page_config(layout='wide')

# If a user is at this page, we assume they are not
# authenticated.  So we change the 'authenticated' value
# in the streamlit session_state to false.
st.session_state['authenticated'] = False

# Use the SideBarLinks function from src/modules/nav.py to control
# the links displayed on the left-side panel.
# IMPORTANT: ensure src/.streamlit/config.toml sets
# showSidebarNavigation = false in the [client] section
SideBarLinks(show_home=True)

# ***************************************************
#    The major content of this page
# ***************************************************

logger.info("Loading the Home page of the app")
st.title('Roommate Reviewer')
st.caption('Chore tracking and accountability for shared dorm rooms.')
st.write('#### Choose a persona to explore the app')

# For each of the user personas for which we are implementing
# functionality, we put a card on the screen with a button that the
# user can click to MIMIC logging in as that mock user.
#
# Bordered columns keep the three cards the same height however the
# descriptions wrap, so the buttons stay on a common baseline.
joshua_col, frank_col, carol_col = st.columns(3, gap='medium', border=True)

with joshua_col:
    st.markdown('### Joshua Patel')
    st.badge('Resident', color='gray')
    st.caption(
        "Plans the week's chores, checks them off, and files a report when a "
        "roommate skips one."
    )
    if st.button('Log in as Joshua',
                 type='primary',
                 use_container_width=True):
        st.session_state['authenticated'] = True
        st.session_state['role'] = 'user'
        st.session_state['user_id'] = 43
        # Set here as well as on the landing page, so the sidebar has a name
        # to show immediately rather than the previous persona's.
        st.session_state['first_name'] = 'Joshua'
        logger.info("Logging in as the Resident Persona")
        st.switch_page('pages/00_User_Start.py')

with frank_col:
    st.markdown('### Frank Osei')
    st.badge('Resident', color='gray')
    st.caption(
        "Behind on his chores. Asks for extensions, disputes reports, and "
        "marks the days he is away."
    )
    if st.button('Log in as Frank',
                 type='primary',
                 use_container_width=True):
        st.session_state['authenticated'] = True
        st.session_state['role'] = 'student'
        # Frank Osei (Users.UserID 4) is the seeded stand-in for the Ronny RuleBreaker
        # persona: 0 tasks completed, 3 missed, two open strikes, and four open requests.
        st.session_state['user_id'] = 4
        st.session_state['first_name'] = 'Frank'
        logger.info("Logging in as the Ronny RuleBreaker Persona")
        st.switch_page('pages/10_Student_Home.py')

with carol_col:
    st.markdown('### Carol Diaz')
    st.badge('Residence Advisor', color='gray')
    st.caption(
        "Reviews reports across her rooms, tracks completion rates, and sets "
        "the rules residents follow."
    )
    if st.button('Log in as Carol',
                 type='primary',
                 use_container_width=True):
        st.session_state['authenticated'] = True
        st.session_state['role'] = 'ra'
        st.session_state['first_name'] = 'Carol'
        # Carol Diaz is RAs.RA_ID 1 in the seed data, so pages that scope data to
        # "the current RA" (e.g. Rules Manager) have a real record to use.
        st.session_state['user_id'] = 1
        logger.info("Logging in as Residence Advisor Persona")
        st.switch_page('pages/00_RA_Home.py')

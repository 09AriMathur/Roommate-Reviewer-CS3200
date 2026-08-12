##################################################
# This is the main/entry-point file for the
# sample application for your project
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
st.write('#### Hi! As which user would you like to log in?')

# For each of the user personas for which we are implementing
# functionality, we put a button on the screen that the user
# can click to MIMIC logging in as that mock user.

if st.button('User Page',
        type='primary',
        use_container_width=True):
        st.session_state['authenticated'] = True
        st.session_state['role'] = 'user'
        st.session_state['user_id'] = 43
        st.switch_page('pages/00_User_Start.py')
if st.button('Act as Frank, a Resident Falling Behind',
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
if st.button('Act as Carol, a Residence Advisor',
            type='primary',
            use_container_width=True):
    st.session_state['authenticated'] = True
    st.session_state['role'] = 'ra'
    st.session_state['first_name'] = 'Carol'
    # Risha stands in for Carol Diaz (RAs.UserID 1) in the seed data, so pages that
    # scope data to "the current RA" (e.g. Rules Manager) have a real record to use
    st.session_state['user_id'] = 1
    logger.info("Logging in as Residence Advisor Persona")
    st.switch_page('pages/00_RA_Home.py')

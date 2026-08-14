import streamlit as st
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

# A Back control in the LEFT pane (sidebar) that returns the user to their own
# home page rather than the login screen. Falls back to login if no role is set.
_home_by_role = {
    "user": "pages/00_Resident_Home.py",
    "student": "pages/00_Resident_Home.py",
    "ra": "pages/00_RA_Home.py",
    "admin": "pages/20_Admin_Home.py",
}
_back_target = _home_by_role.get(st.session_state.get("role"), "Home.py")
if st.sidebar.button("← Back", type="primary", use_container_width=True):
    st.switch_page(_back_target)

st.title("About Roommate Reviewer")

st.markdown(
    """
    Shared dorm rooms run on chores nobody wants to track. Someone skips the
    trash, someone else notices, and there is no record of any of it until the
    room stops speaking to each other.

    **Roommate Reviewer** gives a room one place to agree on who does what, mark
    chores off as they get done, and raise a flag when they don't. If a room
    cannot sort something out on its own, it escalates to the Residence Advisor
    with the history already attached.
    """
)

st.write("### Who uses it")

st.caption(
    "The two Resident personas see the identical set of pages -- the "
    "difference is entirely in the data behind them."
)

roles = st.columns(3, gap='medium', border=True)

with roles[0]:
    st.markdown("**Resident, on track**")
    st.caption(
        "Chores done, no open strikes, nothing overdue. The dashboard and "
        "requests pages stay quiet."
    )

with roles[1]:
    st.markdown("**Resident, falling behind**")
    st.caption(
        "Missed chores, open strikes, and pending requests -- the same "
        "pages, but every warning banner is lit up."
    )

with roles[2]:
    st.markdown("**Residence Advisor**")
    st.caption(
        "Reviews reports across their rooms, tracks completion rates, runs "
        "interventions, and sets the rules."
    )

st.write("### How it is built")

st.markdown(
    """
    Three Docker containers:

    - **Streamlit** for the front end, one Python file per page
    - **Flask** for the REST API, split into blueprints by resource
    - **MySQL** for the database, seeded from `database-files/ddl.sql`

    The front end never touches the database directly. Every page goes through
    the API.
    """
)

st.write("### Team")

st.markdown(
    """
    Aryaman Mathur · Hutch Turner · Nathan Rabe · Phone Kyaw

    Built for CS 3200, Database Design, Summer B 2026.
    """
)

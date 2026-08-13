import streamlit as st
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

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

roles = st.columns(3, gap='medium', border=True)

with roles[0]:
    st.markdown("**Resident**")
    st.caption(
        "Plans the week's chores, checks them off, and files a report when a "
        "roommate skips one."
    )

with roles[1]:
    st.markdown("**Resident falling behind**")
    st.caption(
        "Asks for extensions, disputes reports filed against them, marks away "
        "dates, and watches their standing against the room."
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

if st.button("Return to Home", type="primary"):
    st.switch_page("Home.py")

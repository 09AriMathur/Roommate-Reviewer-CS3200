# Idea borrowed from https://github.com/fsmosca/sample-streamlit-authenticator

# This file has functions to add links to the left sidebar based on the user's role.

import streamlit as st


# How each role is described under the user's name in the sidebar.
ROLE_LABELS = {
    "user": "Resident",
    "student": "Resident",
    "ra": "Residence Advisor",
}


# ---- General ----------------------------------------------------------------

def home_nav():
    st.sidebar.page_link("Home.py", label="Home", icon="🏠")


def about_page_nav():
    st.sidebar.page_link("pages/30_About.py", label="About", icon="ℹ️")


# ---- Roles: user & student (Joshua & Frank share the same resident pages) ----

def resident_home_nav():
    st.sidebar.page_link("pages/00_Resident_Home.py", label="Home", icon="🏠")


def my_chores_nav():
    st.sidebar.page_link("pages/01_My_Chores.py", label="My Chores", icon="🧹")


def chore_reports_nav():
    st.sidebar.page_link("pages/02_Chore_Reports.py", label="Chore Reports", icon="📝")


def my_requests_nav():
    st.sidebar.page_link("pages/03_My_Requests.py", label="My Requests", icon="✉️")


def ask_my_ra_nav():
    st.sidebar.page_link("pages/04_Ask_My_RA.py", label="Ask My RA", icon="🛎️")


def my_away_nav():
    st.sidebar.page_link("pages/05_My_Away.py", label="Away Dates", icon="✈️")


def my_standing_nav():
    st.sidebar.page_link("pages/06_My_Standing.py", label="My Standing", icon="📈")


# ---- Role: ra (Carol) --------------------------------------------------------

def ra_home_nav():
    st.sidebar.page_link("pages/00_RA_Home.py", label="Home", icon="🏠")


def ra_room_reports_nav():
    st.sidebar.page_link(
        "pages/01_RA_Room_Reports.py", label="Room Reports", icon="📋"
    )


def ra_preform_overview_nav():
    st.sidebar.page_link(
        "pages/02_RA_Preform_Overview.py", label="Performance", icon="📊"
    )


def ra_inter_man_nav():
    st.sidebar.page_link(
        "pages/03_RA_Inter_Man.py", label="Interventions", icon="🛠️"
    )


def ra_rules_man_nav():
    st.sidebar.page_link("pages/04_RA_Rules_Man.py", label="Rules", icon="📜")


# ---- Sidebar assembly -------------------------------------------------------

def current_user_nav():
    """Show who is signed in, under the logo.

    Not every role has a first name in the session straight after login -- the
    'user' role only picks one up once its landing page fetches the record --
    so fall back to the role on its own rather than printing nothing.
    """
    name = st.session_state.get("first_name")
    label = ROLE_LABELS.get(st.session_state.get("role"), "Signed in")

    if name:
        st.sidebar.markdown(f"**{name}**")
        st.sidebar.caption(label)
    else:
        st.sidebar.markdown(f"**{label}**")


def SideBarLinks(show_home=False):
    """
    Renders sidebar navigation links based on the logged-in user's role.
    The role is stored in st.session_state when the user logs in on Home.py.
    """

    # Logo, centred at the top of the sidebar on every page. st.logo() would be
    # the tidier primitive but it renders the mark at roughly 24px, too small to
    # read, so this places the image directly instead.
    st.sidebar.columns([1, 2, 1])[1].image("assets/logo.png", width=96)

    # If no one is logged in, send them to the Home (login) page
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.switch_page("Home.py")

    if st.session_state["authenticated"]:
        current_user_nav()
        st.sidebar.divider()

    if show_home:
        home_nav()

    if st.session_state["authenticated"]:

        if st.session_state["role"] in ("user", "student"):
            resident_home_nav()
            my_chores_nav()
            chore_reports_nav()
            my_requests_nav()
            ask_my_ra_nav()
            my_away_nav()
            my_standing_nav()

        if st.session_state["role"] == "ra":
            ra_home_nav()
            ra_room_reports_nav()
            ra_preform_overview_nav()
            ra_inter_man_nav()
            ra_rules_man_nav()

        st.sidebar.divider()

    # About link appears at the bottom for all roles
    about_page_nav()

    if st.session_state["authenticated"]:
        if st.sidebar.button("Log out", use_container_width=True):
            del st.session_state["role"]
            del st.session_state["authenticated"]
            st.switch_page("Home.py")

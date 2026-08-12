# Idea borrowed from https://github.com/fsmosca/sample-streamlit-authenticator

# This file has functions to add links to the left sidebar based on the user's role.

import streamlit as st


# ---- General ----------------------------------------------------------------

def home_nav():
    st.sidebar.page_link("Home.py", label="Home", icon="🏠")


def about_page_nav():
    st.sidebar.page_link("pages/30_About.py", label="About", icon="🧠")


# ---- Role: pol_strat_advisor ------------------------------------------------

def pol_strat_home_nav():
    st.sidebar.page_link(
        "pages/00_Pol_Strat_Home.py", label="Political Strategist Home", icon="👤"
    )


def world_bank_viz_nav():
    st.sidebar.page_link(
        "pages/01_World_Bank_Viz.py", label="World Bank Visualization", icon="🏦"
    )


def map_demo_nav():
    st.sidebar.page_link("pages/02_Map_Demo.py", label="Map Demonstration", icon="🗺️")


# ---- Role: user --------------------------------------------------------------

def user_start_nav():
    st.sidebar.page_link("pages/00_User_Start.py", label="User Start", icon="👤")


def user_home_nav():
    st.sidebar.page_link("pages/01_User_Home.py", label="User Home", icon="🏠")


def user_room_reports_nav():
    st.sidebar.page_link("pages/02_User_Room_Reports.py", label="Report", icon="📝")


def user_ra_interventions_nav():
    st.sidebar.page_link(
        "pages/03_User_RA_Interventions.py", label="RA Interventions", icon="🛠️"
    )


def past_tasks_nav():
    st.sidebar.page_link("pages/04_Past_Tasks.py", label="Past Tasks", icon="🗒️")


# ---- Role: student -----------------------------------------------------------

def student_home_nav():
    st.sidebar.page_link("pages/10_Student_Home.py", label="My Dorm", icon="👤")


def my_chores_nav():
    st.sidebar.page_link("pages/11_My_Chores.py", label="My Chores", icon="🧹")


def my_requests_nav():
    st.sidebar.page_link("pages/12_My_Requests.py", label="My Requests", icon="✉️")


def my_away_nav():
    st.sidebar.page_link("pages/13_My_Away.py", label="Away Dates", icon="✈️")


def my_standing_nav():
    st.sidebar.page_link("pages/14_My_Standing.py", label="My Standing", icon="📈")


# ---- Role: usaid_worker -----------------------------------------------------

def usaid_worker_home_nav():
    st.sidebar.page_link(
        "pages/10_USAID_Worker_Home.py", label="USAID Worker Home", icon="🏠"
    )


def ngo_directory_nav():
    st.sidebar.page_link("pages/14_NGO_Directory.py", label="NGO Directory", icon="📁")


def add_ngo_nav():
    st.sidebar.page_link("pages/15_Add_NGO.py", label="Add New NGO", icon="➕")


def prediction_nav():
    st.sidebar.page_link(
        "pages/11_Prediction.py", label="Regression Prediction", icon="📈"
    )


def api_test_nav():
    st.sidebar.page_link("pages/12_API_Test.py", label="Test the API", icon="🛜")


def classification_nav():
    st.sidebar.page_link(
        "pages/13_Classification.py", label="Classification Demo", icon="🌺"
    )


# ---- Role: administrator ----------------------------------------------------

def admin_home_nav():
    st.sidebar.page_link("pages/20_Admin_Home.py", label="System Admin", icon="🖥️")


def ml_model_mgmt_nav():
    st.sidebar.page_link(
        "pages/21_ML_Model_Mgmt.py", label="ML Model Management", icon="🏢"
    )


# ---- Role: ra (Residence Advisor) -------------------------------------------

def ra_home_nav():
    st.sidebar.page_link("pages/00_RA_Home.py", label="RA Home", icon="🏠")


def ra_room_reports_nav():
    st.sidebar.page_link(
        "pages/01_RA_Room_Reports.py", label="Room Reports", icon="📋"
    )


def ra_preform_overview_nav():
    st.sidebar.page_link(
        "pages/02_RA_Preform_Overview.py", label="Performance Overview", icon="📊"
    )


def ra_inter_man_nav():
    st.sidebar.page_link(
        "pages/03_RA_Inter_Man.py", label="Intervention Manager", icon="🛠️"
    )


def ra_rules_man_nav():
    st.sidebar.page_link("pages/04_RA_Rules_Man.py", label="Rules Manager", icon="📜")


# ---- Sidebar assembly -------------------------------------------------------

def SideBarLinks(show_home=False):
    """
    Renders sidebar navigation links based on the logged-in user's role.
    The role is stored in st.session_state when the user logs in on Home.py.
    """

    # Logo appears at the top of the sidebar on every page
    st.sidebar.image("assets/logo.png", width=150)

    # If no one is logged in, send them to the Home (login) page
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.switch_page("Home.py")

    if show_home:
        home_nav()

    if st.session_state["authenticated"]:

        if st.session_state["role"] == "user":
            user_start_nav()
            user_home_nav()
            user_room_reports_nav()
            user_ra_interventions_nav()
            past_tasks_nav()

        if st.session_state["role"] == "student":
            student_home_nav()
            my_chores_nav()
            my_requests_nav()
            my_away_nav()
            my_standing_nav()

        if st.session_state["role"] == "pol_strat_advisor":
            pol_strat_home_nav()
            world_bank_viz_nav()
            map_demo_nav()

        if st.session_state["role"] == "usaid_worker":
            usaid_worker_home_nav()
            ngo_directory_nav()
            add_ngo_nav()
            prediction_nav()
            api_test_nav()
            classification_nav()

        if st.session_state["role"] == "administrator":
            admin_home_nav()
            ml_model_mgmt_nav()

        if st.session_state["role"] == "ra":
            ra_home_nav()
            ra_room_reports_nav()
            ra_preform_overview_nav()
            ra_inter_man_nav()
            ra_rules_man_nav()

    # About link appears at the bottom for all roles
    about_page_nav()

    if st.session_state["authenticated"]:
        if st.sidebar.button("Logout"):
            del st.session_state["role"]
            del st.session_state["authenticated"]
            st.switch_page("Home.py")

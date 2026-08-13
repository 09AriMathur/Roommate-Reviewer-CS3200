from datetime import date, timedelta
from email.utils import parsedate_to_datetime

import streamlit as st
from modules.api import api_get, api_write
from modules.nav import SideBarLinks

st.set_page_config(layout='wide')

SideBarLinks()

if st.session_state.get('role') not in ('user', 'student'):
    st.error('You do not have access to this page.')
    st.stop()

USER_ID = st.session_state['user_id']


def to_date(value):
    """Flask serializes DATE columns as RFC 2822."""
    return parsedate_to_datetime(value).date() if value else None


def span(period):
    start, end = to_date(period['Start_Date']), to_date(period['End_Date'])
    nights = (end - start).days
    label = f"{start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}"
    return start, end, f"{label} ({nights + 1} day{'s' if nights else ''})"


st.title('Away Dates')
st.caption(
    "Mark the days you'll be gone and the chore rotation skips you instead of marking "
    "you down for a chore you couldn't be there to do."
)

user = api_get(f"/user/users/{USER_ID}")
if user is None:
    st.stop()

room_id = user.get('RoomID')
today = date.today()

my_away = api_get(f"/away/users/{USER_ID}/away")
if my_away is None:
    st.stop()


# ---- Booking a new stretch of time -------------------------------------------

@st.dialog("Mark yourself away")
def add_away():
    chosen = st.date_input(
        "Which days will you be gone?",
        value=(today, today + timedelta(days=3)),
        min_value=today - timedelta(days=365),
    )

    # A range picker hands back a single date until the second one is chosen.
    if not isinstance(chosen, tuple) or len(chosen) != 2:
        st.caption("Pick an end date to continue.")
        return

    start, end = chosen
    if end < start:
        st.error("The end date has to be on or after the start date.")
        return

    overlapping = [
        p for p in my_away
        if to_date(p['Start_Date']) <= end and to_date(p['End_Date']) >= start
    ]
    if overlapping:
        st.warning(
            "This overlaps a stretch you've already marked. You can still save it, "
            "but you may want to edit the existing one instead."
        )

    if st.button("Save", type="primary", use_container_width=True):
        status, _ = api_write("POST", "/away/away", {
            "UserID": USER_ID,
            "Start_Date": start.strftime("%Y-%m-%d"),
            "End_Date": end.strftime("%Y-%m-%d"),
        })
        if status == 201:
            st.rerun()


if st.button("Add away dates", type="primary"):
    add_away()


# ---- Everything already on the calendar --------------------------------------

st.write("### Your away dates")

if not my_away:
    st.info("You haven't marked any away dates yet.")

for period in my_away:
    away_id = period['AwayID']
    start, end, label = span(period)

    if start <= today <= end:
        state = ("Away now", "orange")
    elif start > today:
        state = ("Upcoming", "blue")
    else:
        state = ("Past", "gray")

    with st.expander(f"{label} · {state[0]}"):
        # Re-read the row before editing so the form starts from what the database
        # currently holds rather than from the list fetched at page load.
        current = api_get(f"/away/away/{away_id}", quiet=True) or period

        st.badge(state[0], color=state[1])

        edited = st.date_input(
            "Change these dates",
            value=(to_date(current['Start_Date']), to_date(current['End_Date'])),
            key=f"edit_{away_id}",
        )

        save_col, cancel_col = st.columns(2)

        if save_col.button("Save changes", key=f"save_{away_id}",
                           use_container_width=True):
            if not isinstance(edited, tuple) or len(edited) != 2:
                st.error("Pick both a start and an end date.")
            elif edited[1] < edited[0]:
                st.error("The end date has to be on or after the start date.")
            else:
                status, _ = api_write("PUT", f"/away/away/{away_id}", {
                    "Start_Date": edited[0].strftime("%Y-%m-%d"),
                    "End_Date": edited[1].strftime("%Y-%m-%d"),
                })
                if status == 200:
                    st.rerun()

        if cancel_col.button("Cancel these dates", key=f"delete_{away_id}",
                             use_container_width=True):
            status, _ = api_write("DELETE", f"/away/away/{away_id}")
            if status == 200:
                st.rerun()


# ---- Who can actually cover a given day --------------------------------------

st.write("### Who's around?")

if not room_id:
    st.caption("You have no room assignment, so there's no suite to check.")
else:
    check_date = st.date_input("Check a date", value=today, key="coverage_date")
    on_date = check_date.strftime("%Y-%m-%d")

    coverage = api_get(f"/away/rooms/{room_id}/available",
                       params={"on_date": on_date}, quiet=True)
    available = (coverage or {}).get('available', [])

    # Everyone away that day, across the whole building -- the suite view above only
    # says who is left, not who is gone.
    away_that_day = api_get("/away/away", params={"on_date": on_date}, quiet=True) or []
    away_ids = {a['UserID'] for a in away_that_day}

    here_col, gone_col = st.columns(2)

    with here_col:
        st.write(f"**Around on {check_date.strftime('%b %d')}**")
        if not available:
            st.caption("Nobody in your suite is available that day.")
        for person in available:
            marker = " (you)" if person['UserID'] == USER_ID else ""
            st.write(f"- {person['First_Name']} {person['Last_Name']}{marker}")

    with gone_col:
        st.write("**Away that day**")
        roommates = (api_get(f"/user/users/{USER_ID}/roommates", quiet=True)
                     or {}).get('roommates', [])
        suite_people = roommates + [user]
        suite_away = [p for p in suite_people if p['UserID'] in away_ids]

        if not suite_away:
            st.caption("Everyone in your suite is around.")
        for person in suite_away:
            marker = " (you)" if person['UserID'] == USER_ID else ""
            st.write(f"- {person['First_Name']} {person['Last_Name']}{marker}")

        st.caption(f"{len(away_ids)} resident(s) away building-wide that day.")

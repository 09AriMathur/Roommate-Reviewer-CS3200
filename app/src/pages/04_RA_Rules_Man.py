import logging
logger = logging.getLogger(__name__)

import pandas as pd
import requests
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

st.title('Rules Manager')
st.write(f"### Hi, {st.session_state['first_name']}.")

API_URL = "http://web-api:4000"


def api_get(path):
    """GET a backend endpoint and return the parsed JSON, or None on failure."""
    try:
        response = requests.get(f"{API_URL}{path}")
        if response.status_code == 200:
            return response.json()
        st.error(f"API error on GET {path}: {response.status_code}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to the API: {e}")
        return None


def api_write(method, path, payload=None):
    """POST/PUT/DELETE to a backend endpoint. Returns the parsed JSON on success,
    or None (after showing the API's error message) on failure."""
    try:
        response = requests.request(method, f"{API_URL}{path}", json=payload)
        if response.status_code in (200, 201):
            return response.json()
        st.error(response.json().get("error", f"API error: {response.status_code}"))
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to the API: {e}")
        return None


ra_id = st.session_state.get('user_id')

if not ra_id:
    st.error("No RA is associated with this session.")
    st.stop()

ra = api_get(f"/ra/ras/{ra_id}")
# The room picker used to offer all 68 rooms in the building, and the API accepted any
# of them, so a rule could be written into a room this RA has nothing to do with.
rooms = api_get(f"/ra/ras/{ra_id}/rooms") or []
dorms = api_get("/dorm/dorms") or []

if ra is None:
    st.stop()

dorm_names = {d["DormID"]: d["Dorm_Name"] for d in dorms}

# A room is keyed by its dorm and its number together, so the lookups key on that
# pair rather than a single id.
room_labels = {}
for r in rooms:
    dorm_label = dorm_names.get(r["DormID"], f"Dorm {r['DormID']}")
    room_labels[(r["DormID"], r["Room_Number"])] = f"{dorm_label} {r['Room_Number']}"
room_label_to_key = {label: key for key, label in room_labels.items()}

st.write(f"#### Rules Created By {ra['First_Name']} {ra['Last_Name']}")

my_rules = api_get(f"/ra/ras/{ra_id}/rules") or []

if my_rules:
    rule_rows = [{
        "Rule ID": r["RuleID"],
        "Description": r["Descr"],
        "Room": room_labels.get((r["DormID"], r["Room_Number"]), "Unassigned"),
    } for r in my_rules]
    st.dataframe(pd.DataFrame(rule_rows), use_container_width=True, hide_index=True)
else:
    st.info("You haven't created any rules yet.")

st.divider()

# ---------------------------------------------------------------------------
# Add a new rule
# ---------------------------------------------------------------------------

st.write('#### Add a New Rule')

with st.form("add_rule_form", clear_on_submit=True):
    new_descr = st.text_area("Description")
    new_room_label = st.selectbox("Room", list(room_label_to_key.keys()))
    add_submitted = st.form_submit_button("Add Rule")

if add_submitted:
    if not new_descr.strip():
        st.error("Description cannot be empty.")
    else:
        result = api_write("POST", "/rule/rules", {
            "Descr": new_descr.strip(),
            "DormID": room_label_to_key[new_room_label][0],
            "Room_Number": room_label_to_key[new_room_label][1],
            "RA_ID": ra_id,
        })
        if result:
            st.success("Rule added.")
            st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Edit or delete an existing rule
# ---------------------------------------------------------------------------

st.write('#### Edit or Delete a Rule')

if my_rules:
    rule_options = {f"#{r['RuleID']}: {r['Descr'][:40]}": r for r in my_rules}
    selected_label = st.selectbox("Select a rule", list(rule_options.keys()))
    selected_rule = rule_options[selected_label]

    room_label_options = list(room_label_to_key.keys())
    current_room_label = room_labels.get(
        (selected_rule["DormID"], selected_rule["Room_Number"]))
    current_index = (
        room_label_options.index(current_room_label) if current_room_label in room_label_options else 0
    )

    with st.form("edit_rule_form"):
        edited_descr = st.text_area("Description", value=selected_rule["Descr"])
        edited_room_label = st.selectbox("Room", room_label_options, index=current_index)
        edit_submitted = st.form_submit_button("Save Changes")

    if edit_submitted:
        if not edited_descr.strip():
            st.error("Description cannot be empty.")
        else:
            result = api_write("PUT", f"/rule/rules/{selected_rule['RuleID']}", {
                "Descr": edited_descr.strip(),
                "DormID": room_label_to_key[edited_room_label][0],
                "Room_Number": room_label_to_key[edited_room_label][1],
            })
            if result:
                st.success("Rule updated.")
                st.rerun()

    if st.button("Delete This Rule", type="primary"):
        result = api_write("DELETE", f"/rule/rules/{selected_rule['RuleID']}")
        if result:
            st.success("Rule deleted.")
            st.rerun()
else:
    st.info("No rules to edit or delete yet.")

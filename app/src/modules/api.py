"""Small wrapper around the Flask API for the Streamlit pages.

The RA pages each define their own copy of these helpers. This module exists so the
resident pages, which make considerably more calls, can share one implementation.

api_write returns the status code alongside the body because some routes use a status
to mean something the UI has to explain -- DELETE /request/requests/<id> answers 409
when the request is no longer open, and "only an open request can be withdrawn" is a
better message than the generic error text.
"""

import requests
import streamlit as st

API_URL = "http://web-api:4000"


def api_get(path, params=None, quiet=False):
    """GET a backend endpoint and return the parsed JSON, or None on failure.

    Pass quiet=True for optional data, where a missing section should render an empty
    state rather than an error banner across the whole page.
    """
    try:
        response = requests.get(f"{API_URL}{path}", params=params)
        if response.status_code == 200:
            return response.json()
        if not quiet:
            st.error(f"API error on GET {path}: {response.status_code}")
        return None
    except requests.exceptions.RequestException as e:
        if not quiet:
            st.error(f"Could not reach the API: {e}")
        return None


def api_write(method, path, payload=None, expected=()):
    """POST/PUT/DELETE a backend endpoint. Returns (status_code, body).

    On anything other than 200/201 the API's own "error" field is shown, so callers
    only have to handle the happy path. List a status in `expected` to suppress that
    banner and handle the response yourself.

    status_code is None when the request never reached the server.
    """
    try:
        response = requests.request(method, f"{API_URL}{path}", json=payload)
    except requests.exceptions.RequestException as e:
        st.error(f"Could not reach the API: {e}")
        return None, None

    try:
        body = response.json()
    except ValueError:
        body = None

    if response.status_code not in (200, 201) and response.status_code not in expected:
        detail = (body or {}).get("error", f"API error: {response.status_code}")
        st.error(detail)

    return response.status_code, body

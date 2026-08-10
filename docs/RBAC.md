# Handling User Role Access and Control (RBAC)

In most applications, when a user logs in, they assume a particular role in the app. For instance, when one logs in to a stock price prediction app, they may be a single investor, a portfolio manager, or a corporate executive (of a publicly traded company). Each of those *roles* will likely present some similar features as well as some different features when compared to the other roles. This is sometimes called Role-based Access Control, or **RBAC** for short.

The code in this project demonstrates how to implement a simple RBAC system in Streamlit without actually using user authentication (usernames and passwords). The template ships with three example roles — *Political Strategist* (labeled *Political Strategy Advisor* on its login button), *USAID Worker*, and *System Administrator* — that you will replace with the personas specific to your project.

> **Important:** this is a *demonstration* of role-based navigation, not a security mechanism. There are no passwords, nothing is verified server-side, and the "login" is just a button that writes a string into browser session state. Never model a real access-control system on this.

## Conceptual Overview

When a user "logs in" by clicking a role button on the Home page, two things happen: their role is recorded and they are redirected to that role's landing page. The recording happens in Streamlit's **`session_state`** object.

`session_state` is a dictionary-like object that Streamlit keeps alive for the duration of a user's browser session. Think of it as a small, per-user context bag — any page in the app can read from or write to it, and the values persist as the user navigates between pages. It is the mechanism that lets a page "remember" who is currently using the app.

At login, three keys are written into `session_state`:

| Key | What it holds |
|-----|---------------|
| `authenticated` | `True` — confirms the user has selected a role |
| `role` | A short string identifying the role (e.g. `'administrator'`) |
| `first_name` | A display name used to personalize the UI |

From that point on, the sidebar is rebuilt on every page load: the call to `SideBarLinks(...)` reads `role` out of `session_state` and renders only the links belonging to that role. Users are not shown links to pages outside their role.

### What the template actually enforces

Be precise about what this buys you, because it is easy to over- *and* under-estimate:

- **Link hiding is enforced.** A user only ever *sees* the sidebar links for their own role.
- **Direct URL access without logging in is redirected.** `session_state` lives for exactly one Streamlit session, and a session is tied to a single page load. Typing a page URL straight into the address bar starts a **brand-new session** with an empty `session_state`, so the `authenticated` key is missing, and the check near the top of `SideBarLinks(...)` in `app/src/modules/nav.py` — just after the sidebar logo is drawn — bounces the user back to `Home.py`.
- **So does refreshing.** The same rule means a logged-in user who hits reload loses their `session_state` and is returned to `Home.py`. This surprises students during demos — if you refresh mid-presentation, you have to click your role button again. It is expected behavior, not a bug.
- **The guard tests presence, not truth.** The check is `if "authenticated" not in st.session_state`, so it fires only when the key is *absent*. `Home.py` sets `st.session_state['authenticated'] = False` as soon as it loads, so for the rest of that session the key exists and the guard no longer fires. That is why the **About** link — which `SideBarLinks(...)` renders for everyone, logged in or not — opens normally from the Home page without logging in.
- **Role *matching* is not enforced.** Nothing compares the page a user is on against the role in `session_state`, and the pages in `app/src/pages/` contain no access checks of their own. Two consequences: a page that forgets to call `SideBarLinks(...)` has **no** protection at all, and if you add in-session navigation from one role's page to another role's page, the target page will happily render.

If you want a page to verify the role as well, add the guard yourself — see *Optional: hardening a page* at the end of this document.

## How the Project Template RBAC and Navigation Works

### 1. Disabling the default Streamlit navigation

The standard Streamlit sidebar navigation panel is turned off via `app/src/.streamlit/config.toml`:

```toml
[client]
showSidebarNavigation = false
```

This gives full control over which links appear in the sidebar for each role.

### 2. The navigation module

`app/src/modules/nav.py` contains a set of functions — generally one per sidebar link — that each call `st.sidebar.page_link(...)` to add a single link to the sidebar. Having a separate function per link makes it easy to compose role-specific sidebar menus. Not every page needs one: `pages/16_NGO_Profile.py` has no `_nav` function and appears in no sidebar, because it is a detail view reached only from the *View Full Profile* button on `pages/14_NGO_Directory.py`, which hands it an id through `session_state`.

### 3. The Home page and session state

`app/src/Home.py` presents one button per role. When a button is clicked, a few variables are written to Streamlit's `session_state` before redirecting to that role's home page via `st.switch_page(...)`. The three roles shipped in the template are:

| Button | `role` string | Redirects to |
|--------|---------------|--------------|
| Act as John, a Political Strategy Advisor | `pol_strat_advisor` | `pages/00_Pol_Strat_Home.py` |
| Act as Mohammad, a USAID Worker | `usaid_worker` | `pages/10_USAID_Worker_Home.py` |
| Act as System Administrator | `administrator` | `pages/20_Admin_Home.py` |

### 4. Calling SideBarLinks on every page

Near the top of `app/src/Home.py` and every page in `app/src/pages/`, there is a call to `SideBarLinks(...)` from `app/src/modules/nav.py`. This function reads the `role` from `session_state` and renders only the links appropriate for that role. Pass `show_home=True` to also render a link back to the Home page — `Home.py` does this; the role pages do not.

`SideBarLinks(...)` also renders the sidebar logo (`app/src/assets/logo.png`) on every page and, for any logged-in user, a **Logout** button at the bottom. Logging out deletes the `role` and `authenticated` keys from `session_state` and returns the user to `Home.py`.

### 5. Page naming convention

Pages use a two-digit numeric prefix to group them by role:

| Prefix range | Role |
|---|---|
| `00_` – `09_` | Political Strategist |
| `10_` – `19_` | USAID Worker |
| `20_` – `29_` | System Administrator |
| `30_` – `39_` | Shared / all roles |

The prefix is organizational only — Streamlit strips it when building the page's URL. `pages/20_Admin_Home.py` is served at `/Admin_Home`, not `/20_Admin_Home`.

A page's prefix groups it with a role but does not by itself put it in that role's sidebar — that is decided by the role branches in `SideBarLinks(...)`. `pages/16_NGO_Profile.py` carries a USAID prefix yet appears in no sidebar, by design (see above).

---

## Adapting RBAC for Your Project

Your team will replace the template roles with the personas relevant to your own project. Here is the recommended sequence of steps.

### Step 1 — Define your personas

Your project defines **four personas**, and you will **implement three of them** in the application. Base them on the stakeholders described in your project proposal (e.g., *Researcher*, *NGO Partner*, *Field Officer*, *Program Director*).

There is no required role. A *System Administrator* persona is one reasonable choice — it is a natural home for system-level chores — but it is not mandatory, and neither is the ML-model management functionality that the template's admin pages demonstrate. Pick the three personas that best exercise your data model.

### Step 2 — Update `Home.py`

For each persona you are implementing, add a button to `app/src/Home.py`. When clicked, the button should set:

```python
st.session_state['authenticated'] = True
st.session_state['role'] = 'your_role_string'
st.session_state['first_name'] = 'Display Name'
st.switch_page('pages/XX_YourRole_Home.py')
```

Remove the buttons for the template roles you are replacing.

### Step 3 — Update `nav.py`

In `app/src/modules/nav.py`, add a sidebar function for each page your new roles need. Follow the existing pattern:

```python
def your_page_nav():
    st.sidebar.page_link('pages/XX_Your_Page.py', label='Page Label', icon='...')
```

Then update the role-dispatch block inside `SideBarLinks(...)` so each of your role strings calls the right set of those functions:

```python
if st.session_state['role'] == 'your_role_string':
    your_role_home_nav()
    your_page_nav()
```

Make sure the role strings here match exactly the strings you set in `Home.py` — a typo means an empty sidebar with no error message.

### Step 4 — Create your pages

Add new page files to `app/src/pages/` using the numbering convention above. Each page should call `SideBarLinks()` near the top, after the imports.

### Step 5 — Delete the template pages you don't need

Once your own pages are in place, remove the example pages that are no longer relevant to your project, along with their `_nav` functions in `nav.py`. Leaving a `st.sidebar.page_link(...)` pointing at a deleted file will raise an error. A page reached only via `st.switch_page(...)` (such as `pages/16_NGO_Profile.py`) has no `_nav` function to remove — delete the calling button instead.

---

## Optional: hardening a page

As shipped, a visitor who opens a page URL in a fresh session is bounced to `Home.py` by `SideBarLinks(...)`. What is *not* checked is whether the logged-in user's role is the right one for the page, nor whether `authenticated` is actually `True` rather than merely present. If you want a page to refuse to render for the wrong user, add an explicit check right after the `SideBarLinks()` call:

```python
if not st.session_state.get('authenticated'):
    st.switch_page('Home.py')

if st.session_state.get('role') != 'your_role_string':
    st.error('You do not have access to this page.')
    st.stop()
```

`st.stop()` halts rendering of the rest of the page, so nothing below it runs. This is not required for the project, but it makes the access-control story in your demo considerably more convincing.

# Roommate Reviewer

A chore tracking and accountability app for shared dorm rooms.

**Team:** Aryaman Mathur · Hutch Turner · Nathan Rabe · Phone Kyaw
CS 3200 — Database Design — Summer B 2026

**Demo video:** [Demo Video YouTube](https://youtu.be/evQs_XJqxgI)

---

## What it does

Shared rooms run on chores nobody tracks. Someone skips the trash, someone else
notices, and there is no record of any of it until the room stops speaking to
each other.

Roommate Reviewer gives a room one place to agree on who does what, mark chores
off as they get done, and raise a flag when they don't. When a room cannot sort
something out on its own, it escalates to the Residence Advisor with the history
already attached.

## Who uses it

The app ships with four personas across three roles. You pick one on the landing
page — there is no real login, the buttons just set a role in the session.

| Persona | Role | What they do |
| --- | --- | --- |
| **Joshua Patel** | Resident | On track: chores done, no strikes, nothing overdue. |
| **Frank Osei** | Resident falling behind | Behind on chores with open strikes and requests, so the same pages tell a very different story. |
| **Carol Diaz** | Residence Advisor | Reviews reports across her rooms, tracks completion rates, manages interventions, and sets the rules. |
| **Sam Reynolds** | System Administrator | Oversight across the whole building: user accounts, RA assignments, dorm occupancy, and the activity log. |

Joshua and Frank are both Residents and share the identical set of seven pages —
a home dashboard plus six feature pages (My Chores, Chore Reports, My Requests,
Ask My RA, Away Dates, My Standing). The two personas exist to show how
differently those same pages read for a resident who is keeping up versus one
who isn't, driven entirely by the data behind each seeded user.

Carol, as the Residence Advisor, has her own home page plus four RA-only feature
pages (Room Reports, Performance, Interventions, Rules). Sam, as the System
Administrator, has a home page plus four admin-only feature pages (Activity Log,
User Accounts, Resident Advisors, Dorms & Occupancy).

## Architecture

Three Docker containers. The front end never talks to the database directly —
every page goes through the REST API.

```
Streamlit  ──HTTP──>  Flask API  ──SQL──>  MySQL
  :8501                 :4000               :3200
```

- **`./app`** — Streamlit front end. One Python file per page in `app/src/pages/`,
  with the sidebar built by role in `app/src/modules/nav.py`.
- **`./api`** — Flask REST API, split into eleven blueprints by resource (users,
  rooms, tasks, requests, room reports, RAs, rules, dorms, away dates,
  interventions, logs).
- **`./database-files`** — `ddl.sql` creates the schema and seeds it. Any `.sql`
  file here runs automatically when the database container is **created**.
- **`./docs`** — project documentation, including the REST route matrix.

## Running it

You need Docker Desktop installed and running.

**1. Create the environment file.** Copy the template and fill in the two
placeholder values:

```bash
cp api/.env.template api/.env
```

Then open `api/.env` and set `SECRET_KEY` to any random string and
`MYSQL_ROOT_PASSWORD` to a password of your choice. Leave the rest alone —
`DB_NAME` must stay `roommate_app`, which is the database `ddl.sql` creates.

**2. Start everything:**

```bash
docker compose up -d
```

**3. Open the app** at [http://localhost:8501](http://localhost:8501).

The API is reachable on its own at `http://localhost:4000` if you want to check
whether a problem is the page or the backend. MySQL is exposed on port `3200`.

### Resetting the database

The seed SQL only runs when the database container is **created**, not when it
restarts. If you change `ddl.sql`, a plain restart will not pick it up — you have
to destroy the volume:

```bash
docker compose down db -v
docker compose up db -d
```

This deletes everything currently in the database and reseeds from `ddl.sql`.

### Picking up code changes

`app/src` and `api/` are mounted into their containers, so editing a page file
and refreshing the browser is enough. Two exceptions:

- Editing `app/src/modules/*.py` needs `docker restart web-app`, because
  Streamlit caches imported modules.
- Editing either `requirements.txt` needs a rebuild: `docker compose build app`
  or `docker compose build api`.

## Documentation

`docs/rest-matrix.md` lists the API routes and which user story each one serves.
The rest of `docs/` covers setup prerequisites, theming, and the role-based
access pattern.

# REST API Matrix — Roommate Reviewer

*The Roomie Reeves · CS 3200 Summer B 2026 · Phase 3 deliverable 1*

Resources are rows, HTTP verbs are columns. Each cell states what the route does and the user
story it serves. An empty cell means that verb is deliberately not offered on that resource.

Story IDs follow the Phase 1+2 submission: `1.x` Arnold Administrator, `2.x` Peter Clean,
`3.x` Ronny RuleBreaker, `4.x` Risha Residence.

Base URL in the Streamlit app is `http://web-api:4000`. Each blueprint is mounted under a
**singular** prefix while the collection path inside it is **plural**, so the full URL reads
`/request/requests`.

---

## Blueprint: `requests` → `/request`

Table: `Requests`. Owner: Po. **Implemented.**

| Resource | GET | POST | PUT | DELETE |
|---|---|---|---|---|
| `/request/requests` | List all requests; filter with `?status=`, `?request_type=`, `?user_id=` — *1.1, 3.5* | File an extension, dispute, expunction, or swap — *3.1, 3.2, 3.3, 3.6* | — | — |
| `/request/requests/{id}` | One request with its involved task attached — *3.5* | — | Approve, reject, or amend a pending request — *3.2, 3.6* | Withdraw a request nobody has voted on; 409 if not `open` — *3.6* |
| `/request/requests/stats` | Total requests plus counts grouped by status and by type — *1.5* | — | — | — |
| `/request/users/{id}/requests` | Every request a given user filed; optional `?status=` — *3.5* | — | — | — |

**Notes.** `Request_Type` is a free `VARCHAR(50)`, so accepted values are validated in the route
layer against `extension`, `dispute`, `expunction`, `swap` (Persona 3) plus `maintenance`,
`chore_swap`, `room_change` (already in the seed data). `Requests.Requested_By_UserID` was added in
Phase 3 — without it a dispute or expunction, which carry `Task_ID = NULL`, could not be traced to
the person who filed it.

---

## Blueprint: `user_away` → `/away`

Table: `UserAway`. Owner: Po. **Implemented.**

| Resource | GET | POST | PUT | DELETE |
|---|---|---|---|---|
| `/away/away` | List away periods; filter with `?user_id=`, `?on_date=` — *3.4* | Mark a date range as away — *3.4* | — | — |
| `/away/away/{id}` | One away period — *3.4* | — | Change the start or end date — *3.4* | Cancel an away period — *3.4* |
| `/away/users/{id}/away` | One user's away periods — *3.4* | — | — | — |
| `/away/rooms/{id}/available` | Roommates *not* away on `?on_date=`, so the rotation can skip whoever is gone — *3.4* | — | — | — |

**Notes.** `UserAway` carries `CHECK (End_Date >= Start_Date)`, which MySQL 9 enforces. POST and PUT
validate the range in Python first so an inverted range returns 400 rather than a raw 500.

---

## Blueprint: `dorms` → `/dorm`

Table: `Dorms`. Owner: Po. **Implemented.**

| Resource | GET | POST | PUT | DELETE |
|---|---|---|---|---|
| `/dorm/dorms` | List all dorms | Add a dorm | — | — |
| `/dorm/dorms/{id}` | One dorm | — | Rename a dorm | Remove a dorm; 409 if it still has rooms |
| `/dorm/dorms/{id}/stats` | Request and report counts for the dorm — *1.4, 4.4* | — | — | — |
| `/dorm/dorms/{id}/users` | Residents of the dorm, joined through `Rooms` — *1.2* | — | — | — |

**Notes.** `Rooms.DormID` is `ON DELETE RESTRICT`, so DELETE pre-checks for child rooms and returns
409 with a readable message. Rooms *within* a dorm are served by Nathan's rooms blueprint at
`/room/dorms/{id}/rooms`; this blueprint deliberately does not duplicate that route.

---

## Blueprint: `room_reports` → `/room_report`

Table: `Room_Reports`. Owner: Hutch, with three GET routes added by Po. **Implemented.**

| Resource | GET | POST | PUT | DELETE |
|---|---|---|---|---|
| `/room_report/room_reports` | List all reports — *2.3, 4.3* | File a report that a task was not done — *2.3* | — | — |
| `/room_report/room_reports/{id}` | One report with its task attached | — | Update status or link it to a request — *4.1* | Remove a report |
| `/room_report/users/{id}/room_reports` | Reports tied to a user; `?role=named` (default) is their strike list, `?role=filed` is reports they submitted — *3.5* | — | — | — |
| `/room_report/users/{id}/standing` | Completion score vs. suite average plus open-strike count — *3.5* | — | — | — |

**Notes.** `Room_Reports.UserID` is the roommate who **filed** the report, not the one blamed —
query 2.3 in the Phase 2 submission inserts Peter's ID when Peter reports a chore someone else
skipped. The blamed roommate is only reachable through `TaskID → Tasks.Assigned_UserID`, which is
why `?role=named` uses an inner join and a report with `TaskID = NULL` can never appear in a strike
list. `open_strikes` on the standing route counts open reports against tasks assigned to the user.

---

## Blueprints owned by teammates

Listed so the matrix covers the whole application. See each owner for detail.

| Blueprint | Prefix | Owner | Routes | Covers |
|---|---|---|---|---|
| `users` | `/user` | Hutch | 11 | Roster, roommates, and task lists filtered by status and by assigned/created — *2.2, 2.5* |
| `tasks` | `/task` | Hutch | 4 | Task CRUD, including marking one complete — *2.1, 2.2, 2.6* |
| `rooms` | `/room` | Nathan | 8 | Rooms, their rules, residents, and assigned RA — *4.1* |
| `ras` | `/ra` | Nathan | 7 | RA roster, their rooms, users, rules, and interventions — *4.2, 4.5* |

---

## Requirement check

Phase 3 asks for at least 4 blueprints, at least 5 routes each, roughly 20 routes total, all four
verbs, at least 2 POST / 2 PUT / 2 DELETE, and no more than one of each write verb inside a single
blueprint.

Counts below for `users`, `tasks`, `room_reports`, `requests`, `user_away`, and `dorms` were read
off the running app's `url_map`. `rooms` and `ras` are counted from Nathan's branch, which has not
merged yet.

| Blueprint | Routes | GET | POST | PUT | DELETE |
|---|---|---|---|---|---|
| `users` | 11 | 9 | 1 | 1 | 0 |
| `tasks` | 4 ⚠️ | 1 | 1 | 1 | 1 |
| `room_reports` | 7 | 4 | 1 | 1 | 1 |
| `rooms` | 8 | 6 | 1 | 1 | 0 |
| `ras` | 7 | 5 | 1 | 1 | 0 |
| `requests` | 7 | 4 | 1 | 1 | 1 |
| `user_away` | 7 | 4 | 1 | 1 | 1 |
| `dorms` | 7 | 4 | 1 | 1 | 1 |
| **Total** | **58** | **37** | **8** | **8** | **5** |

Every threshold is met except one: **`tasks` has 4 routes and needs a 5th** — a GET by id is the
obvious addition. No blueprint exceeds one POST, one PUT, or one DELETE.

The boilerplate `simple_routes` blueprint contributes a further 6 GET routes but is sample code that
Phase 3 requirement 4c says to delete, so it is excluded from the table above.

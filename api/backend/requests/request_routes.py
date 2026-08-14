from datetime import datetime

from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from backend.tasks.task_routes import _apply_counter_change
from mysql.connector import Error

# Create a Blueprint for Request routes
requests = Blueprint("request", __name__)

# Request_Type is a free VARCHAR(50) in the schema rather than an ENUM, so the accepted
# values are enforced here instead. 'chore_swap' used to sit alongside 'swap' as a second
# name for the same thing, which meant every page that acted on a swap had to test for
# both; the seed rows now say 'swap'. maintenance and room_change are older vocabulary
# with no form behind them, kept so existing rows still validate.
VALID_REQUEST_TYPES = {
    "extension",
    "dispute",
    "expunction",
    "swap",
    "maintenance",
    "room_change",
}

# Mirrors the ENUM on Requests.Status
VALID_STATUSES = {"open", "in_progress", "resolved", "rejected"}


def _valid_date(value):
    """True if value is a YYYY-MM-DD date string. Used to reject bad dates with a
    400 instead of letting MySQL raise and surface as a 500."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


# Get all requests, with optional filtering by status, type, and the user who filed them
# Example: /request/requests?status=open&request_type=extension&user_id=4
@requests.route("/requests", methods=["GET"])
def get_all_requests():
    cursor = get_db().cursor(dictionary=True)
    try:
        current_app.logger.info('GET /request/requests')

        status = request.args.get("status")
        request_type = request.args.get("request_type")
        user_id = request.args.get("user_id")
        ra_id = request.args.get("ra_id")

        # A request has no room of its own -- it belongs to whoever filed it, and that
        # resident lives in a room with an RA. Both chores' names travel with the row,
        # because a request that says "swap task 495 for task 494" is unreadable.
        query = """
            SELECT r.*,
                   u.First_Name, u.Last_Name, u.DormID, u.Room_Number,
                   given.Task_Name  AS given_name,  given.due_date  AS given_due,
                   -- Who holds the chore now. A decided request is only readable next to
                   -- this: "resolved" on a swap means nothing until the row can say the
                   -- chore actually changed hands.
                   given.Assigned_UserID AS given_owner,
                   want.Task_Name   AS wanted_name, want.due_date   AS wanted_due,
                   want.Assigned_UserID AS wanted_owner
            FROM Requests r
            LEFT JOIN Users u    ON u.UserID = r.Requested_By_UserID
            LEFT JOIN Tasks given ON given.Task_ID = r.Task_ID
            LEFT JOIN Tasks want  ON want.Task_ID = r.Offered_Task_ID
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND r.Status = %s"
            params.append(status)
        if request_type:
            query += " AND r.Request_Type = %s"
            params.append(request_type)
        if user_id:
            query += " AND r.Requested_By_UserID = %s"
            params.append(user_id)
        if ra_id:
            query += """
                AND EXISTS (
                    SELECT 1 FROM Rooms rm
                    WHERE rm.RA = %s
                      AND rm.DormID = u.DormID AND rm.Room_Number = u.Room_Number
                )
            """
            params.append(ra_id)

        query += " ORDER BY r.Created_At DESC"

        cursor.execute(query, params)
        request_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(request_list)} Requests')
        return jsonify(request_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_all_requests: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Summary counts for the admin dashboard tiles (user story 1.5)
# Declared alongside /requests/<int:request_id>; the int converter means "stats"
# can never match that rule, so declaration order does not matter.
# Example: /request/requests/stats
@requests.route("/requests/stats", methods=["GET"])
def get_request_stats():
    cursor = get_db().cursor(dictionary=True)
    try:
        current_app.logger.info('GET /request/requests/stats')

        cursor.execute("SELECT COUNT(*) AS total FROM Requests")
        total = cursor.fetchone()["total"]

        cursor.execute("SELECT Status, COUNT(*) AS total FROM Requests GROUP BY Status")
        by_status = cursor.fetchall()

        cursor.execute("SELECT Request_Type, COUNT(*) AS total FROM Requests GROUP BY Request_Type")
        by_type = cursor.fetchall()

        return jsonify({
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
        }), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_request_stats: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get a single request along with the task it involves, if any
# Example: /request/requests/5
@requests.route("/requests/<int:request_id>", methods=["GET"])
def get_request(request_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Requests WHERE Request_ID = %s", (request_id,))
        req = cursor.fetchone()

        if not req:
            return jsonify({"error": "Request not found"}), 404

        # Reuse the same cursor for the follow-up query
        if req["Task_ID"] is not None:
            cursor.execute("SELECT * FROM Tasks WHERE Task_ID = %s", (req["Task_ID"],))
            req["task"] = cursor.fetchone()
        else:
            req["task"] = None

        return jsonify(req), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_request: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get every request a given user has filed (user story 3.5 - "requests I'm waiting on")
# Example: /request/users/4/requests
@requests.route("/users/<int:user_id>/requests", methods=["GET"])
def get_user_requests(user_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (user_id,))
        if not cursor.fetchone():
            return jsonify({"error": "User not found"}), 404

        status = request.args.get("status")

        query = "SELECT * FROM Requests WHERE Requested_By_UserID = %s"
        params = [user_id]

        if status:
            query += " AND Status = %s"
            params.append(status)

        query += " ORDER BY Created_At DESC"

        cursor.execute(query, params)
        request_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(request_list)} Requests for user {user_id}')
        return jsonify(request_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_user_requests: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# File a new request - extension, dispute, expunction, or swap
# (user stories 3.1, 3.2, 3.3, 3.6)
@requests.route("/requests", methods=["POST"])
def create_new_request():
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        required_fields = [
            "Request_Type",
            "Requested_By_UserID",
        ]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        if data["Request_Type"] not in VALID_REQUEST_TYPES:
            return jsonify({
                "error": f"Invalid request type. Must be one of: {', '.join(sorted(VALID_REQUEST_TYPES))}"
            }), 400

        if "Status" in data and data["Status"] not in VALID_STATUSES:
            return jsonify({"error": "Invalid status type"}), 400

        if data.get("Proposed_Due_Date") is not None and not _valid_date(data["Proposed_Due_Date"]):
            return jsonify({"error": "Proposed_Due_Date must be a date in YYYY-MM-DD format"}), 400

        # Confirm the filing user exists before inserting, so a bad ID gives a clear
        # 404 rather than a raw foreign key error
        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (data["Requested_By_UserID"],))
        if not cursor.fetchone():
            return jsonify({"error": "User not found"}), 404

        # Task_ID is optional: an expunction challenges a report rather than a chore, so
        # it carries no task reference. Offered_Task_ID is the chore wanted in return on
        # a two-sided swap, and is optional even there.
        for field in ("Task_ID", "Offered_Task_ID"):
            if data.get(field) is not None:
                cursor.execute("SELECT Task_ID FROM Tasks WHERE Task_ID = %s", (data[field],))
                if not cursor.fetchone():
                    return jsonify({"error": f"{field} does not name an existing chore"}), 404

        # Trading a chore for itself is not a trade.
        if (data.get("Offered_Task_ID") is not None
                and data.get("Offered_Task_ID") == data.get("Task_ID")):
            return jsonify({
                "error": "A swap has to name two different chores."
            }), 400

        # One live request of a kind per chore per person. A second dispute over the same
        # miss, or a second extension on the same deadline, is not a stronger case -- it
        # is two rows in front of whoever decides, and acting on either leaves the other
        # pointing at a chore that has already moved. This is the same rule the expunction
        # check below applies to strikes.
        if data.get("Task_ID") is not None:
            cursor.execute(
                """
                    SELECT Request_ID FROM Requests
                    WHERE Task_ID = %s AND Requested_By_UserID = %s
                      AND Request_Type = %s AND Status IN ('open', 'in_progress')
                """,
                (data["Task_ID"], data["Requested_By_UserID"], data["Request_Type"]),
            )
            if cursor.fetchone():
                return jsonify({
                    "error": f"You already have a {data['Request_Type']} waiting on a "
                             "decision for this chore."
                }), 409

        # An expunction asks for one specific strike to come off, so it names the report
        # it is about. My Standing used to file the request and then PUT the link onto
        # the report as a second call: pressing the button twice created two requests and
        # the second link overwrote the first, leaving an appeal in the RA's queue that
        # pointed at nothing and could never be carried out. Both halves happen here, in
        # one transaction, and a report that already has an appeal in flight refuses a
        # second one rather than quietly stacking them up.
        report_id = data.get("ReportID")
        if report_id is not None:
            if data["Request_Type"] != "expunction":
                return jsonify({
                    "error": "ReportID belongs to an expunction; other request types name "
                             "a chore rather than a report."
                }), 400

            cursor.execute(
                """
                    SELECT rp.ReportID, rp.Status, rp.RequestID, t.Assigned_UserID,
                           ap.Status AS appeal_status
                    FROM Room_Reports rp
                    LEFT JOIN Tasks t     ON t.Task_ID = rp.TaskID
                    LEFT JOIN Requests ap ON ap.Request_ID = rp.RequestID
                    WHERE rp.ReportID = %s
                """,
                (report_id,),
            )
            report = cursor.fetchone()
            if not report:
                return jsonify({"error": "Report not found"}), 404

            # Only the resident the report names can ask for it to come off.
            if (report["Assigned_UserID"] is not None
                    and int(data["Requested_By_UserID"]) != int(report["Assigned_UserID"])):
                return jsonify({
                    "error": "You can only appeal a report that names you."
                }), 409

            if report["Status"] != "open":
                return jsonify({
                    "error": "This report has already been ruled on, so there is no open "
                             "strike to clear."
                }), 409

            if report["appeal_status"] in ("open", "in_progress"):
                return jsonify({
                    "error": "You have already asked for this strike to be cleared. Your "
                             "RA still has that appeal."
                }), 409

        query = """
                    INSERT INTO Requests
                        (Status, Reason, Request_Type, Proposed_Due_Date, Task_ID,
                         Offered_Task_ID, Requested_By_UserID)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
        cursor.execute(query, (
            data.get("Status", "open"),
            data.get("Reason"),
            data["Request_Type"],
            data.get("Proposed_Due_Date"),
            data.get("Task_ID"),
            data.get("Offered_Task_ID"),
            data["Requested_By_UserID"],
        ))
        new_request_id = cursor.lastrowid

        # Same transaction as the insert, so an appeal can never exist without the report
        # it is appealing.
        if report_id is not None:
            cursor.execute(
                "UPDATE Room_Reports SET RequestID = %s WHERE ReportID = %s",
                (new_request_id, report_id),
            )

        get_db().commit()
        current_app.logger.info(f'Created Request {new_request_id}')
        return jsonify({"message": "Request created successfully", "Request_ID": new_request_id}), 201

    # Error handling
    except Error as e:
        current_app.logger.error(f'Database error in create_new_request: {e}')
        return jsonify({"error": str(e)}), 500

    # Final clean up
    finally:
        cursor.close()


def _resolve_effect(cursor, req, accepted_by):
    """Do the thing the request was asking for. Returns a short description, or None.

    Resolving used to mean nothing but turning the row green. An approved extension left
    the deadline where it was, an approved dispute left the chore marked missed, and an
    approved expunction left the strike standing -- so three of the four request types
    were decorative, and a resident could be told yes and see nothing change. The effect
    belongs here rather than in the page so it cannot be skipped or half-applied.
    """
    kind, task_id = req["Request_Type"], req["Task_ID"]

    if kind == "extension":
        if task_id is None or req["Proposed_Due_Date"] is None:
            return None
        cursor.execute("UPDATE Tasks SET due_date = %s WHERE Task_ID = %s",
                       (req["Proposed_Due_Date"], task_id))
        return f"deadline moved to {req['Proposed_Due_Date']:%b %d, %Y}"

    if kind == "swap":
        if task_id is None or accepted_by is None:
            return None
        # The chore being given up goes to whoever accepted. Status returns to 'todo' so
        # it lands in their To do tab rather than arriving pre-marked.
        cursor.execute(
            "SELECT status, Assigned_UserID FROM Tasks WHERE Task_ID = %s", (task_id,))
        given = cursor.fetchone()
        if not given:
            return None
        cursor.execute(
            "UPDATE Tasks SET Assigned_UserID = %s, status = 'todo' WHERE Task_ID = %s",
            (accepted_by, task_id))
        _apply_counter_change(cursor, given["status"], given["Assigned_UserID"],
                              "todo", accepted_by)
        moved = "chore reassigned"

        # A two-sided swap: the chore the requester asked for in return goes back to them.
        if req["Offered_Task_ID"] is not None:
            cursor.execute(
                "SELECT status, Assigned_UserID FROM Tasks WHERE Task_ID = %s",
                (req["Offered_Task_ID"],))
            wanted = cursor.fetchone()
            if wanted:
                cursor.execute(
                    "UPDATE Tasks SET Assigned_UserID = %s, status = 'todo' "
                    "WHERE Task_ID = %s",
                    (req["Requested_By_UserID"], req["Offered_Task_ID"]))
                _apply_counter_change(cursor, wanted["status"], wanted["Assigned_UserID"],
                                      "todo", req["Requested_By_UserID"])
                moved = "chores traded both ways"
        return moved

    if kind == "dispute":
        # The resident said the miss was unfair and the RA agreed, so the chore goes back
        # to being open and the mark comes off their record.
        if task_id is None:
            return None
        cursor.execute(
            "SELECT status, Assigned_UserID FROM Tasks WHERE Task_ID = %s", (task_id,))
        task = cursor.fetchone()
        if not task or task["status"] != "missed":
            return None
        cursor.execute("UPDATE Tasks SET status = 'todo' WHERE Task_ID = %s", (task_id,))
        _apply_counter_change(cursor, "missed", task["Assigned_UserID"],
                              "todo", task["Assigned_UserID"])
        # The reports that put it there are settled by the same ruling; leaving them open
        # would keep counting as strikes for a mark that no longer exists.
        cursor.execute(
            "UPDATE Room_Reports SET Status = 'closed', "
            "Reviewed_At = COALESCE(Reviewed_At, NOW()) "
            "WHERE TaskID = %s AND Status = 'open'",
            (task_id,))
        return "chore un-marked and its reports closed"

    if kind == "expunction":
        # An expunction asks for a specific report to come off the record. The link is
        # Room_Reports.RequestID, set when the resident files it from My Standing.
        cursor.execute(
            "UPDATE Room_Reports SET Status = 'closed', "
            "Reviewed_At = COALESCE(Reviewed_At, NOW()) "
            "WHERE RequestID = %s AND Status = 'open'",
            (req["Request_ID"],))
        return "strike cleared" if cursor.rowcount else None

    return None


# Approve, reject, or otherwise amend an existing request
# (user stories 3.2 and 3.6 - the roommate verdict on a pending request)
#
# Moving a request to 'resolved' carries out what it asked for, in the same transaction.
# Pass accepted_by on a swap to say who is taking the chore on.
@requests.route("/requests/<int:request_id>", methods=["PUT"])
def update_request(request_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        data = request.get_json()

        cursor.execute(
            """
                SELECT Request_ID, Status, Request_Type, Task_ID, Offered_Task_ID,
                       Proposed_Due_Date, Requested_By_UserID
                FROM Requests WHERE Request_ID = %s
            """,
            (request_id,),
        )
        existing = cursor.fetchone()
        if not existing:
            return jsonify({"error": "Request not found"}), 404

        if "Status" in data and data["Status"] not in VALID_STATUSES:
            return jsonify({"error": "Invalid status type"}), 400

        if "Request_Type" in data and data["Request_Type"] not in VALID_REQUEST_TYPES:
            return jsonify({
                "error": f"Invalid request type. Must be one of: {', '.join(sorted(VALID_REQUEST_TYPES))}"
            }), 400

        if data.get("Proposed_Due_Date") is not None and not _valid_date(data["Proposed_Due_Date"]):
            return jsonify({"error": "Proposed_Due_Date must be a date in YYYY-MM-DD format"}), 400

        # Same pre-check as the create route, so reassigning a request to a task that
        # does not exist gives a 404 rather than a raw foreign key error
        if data.get("Task_ID") is not None:
            cursor.execute("SELECT Task_ID FROM Tasks WHERE Task_ID = %s", (data["Task_ID"],))
            if not cursor.fetchone():
                return jsonify({"error": "Task not found"}), 404

        # Build update query dynamically based on provided fields
        allowed_fields = ["Status", "Reason", "Request_Type", "Proposed_Due_Date",
                          "Task_ID", "Offered_Task_ID"]
        update_fields = [f"{f} = %s" for f in allowed_fields if f in data]
        params = [data[f] for f in allowed_fields if f in data]

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(request_id)
        query = f"UPDATE Requests SET {', '.join(update_fields)} WHERE Request_ID = %s"
        cursor.execute(query, params)

        # Only the crossing into 'resolved' carries the request out. Re-saving an already
        # resolved request must not move a deadline or trade a chore a second time.
        effect = None
        if data.get("Status") == "resolved" and existing["Status"] != "resolved":
            merged = dict(existing)
            for field in ("Task_ID", "Offered_Task_ID", "Proposed_Due_Date",
                          "Request_Type"):
                if field in data:
                    merged[field] = data[field]
            effect = _resolve_effect(cursor, merged, data.get("accepted_by"))

        db.commit()

        current_app.logger.info(f'Updated Request {request_id}')
        return jsonify({"message": "Request updated successfully",
                        "effect": effect}), 200
    except Error as e:
        db.rollback()
        current_app.logger.error(f'Database error in update_request: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Withdraw a request that nobody has voted on yet (user story 3.6)
@requests.route("/requests/<int:request_id>", methods=["DELETE"])
def delete_request(request_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT Request_ID, Status FROM Requests WHERE Request_ID = %s", (request_id,))
        req = cursor.fetchone()

        if not req:
            return jsonify({"error": "Request not found"}), 404

        # Only an untouched request can be withdrawn. Once roommates have acted on it
        # the row is part of the record and stays put.
        if req["Status"] != "open":
            return jsonify({
                "error": f"Only requests with status 'open' can be withdrawn; this one is '{req['Status']}'"
            }), 409

        cursor.execute("DELETE FROM Requests WHERE Request_ID = %s", (request_id,))
        get_db().commit()

        current_app.logger.info(f'Deleted Request {request_id}')
        return jsonify({"message": "Request deleted successfully"}), 200

    except Error as e:
        current_app.logger.error(f'Database error in delete_request: {e}')
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()

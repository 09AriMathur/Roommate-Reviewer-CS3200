from datetime import datetime

from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from mysql.connector import Error

# Create a Blueprint for Request routes
requests = Blueprint("request", __name__)

# Request_Type is a free VARCHAR(50) in the schema rather than an ENUM, so the
# accepted values are enforced here instead. This is the union of two vocabularies:
# the four Persona 3 (Ronny RuleBreaker) actions, and the three values already
# present in the seed data. Normalising these to one set is a team decision.
VALID_REQUEST_TYPES = {
    "extension",
    "dispute",
    "expunction",
    "swap",
    "maintenance",
    "chore_swap",
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

        # WHERE 1=1 lets us append AND clauses cleanly without special-casing the first filter
        query = "SELECT * FROM Requests WHERE 1=1"
        params = []

        if status:
            query += " AND Status = %s"
            params.append(status)
        if request_type:
            query += " AND Request_Type = %s"
            params.append(request_type)
        if user_id:
            query += " AND Requested_By_UserID = %s"
            params.append(user_id)

        query += " ORDER BY Created_At DESC"

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

        # Task_ID is optional: dispute and expunction requests challenge a report
        # rather than a task, so they carry no task reference
        if data.get("Task_ID") is not None:
            cursor.execute("SELECT Task_ID FROM Tasks WHERE Task_ID = %s", (data["Task_ID"],))
            if not cursor.fetchone():
                return jsonify({"error": "Task not found"}), 404

        query = """
                    INSERT INTO Requests
                        (Status, Reason, Request_Type, Proposed_Due_Date, Task_ID, Requested_By_UserID)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
        cursor.execute(query, (
            data.get("Status", "open"),
            data.get("Reason"),
            data["Request_Type"],
            data.get("Proposed_Due_Date"),
            data.get("Task_ID"),
            data["Requested_By_UserID"],
        ))

        get_db().commit()
        current_app.logger.info(f'Created Request {cursor.lastrowid}')
        return jsonify({"message": "Request created successfully", "Request_ID": cursor.lastrowid}), 201

    # Error handling
    except Error as e:
        current_app.logger.error(f'Database error in create_new_request: {e}')
        return jsonify({"error": str(e)}), 500

    # Final clean up
    finally:
        cursor.close()


# Approve, reject, or otherwise amend an existing request
# (user stories 3.2 and 3.6 - the roommate verdict on a pending request)
@requests.route("/requests/<int:request_id>", methods=["PUT"])
def update_request(request_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        cursor.execute("SELECT Request_ID FROM Requests WHERE Request_ID = %s", (request_id,))
        if not cursor.fetchone():
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
        allowed_fields = ["Status", "Reason", "Request_Type", "Proposed_Due_Date", "Task_ID"]
        update_fields = [f"{f} = %s" for f in allowed_fields if f in data]
        params = [data[f] for f in allowed_fields if f in data]

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(request_id)
        query = f"UPDATE Requests SET {', '.join(update_fields)} WHERE Request_ID = %s"
        cursor.execute(query, params)
        get_db().commit()

        current_app.logger.info(f'Updated Request {request_id}')
        return jsonify({"message": "Request updated successfully"}), 200
    except Error as e:
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

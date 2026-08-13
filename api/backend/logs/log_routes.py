from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from mysql.connector import Error

# Blueprint for the System Admin activity-log routes (Persona 1 - Arnold Administrator).
# Table: Logs. Mounted at prefix "/log" in rest_entry.py, so the full paths read
# like "/log/logs". Every log row records that a user did something, optionally
# reviewed by a System_Admin (ReviewerID).
logs = Blueprint("log", __name__)


# ---------------------------------------------------------------------------
# GET /log/logs
# List all activity-log entries. Optional filters let an admin narrow the feed:
#   ?user_id=      only actions taken by this user
#   ?reviewer_id=  only entries reviewed by this admin
# Example: /log/logs?user_id=2
# ---------------------------------------------------------------------------
@logs.route("/logs", methods=["GET"])
def get_all_logs():
    cursor = get_db().cursor(dictionary=True)
    try:
        current_app.logger.info('GET /log/logs')

        user_id = request.args.get("user_id")
        reviewer_id = request.args.get("reviewer_id")

        # WHERE 1=1 lets us append AND clauses without special-casing the first one
        query = "SELECT * FROM Logs WHERE 1=1"
        params = []

        if user_id:
            query += " AND UserId = %s"
            params.append(user_id)
        if reviewer_id:
            query += " AND ReviewerID = %s"
            params.append(reviewer_id)

        query += " ORDER BY Timestamp DESC"

        cursor.execute(query, params)
        log_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(log_list)} Logs')
        return jsonify(log_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_all_logs: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# GET /log/logs/<id>
# One specific log entry by its ID.
# ---------------------------------------------------------------------------
@logs.route("/logs/<int:log_id>", methods=["GET"])
def get_log(log_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Logs WHERE Log_Id = %s", (log_id,))
        log = cursor.fetchone()

        if not log:
            return jsonify({"error": "Log not found"}), 404

        return jsonify(log), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_log: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# GET /log/users/<id>/logs
# Every log entry tied to one user - their activity history.
# ---------------------------------------------------------------------------
@logs.route("/users/<int:user_id>/logs", methods=["GET"])
def get_user_logs(user_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        # Confirm the user exists first, so a bad ID gives a clear 404
        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (user_id,))
        if not cursor.fetchone():
            return jsonify({"error": "User not found"}), 404

        cursor.execute(
            "SELECT * FROM Logs WHERE UserId = %s ORDER BY Timestamp DESC",
            (user_id,),
        )
        log_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(log_list)} Logs for user {user_id}')
        return jsonify(log_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_user_logs: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# POST /log/logs
# Record a new activity-log entry.
# Body (JSON): { "UserId": 2, "Action": "Marked task #1 as done", "ReviewerID": 1 }
#   UserId + Action are required; ReviewerID is optional.
# ---------------------------------------------------------------------------
@logs.route("/logs", methods=["POST"])
def create_log():
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        required_fields = ["UserId", "Action"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # The user the action belongs to must exist (clear 404 instead of a raw FK error)
        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (data["UserId"],))
        if not cursor.fetchone():
            return jsonify({"error": "User not found"}), 404

        query = """
                    INSERT INTO Logs (UserId, Action, ReviewerID)
                    VALUES (%s, %s, %s)
                """
        cursor.execute(query, (
            data["UserId"],
            data["Action"],
            data.get("ReviewerID"),
        ))

        get_db().commit()
        current_app.logger.info(f'Created Log {cursor.lastrowid}')
        return jsonify({"message": "Log created successfully", "Log_Id": cursor.lastrowid}), 201
    except Error as e:
        current_app.logger.error(f'Database error in create_log: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# PUT /log/logs/<id>
# Amend a log entry - most often to stamp it with the admin who reviewed it.
# Body (JSON): any of { "Action": "...", "ReviewerID": 1 }
# ---------------------------------------------------------------------------
@logs.route("/logs/<int:log_id>", methods=["PUT"])
def update_log(log_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        cursor.execute("SELECT Log_Id FROM Logs WHERE Log_Id = %s", (log_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Log not found"}), 404

        # Build the UPDATE dynamically from whichever allowed fields were sent
        allowed_fields = ["Action", "ReviewerID"]
        update_fields = [f"{f} = %s" for f in allowed_fields if f in data]
        params = [data[f] for f in allowed_fields if f in data]

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(log_id)
        query = f"UPDATE Logs SET {', '.join(update_fields)} WHERE Log_Id = %s"
        cursor.execute(query, params)
        get_db().commit()

        current_app.logger.info(f'Updated Log {log_id}')
        return jsonify({"message": "Log updated successfully"}), 200
    except Error as e:
        current_app.logger.error(f'Database error in update_log: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# DELETE /log/logs/<id>
# Remove a log entry.
# ---------------------------------------------------------------------------
@logs.route("/logs/<int:log_id>", methods=["DELETE"])
def delete_log(log_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT Log_Id FROM Logs WHERE Log_Id = %s", (log_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Log not found"}), 404

        cursor.execute("DELETE FROM Logs WHERE Log_Id = %s", (log_id,))
        get_db().commit()

        current_app.logger.info(f'Deleted Log {log_id}')
        return jsonify({"message": "Log deleted successfully"}), 200
    except Error as e:
        current_app.logger.error(f'Database error in delete_log: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

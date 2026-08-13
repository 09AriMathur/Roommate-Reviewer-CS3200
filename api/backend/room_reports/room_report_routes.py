from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from mysql.connector import Error

# Create a Blueprint for Room Report routes
room_reports = Blueprint("room_report", __name__)


def _as_number(value):
    """MySQL ROUND() returns a DECIMAL, which Flask serializes as a JSON *string*
    ("62.5" rather than 62.5). Charts in the Streamlit app need real numbers, so
    percentages are coerced before they go out. NULL stays None."""
    return None if value is None else float(value)

# Get all room reports
@room_reports.route("/room_reports", methods=["GET"])
def get_all_room_reports():
    cursor = get_db().cursor(dictionary=True)
    try:
        query = "SELECT * FROM Room_Reports WHERE 1=1"
        cursor.execute(query)

        report_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(report_list)} Room Reports')
        return jsonify(report_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_all_room_reports: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

# Create a new room report
@room_reports.route("/room_reports", methods=["POST"])
def create_new_room_report():
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()
        
        required_fields = [
            "TaskID",
            "UserID",
            "Description"
        ]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # A report accuses someone of skipping a chore, so the chore has to exist --
        # and both rules below depend on who it belongs to and when it was due.
        cursor.execute(
            """
                SELECT Task_ID, Task_Name, Assigned_UserID, status, due_date,
                       (due_date IS NOT NULL AND due_date < CURDATE()) AS past_due
                FROM Tasks
                WHERE Task_ID = %s
            """,
            (data["TaskID"],),
        )
        task = cursor.fetchone()

        if not task:
            return jsonify({"error": "Task not found"}), 404

        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (data["UserID"],))
        if not cursor.fetchone():
            return jsonify({"error": "User not found"}), 404

        # Room_Reports.UserID is the person filing; the person being accused is the
        # task's assignee. Those being equal means someone reported themselves.
        if (task["Assigned_UserID"] is not None
                and int(data["UserID"]) == int(task["Assigned_UserID"])):
            return jsonify({
                "error": "You cannot file a report about a chore assigned to you."
            }), 409

        # "This was not done" only means anything once the deadline has passed. A
        # chore already marked missed is fair game whatever its due date says, and a
        # chore with no due date has no deadline to have blown.
        if task["status"] != "missed" and not task["past_due"]:
            if task["due_date"] is None:
                detail = (f"\"{task['Task_Name']}\" has no due date, so it cannot be "
                          "reported as incomplete.")
            else:
                detail = (f"\"{task['Task_Name']}\" is not due until "
                          f"{task['due_date']:%B %d, %Y}, so it cannot be reported as "
                          "incomplete yet.")
            return jsonify({"error": detail}), 409

        # One open report per chore per filer. Without this the same person can press
        # the button three times on one chore and push the assignee to the RA
        # escalation threshold over a single missed job.
        cursor.execute(
            """
                SELECT ReportID FROM Room_Reports
                WHERE TaskID = %s AND UserID = %s AND Status = 'open'
            """,
            (data["TaskID"], data["UserID"]),
        )
        if cursor.fetchone():
            return jsonify({
                "error": f"You already have an open report on \"{task['Task_Name']}\"."
            }), 409

        query = """
                    INSERT INTO Room_Reports (TaskID, UserID, Description)
                    VALUES (%s, %s, %s)
                """
        cursor.execute(query, (
            data["TaskID"],
            data["UserID"],
            data["Description"]
        ))

        get_db().commit()
        return jsonify({"message": "Room Report created successfully", "ReportID": cursor.lastrowid}), 201

    # Error handling
    except Error as e:
        return jsonify({"error": str(e)}), 500

    # Final clean up
    finally:
        cursor.close()


# Update an existing room report
@room_reports.route("/room_reports/<report_id>", methods=["PUT"])
def update_room_report(report_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        cursor.execute("SELECT ReportID FROM Room_Reports WHERE ReportID = %s", (report_id,))
        report = cursor.fetchone()
        if not report:
            return jsonify({"error": "Room Report not found"}), 404

        VALID_STATUSES = {"open", "reviewed", "closed"}
        if "Status" in data and data["Status"] not in VALID_STATUSES:
            return jsonify({"error": "Invalid status type"}), 400

        # Build update query dynamically based on provided fields
        allowed_fields = ["Status", "RequestID"]
        update_fields = [f"{f} = %s" for f in allowed_fields if f in data]
        params = [data[f] for f in allowed_fields if f in data]

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(report_id)
        query = f"UPDATE Room_Reports SET {', '.join(update_fields)} WHERE ReportID = %s"
        cursor.execute(query, params)
        get_db().commit()

        return jsonify({"message": "Room Report updated successfully"}), 200
    except Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

# Delete an existing room report
@room_reports.route("/room_reports/<report_id>", methods=["DELETE"])
def delete_room_report(report_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT ReportID FROM Room_Reports WHERE ReportID = %s", (report_id,))
        report = cursor.fetchone()

        if not report:
            return jsonify({"error": "Room Report not found"}), 404

        cursor.execute("DELETE FROM Room_Reports WHERE ReportID = %s", (report_id,))
        get_db().commit()

        return jsonify({"message": "Room Report deleted successfully"}), 200

    except Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()


# Get a single room report along with the task it concerns
# Example: /room_report/room_reports/1
@room_reports.route("/room_reports/<int:report_id>", methods=["GET"])
def get_room_report(report_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Room_Reports WHERE ReportID = %s", (report_id,))
        report = cursor.fetchone()

        if not report:
            return jsonify({"error": "Room Report not found"}), 404

        # Reuse the same cursor for the follow-up query
        if report["TaskID"] is not None:
            cursor.execute("SELECT * FROM Tasks WHERE Task_ID = %s", (report["TaskID"],))
            report["task"] = cursor.fetchone()
        else:
            report["task"] = None

        return jsonify(report), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_room_report: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Reports connected to a given user, in one of two directions:
#
#   ?role=named (default) - reports about a task assigned to this user. This is the
#       strike list behind user story 3.5; a strike is an open report against you.
#   ?role=filed           - reports this user submitted about someone else.
#
# The distinction matters because Room_Reports.UserID is the *filer*, not the person
# blamed (see query 2.3 in the Phase 2 submission, where UserID is Peter reporting a
# chore he did not do). The blamed user is only reachable through the task, so a report
# with TaskID = NULL cannot be attributed to anyone and never appears under role=named.
# Mirrors the ?type=assigned/created convention already used by the users blueprint.
# Example: /room_report/users/4/room_reports?role=named&status=open
@room_reports.route("/users/<int:user_id>/room_reports", methods=["GET"])
def get_user_room_reports(user_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (user_id,))
        if not cursor.fetchone():
            return jsonify({"error": "User not found"}), 404

        role = request.args.get("role", "named")
        if role not in ("named", "filed"):
            return jsonify({"error": "role must be either 'named' or 'filed'"}), 400

        status = request.args.get("status")

        if role == "filed":
            query = """
                        SELECT rp.*, t.Task_Name, t.due_date, t.Assigned_UserID
                        FROM Room_Reports rp
                        LEFT JOIN Tasks t ON rp.TaskID = t.Task_ID
                        WHERE rp.UserID = %s
                    """
        else:
            # INNER JOIN, not LEFT: a report with no task has nobody it can name
            query = """
                        SELECT rp.*, t.Task_Name, t.due_date, t.Assigned_UserID
                        FROM Room_Reports rp
                        JOIN Tasks t ON rp.TaskID = t.Task_ID
                        WHERE t.Assigned_UserID = %s
                    """
        params = [user_id]

        if status:
            query += " AND rp.Status = %s"
            params.append(status)

        query += " ORDER BY rp.Time_Reported DESC"

        cursor.execute(query, params)
        report_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(report_list)} Room Reports ({role}) for user {user_id}')
        return jsonify(report_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_user_room_reports: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# A user's accountability standing: completion score, open strike count, the suite
# average, and the per-roommate comparison. This is user story 3.5, and it mirrors
# query 3.5 from the Phase 2 submission.
# Example: /room_report/users/4/standing
@room_reports.route("/users/<int:user_id>/standing", methods=["GET"])
def get_user_standing(user_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        query = """
                    SELECT UserID, First_Name, Last_Name, DormID, Room_Number,
                           TasksCompleted, TasksMissed,
                           ROUND(TasksCompleted /
                                 NULLIF(TasksCompleted + TasksMissed, 0) * 100, 1) AS completion_pct
                    FROM Users
                    WHERE UserID = %s
                """
        cursor.execute(query, (user_id,))
        me = cursor.fetchone()

        if not me:
            return jsonify({"error": "User not found"}), 404

        # A strike is an open report about a task assigned to this user. Room_Reports.UserID
        # is the filer, so the blamed user is reached through Tasks.Assigned_UserID.
        # DISTINCT on the task: a strike is a chore you skipped, not a complaint. Two
        # roommates reporting the same missed chore is one strike, not two.
        query = """
                    SELECT COUNT(DISTINCT rp.TaskID) AS total
                    FROM Room_Reports rp
                    JOIN Tasks t ON rp.TaskID = t.Task_ID
                    WHERE t.Assigned_UserID = %s
                      AND rp.Status = 'open'
                """
        cursor.execute(query, (user_id,))
        open_strikes = cursor.fetchone()["total"]

        # A user with no room has no suite to compare against, and matching on a NULL
        # room key would match nothing, so handle that case rather than returning an
        # empty comparison that looks like a score of zero.
        suite_avg_pct = None
        roommates = []
        if me["DormID"] is not None:
            query = """
                        SELECT ROUND(AVG(TasksCompleted /
                               NULLIF(TasksCompleted + TasksMissed, 0)) * 100, 1) AS suite_avg_pct
                        FROM Users
                        WHERE DormID = %s AND Room_Number = %s
                    """
            cursor.execute(query, (me["DormID"], me["Room_Number"]))
            suite_avg_pct = cursor.fetchone()["suite_avg_pct"]

            query = """
                        SELECT UserID, First_Name, Last_Name,
                               TasksCompleted, TasksMissed,
                               ROUND(TasksCompleted /
                                     NULLIF(TasksCompleted + TasksMissed, 0) * 100, 1) AS completion_pct
                        FROM Users
                        WHERE DormID = %s AND Room_Number = %s
                        ORDER BY completion_pct DESC, UserID
                    """
            cursor.execute(query, (me["DormID"], me["Room_Number"]))
            roommates = cursor.fetchall()
            for mate in roommates:
                mate["completion_pct"] = _as_number(mate["completion_pct"])

        return jsonify({
            "UserID": me["UserID"],
            "First_Name": me["First_Name"],
            "Last_Name": me["Last_Name"],
            "DormID": me["DormID"],
            "Room_Number": me["Room_Number"],
            "TasksCompleted": me["TasksCompleted"],
            "TasksMissed": me["TasksMissed"],
            "completion_pct": _as_number(me["completion_pct"]),
            "open_strikes": open_strikes,
            "suite_avg_pct": _as_number(suite_avg_pct),
            "roommates": roommates,
        }), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_user_standing: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
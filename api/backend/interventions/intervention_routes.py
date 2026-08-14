from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from mysql.connector import Error

# An intervention is a resident asking their RA to step in, and the RA working through
# it. It used to live on the RA blueprint, which meant that blueprint carried two POST
# routes and, more to the point, there was nowhere at all for the RA half of the
# exchange: the table had no PUT, so every case a resident filed sat at 'pending' for
# ever and the RA pages could only read them.
interventions = Blueprint("intervention", __name__)

VALID_STATUSES = ("pending", "active", "closed")

# Only a closed case is settled work. Moving one back to active undoes that.
SETTLED_STATUS = "closed"


# List interventions, narrowed by RA, resident, or status.
# Example: /intervention/interventions?ra_id=1&status=pending
#
# Names travel with each row. The RA pages used to fetch every intervention for every RA
# in the building and match ids in Python, which also meant a resident's page received
# the case notes of everyone else that RA manages.
@interventions.route("/interventions", methods=["GET"])
def get_interventions():
    cursor = get_db().cursor(dictionary=True)
    try:
        ra_id = request.args.get("ra_id")
        user_id = request.args.get("user_id")
        status = request.args.get("status")

        if status and status not in VALID_STATUSES:
            return jsonify({
                "error": f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"
            }), 400

        query = """
            SELECT i.*,
                   u.First_Name, u.Last_Name, u.DormID, u.Room_Number,
                   r.First_Name AS ra_first, r.Last_Name AS ra_last
            FROM RA_Intervention i
            JOIN Users u ON u.UserID = i.UserID
            LEFT JOIN RAs r ON r.RA_ID = i.RA
            WHERE 1=1
        """
        params = []
        if ra_id:
            query += " AND i.RA = %s"
            params.append(ra_id)
        if user_id:
            query += " AND i.UserID = %s"
            params.append(user_id)
        if status:
            query += " AND i.Status = %s"
            params.append(status)

        query += " ORDER BY i.RequestID DESC"
        cursor.execute(query, params)
        return jsonify(cursor.fetchall()), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_interventions: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get a single intervention by id, with the same resident/RA names joined in as the list route.
@interventions.route("/interventions/<int:request_id>", methods=["GET"])
def get_intervention(request_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute(
            """
                SELECT i.*,
                       u.First_Name, u.Last_Name, u.DormID, u.Room_Number,
                       r.First_Name AS ra_first, r.Last_Name AS ra_last
                FROM RA_Intervention i
                JOIN Users u ON u.UserID = i.UserID
                LEFT JOIN RAs r ON r.RA_ID = i.RA
                WHERE i.RequestID = %s
            """,
            (request_id,),
        )
        intervention = cursor.fetchone()
        if not intervention:
            return jsonify({"error": "Intervention not found"}), 404

        return jsonify(intervention), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_intervention: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Counts of interventions grouped by status, for the admin/RA dashboards.
@interventions.route("/interventions/stats", methods=["GET"])
def get_intervention_stats():
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) AS total FROM RA_Intervention")
        total = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT Status, COUNT(*) AS count FROM RA_Intervention GROUP BY Status"
        )
        by_status = cursor.fetchall()

        return jsonify({"total": total, "by_status": by_status}), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_intervention_stats: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# File an intervention. The RA is looked up server-side from the resident's own Users.RA
# column rather than trusted from the body, so a resident can only ever file against
# their own assigned RA.
@interventions.route("/interventions", methods=["POST"])
def create_intervention():
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        required_fields = ["UserID", "Description"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        cursor.execute("SELECT RA FROM Users WHERE UserID = %s", (data["UserID"],))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
        if not user["RA"]:
            return jsonify({"error": "User has no assigned RA"}), 400

        cursor.execute(
            """
                INSERT INTO RA_Intervention (Description, Status, UserID, RA)
                VALUES (%s, %s, %s, %s)
            """,
            (data["Description"], "pending", data["UserID"], user["RA"]),
        )
        get_db().commit()

        return jsonify({
            "message": "Intervention created successfully",
            "RequestID": cursor.lastrowid,
        }), 201
    except Error as e:
        current_app.logger.error(f'Database error in create_intervention: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# The RA half: move a case through pending -> active -> closed.
#
# Closing one bumps that RA's Settled_Reqs. Those counters are shown on the admin's RA
# roster as though they were live, and nothing in the app had ever incremented them, so
# they only ever read back whatever the seed file happened to say.
@interventions.route("/interventions/<int:request_id>", methods=["PUT"])
def update_intervention(request_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        data = request.get_json()

        if "Status" not in data:
            return jsonify({"error": "Missing required field: Status"}), 400
        if data["Status"] not in VALID_STATUSES:
            return jsonify({
                "error": f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"
            }), 400

        cursor.execute(
            "SELECT RequestID, Status, RA FROM RA_Intervention WHERE RequestID = %s",
            (request_id,),
        )
        intervention = cursor.fetchone()
        if not intervention:
            return jsonify({"error": "Intervention not found"}), 404

        before, after = intervention["Status"], data["Status"]
        cursor.execute(
            "UPDATE RA_Intervention SET Status = %s WHERE RequestID = %s",
            (after, request_id),
        )

        # Only the crossing counts, in either direction, so reopening a case gives the
        # credit back rather than leaving it banked.
        if intervention["RA"] is not None and before != after:
            if after == SETTLED_STATUS:
                cursor.execute(
                    "UPDATE RAs SET Settled_Reqs = Settled_Reqs + 1 WHERE RA_ID = %s",
                    (intervention["RA"],),
                )
            elif before == SETTLED_STATUS:
                cursor.execute(
                    "UPDATE RAs SET Settled_Reqs = GREATEST(Settled_Reqs - 1, 0) "
                    "WHERE RA_ID = %s",
                    (intervention["RA"],),
                )

        db.commit()
        return jsonify({"message": "Intervention updated successfully"}), 200
    except Error as e:
        db.rollback()
        current_app.logger.error(f'Database error in update_intervention: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

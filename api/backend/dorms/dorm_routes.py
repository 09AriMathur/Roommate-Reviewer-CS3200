from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from mysql.connector import Error

# Create a Blueprint for Dorm routes
dorms = Blueprint("dorm", __name__)


# Get all dorms, optionally filtered by name
# Example: /dorm/dorms?name=North
@dorms.route("/dorms", methods=["GET"])
def get_all_dorms():
    cursor = get_db().cursor(dictionary=True)
    try:
        current_app.logger.info('GET /dorm/dorms')

        name = request.args.get("name")

        # WHERE 1=1 lets us append AND clauses cleanly without special-casing the first filter
        query = "SELECT * FROM Dorms WHERE 1=1"
        params = []

        if name:
            query += " AND Dorm_Name LIKE %s"
            params.append(f"%{name}%")

        query += " ORDER BY Dorm_Name"

        cursor.execute(query, params)
        dorm_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(dorm_list)} Dorms')
        return jsonify(dorm_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_all_dorms: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get a single dorm
# Example: /dorm/dorms/1
@dorms.route("/dorms/<int:dorm_id>", methods=["GET"])
def get_dorm(dorm_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Dorms WHERE DormID = %s", (dorm_id,))
        dorm = cursor.fetchone()

        if not dorm:
            return jsonify({"error": "Dorm not found"}), 404

        return jsonify(dorm), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_dorm: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Activity totals for a dorm plus a per-room breakdown of where the trouble is.
# Serves the admin's requests-by-residence-hall chart (1.4) and the RA's
# "which rooms have the most issues" view (4.4).
# Example: /dorm/dorms/1/stats
@dorms.route("/dorms/<int:dorm_id>/stats", methods=["GET"])
def get_dorm_stats(dorm_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Dorms WHERE DormID = %s", (dorm_id,))
        dorm = cursor.fetchone()
        if not dorm:
            return jsonify({"error": "Dorm not found"}), 404

        cursor.execute("SELECT COUNT(*) AS total FROM Rooms WHERE DormID = %s", (dorm_id,))
        room_count = cursor.fetchone()["total"]

        query = """
                    SELECT COUNT(*) AS total
                    FROM Users u
                    JOIN Rooms rm ON u.DormID = rm.DormID AND u.Room_Number = rm.Room_Number
                    WHERE rm.DormID = %s
                """
        cursor.execute(query, (dorm_id,))
        resident_count = cursor.fetchone()["total"]

        # Requests are attributed through Requested_By_UserID, so this counts requests
        # filed by anyone living in the dorm
        query = """
                    SELECT COUNT(*) AS total,
                           SUM(rq.Status = 'open') AS open_total
                    FROM Requests rq
                    JOIN Users u  ON rq.Requested_By_UserID = u.UserID
                    JOIN Rooms rm ON u.DormID = rm.DormID AND u.Room_Number = rm.Room_Number
                    WHERE rm.DormID = %s
                """
        cursor.execute(query, (dorm_id,))
        request_row = cursor.fetchone()

        query = """
                    SELECT COUNT(*) AS total,
                           SUM(rp.Status = 'open') AS open_total
                    FROM Room_Reports rp
                    JOIN Users u  ON rp.UserID = u.UserID
                    JOIN Rooms rm ON u.DormID = rm.DormID AND u.Room_Number = rm.Room_Number
                    WHERE rm.DormID = %s
                """
        cursor.execute(query, (dorm_id,))
        report_row = cursor.fetchone()

        # COUNT(DISTINCT ...) because joining both Room_Reports and Requests to the same
        # users fans the rows out; a plain COUNT would multiply the two together
        query = """
                    SELECT rm.DormID,
                           rm.Room_Number,
                           COUNT(DISTINCT rp.ReportID)   AS report_count,
                           COUNT(DISTINCT rq.Request_ID) AS request_count
                    FROM Rooms rm
                    LEFT JOIN Users u        ON u.DormID = rm.DormID AND u.Room_Number = rm.Room_Number
                    LEFT JOIN Room_Reports rp ON rp.UserID = u.UserID
                    LEFT JOIN Requests rq     ON rq.Requested_By_UserID = u.UserID
                    WHERE rm.DormID = %s
                    GROUP BY rm.DormID, rm.Room_Number
                    ORDER BY report_count DESC, request_count DESC
                """
        cursor.execute(query, (dorm_id,))
        by_room = cursor.fetchall()

        return jsonify({
            "DormID": dorm["DormID"],
            "Dorm_Name": dorm["Dorm_Name"],
            "room_count": room_count,
            "resident_count": resident_count,
            "request_count": request_row["total"],
            "open_request_count": int(request_row["open_total"] or 0),
            "report_count": report_row["total"],
            "open_report_count": int(report_row["open_total"] or 0),
            "by_room": by_room,
        }), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_dorm_stats: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Everyone living in a dorm, joined through Rooms. Rooms themselves are served by
# the rooms blueprint at /room/dorms/<dorm_id>/rooms, so they are not repeated here.
# Example: /dorm/dorms/1/users
@dorms.route("/dorms/<int:dorm_id>/users", methods=["GET"])
def get_dorm_users(dorm_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT DormID FROM Dorms WHERE DormID = %s", (dorm_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Dorm not found"}), 404

        query = """
                    SELECT u.UserID, u.First_Name, u.Last_Name, u.Email,
                           u.DormID, u.Room_Number, u.TasksCompleted, u.TasksMissed
                    FROM Users u
                    JOIN Rooms rm ON u.DormID = rm.DormID AND u.Room_Number = rm.Room_Number
                    WHERE rm.DormID = %s
                    ORDER BY rm.Room_Number, u.UserID
                """
        cursor.execute(query, (dorm_id,))
        user_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(user_list)} residents of dorm {dorm_id}')
        return jsonify(user_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_dorm_users: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Add a dorm
@dorms.route("/dorms", methods=["POST"])
def create_new_dorm():
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        required_fields = [
            "Dorm_Name",
        ]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        if not str(data["Dorm_Name"]).strip():
            return jsonify({"error": "Dorm_Name cannot be empty"}), 400

        query = """
                    INSERT INTO Dorms (Dorm_Name)
                    VALUES (%s)
                """
        cursor.execute(query, (data["Dorm_Name"].strip(),))

        get_db().commit()
        current_app.logger.info(f'Created Dorm {cursor.lastrowid}')
        return jsonify({"message": "Dorm created successfully", "DormID": cursor.lastrowid}), 201

    # Error handling
    except Error as e:
        current_app.logger.error(f'Database error in create_new_dorm: {e}')
        return jsonify({"error": str(e)}), 500

    # Final clean up
    finally:
        cursor.close()


# Rename a dorm
@dorms.route("/dorms/<int:dorm_id>", methods=["PUT"])
def update_dorm(dorm_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        cursor.execute("SELECT DormID FROM Dorms WHERE DormID = %s", (dorm_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Dorm not found"}), 404

        if "Dorm_Name" in data and not str(data["Dorm_Name"]).strip():
            return jsonify({"error": "Dorm_Name cannot be empty"}), 400

        # Build update query dynamically based on provided fields
        allowed_fields = ["Dorm_Name"]
        update_fields = [f"{f} = %s" for f in allowed_fields if f in data]
        params = [data[f] for f in allowed_fields if f in data]

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(dorm_id)
        query = f"UPDATE Dorms SET {', '.join(update_fields)} WHERE DormID = %s"
        cursor.execute(query, params)
        get_db().commit()

        current_app.logger.info(f'Updated Dorm {dorm_id}')
        return jsonify({"message": "Dorm updated successfully"}), 200
    except Error as e:
        current_app.logger.error(f'Database error in update_dorm: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Remove a dorm. Rooms.DormID is ON DELETE RESTRICT, so a dorm that still has rooms
# cannot be removed; pre-check for them and say so rather than surfacing a raw FK error.
@dorms.route("/dorms/<int:dorm_id>", methods=["DELETE"])
def delete_dorm(dorm_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT DormID FROM Dorms WHERE DormID = %s", (dorm_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Dorm not found"}), 404

        cursor.execute("SELECT COUNT(*) AS total FROM Rooms WHERE DormID = %s", (dorm_id,))
        room_count = cursor.fetchone()["total"]
        if room_count > 0:
            return jsonify({
                "error": f"Cannot delete a dorm that still has rooms; this one has {room_count}. "
                         "Move or remove its rooms first."
            }), 409

        cursor.execute("DELETE FROM Dorms WHERE DormID = %s", (dorm_id,))
        get_db().commit()

        current_app.logger.info(f'Deleted Dorm {dorm_id}')
        return jsonify({"message": "Dorm deleted successfully"}), 200

    except Error as e:
        current_app.logger.error(f'Database error in delete_dorm: {e}')
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()

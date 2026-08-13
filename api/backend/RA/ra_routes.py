from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from mysql.connector import Error

# Create a Blueprint for RA routes
ras = Blueprint("ras", __name__)


# Get all RAs
# Example: /ras
@ras.route("/ras", methods=["GET"])
def get_all_ras():
    cursor = get_db().cursor(dictionary=True)
    try:
        current_app.logger.info('GET /ras')

        cursor.execute("SELECT * FROM RAs")
        ra_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(ra_list)} RAs')
        return jsonify(ra_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_all_ras: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get detailed information about a specific RA
# Example: /ras/1
@ras.route("/ras/<int:ra_id>", methods=["GET"])
def get_ra(ra_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM RAs WHERE RA_ID = %s", (ra_id,))
        ra = cursor.fetchone()

        if not ra:
            return jsonify({"error": "RA not found"}), 404

        return jsonify(ra), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_ra: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Create a new RA
# Required fields: First_Name, Last_Name, Email
# Optional: Settled_Reqs, Settled_Reps
# Example: POST /ras with JSON body
@ras.route("/ras", methods=["POST"])
def create_ra():
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        required_fields = ["First_Name", "Last_Name", "Email"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        query = """
            INSERT INTO RAs (First_Name, Last_Name, Email, Settled_Reqs, Settled_Reps)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            data["First_Name"],
            data["Last_Name"],
            data["Email"],
            data.get("Settled_Reqs", 0),
            data.get("Settled_Reps", 0),
        ))

        get_db().commit()
        return jsonify({"message": "RA created successfully", "ra_id": cursor.lastrowid}), 201
    except Error as e:
        if e.errno == 1062:  # duplicate entry on unique Email
            return jsonify({"error": "An RA with that email already exists"}), 409
        current_app.logger.error(f'Database error in create_ra: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Update an existing RA's information
# Can update First_Name, Last_Name, Email, Settled_Reqs, Settled_Reps
# Example: PUT /ras/1 with JSON body containing fields to update
@ras.route("/ras/<int:ra_id>", methods=["PUT"])
def update_ra(ra_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        cursor.execute("SELECT RA_ID FROM RAs WHERE RA_ID = %s", (ra_id,))
        if not cursor.fetchone():
            return jsonify({"error": "RA not found"}), 404

        allowed_fields = ["First_Name", "Last_Name", "Email", "Settled_Reqs", "Settled_Reps"]
        update_fields = [f"{f} = %s" for f in allowed_fields if f in data]
        params = [data[f] for f in allowed_fields if f in data]

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(ra_id)
        query = f"UPDATE RAs SET {', '.join(update_fields)} WHERE RA_ID = %s"
        cursor.execute(query, params)
        get_db().commit()

        return jsonify({"message": "RA updated successfully"}), 200
    except Error as e:
        if e.errno == 1062:
            return jsonify({"error": "An RA with that email already exists"}), 409
        current_app.logger.error(f'Database error in update_ra: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get all rooms under a specific RA.
# Rooms don't FK directly to RAs, so this is derived via the users
# assigned to each room: any room housing a user whose Users.RA points
# to this RA counts as "under" that RA.
# Example: /ras/1/rooms
@ras.route("/ras/<int:ra_id>/rooms", methods=["GET"])
def get_ra_rooms(ra_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT RA_ID FROM RAs WHERE RA_ID = %s", (ra_id,))
        if not cursor.fetchone():
            return jsonify({"error": "RA not found"}), 404

        query = """
            SELECT DISTINCT r.*
            FROM Rooms r
            JOIN Users u ON u.DormID = r.DormID AND u.Room_Number = r.Room_Number
            WHERE u.RA = %s
        """
        cursor.execute(query, (ra_id,))
        return jsonify(cursor.fetchall()), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_ra_rooms: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get all users under a specific RA
# Example: /ras/1/users
@ras.route("/ras/<int:ra_id>/users", methods=["GET"])
def get_ra_users(ra_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT RA_ID FROM RAs WHERE RA_ID = %s", (ra_id,))
        if not cursor.fetchone():
            return jsonify({"error": "RA not found"}), 404

        cursor.execute("SELECT * FROM Users WHERE RA = %s", (ra_id,))
        return jsonify(cursor.fetchall()), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_ra_users: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get all rules created by a specific RA
# Example: /ras/1/rules
@ras.route("/ras/<int:ra_id>/rules", methods=["GET"])
def get_ra_rules(ra_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT RA_ID FROM RAs WHERE RA_ID = %s", (ra_id,))
        if not cursor.fetchone():
            return jsonify({"error": "RA not found"}), 404

        cursor.execute("SELECT * FROM Rules WHERE RA_ID = %s", (ra_id,))
        return jsonify(cursor.fetchall()), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_ra_rules: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get all interventions being managed by a specific RA
# Example: /ras/1/interventions
@ras.route("/ras/<int:ra_id>/interventions", methods=["GET"])
def get_ra_interventions(ra_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT RA_ID FROM RAs WHERE RA_ID = %s", (ra_id,))
        if not cursor.fetchone():
            return jsonify({"error": "RA not found"}), 404

        cursor.execute("SELECT * FROM RA_Intervention WHERE RA = %s", (ra_id,))
        return jsonify(cursor.fetchall()), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_ra_interventions: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Create a new intervention request filed by a student.
# The RA is always looked up server-side from the student's own Users.RA
# column rather than trusted from the request body, so a student can only
# ever file against their own assigned RA.
# Required fields: UserID, Description
# Example: POST /ras/interventions with JSON body
@ras.route("/ras/interventions", methods=["POST"])
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

        query = """
            INSERT INTO RA_Intervention (Description, Status, UserID, RA)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (data["Description"], "pending", data["UserID"], user["RA"]))
        get_db().commit()

        return jsonify({"message": "Intervention created successfully", "RequestID": cursor.lastrowid}), 201
    except Error as e:
        current_app.logger.error(f'Database error in create_intervention: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
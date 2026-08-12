from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from mysql.connector import Error

# Create a Blueprint for Room routes
rooms = Blueprint("rooms", __name__)


# Get all rooms, with optional filtering by dorm
# Example: /rooms?dorm_id=1
@rooms.route("/rooms", methods=["GET"])
def get_all_rooms():
    cursor = get_db().cursor(dictionary=True)
    try:
        current_app.logger.info('GET /rooms')

        dorm_id = request.args.get("dorm_id")

        query = "SELECT * FROM Rooms WHERE 1=1"
        params = []

        if dorm_id:
            query += " AND DormID = %s"
            params.append(dorm_id)

        cursor.execute(query, params)
        room_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(room_list)} rooms')
        return jsonify(room_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_all_rooms: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get detailed information about a specific room
# Example: /rooms/1
@rooms.route("/rooms/<int:room_id>", methods=["GET"])
def get_room(room_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Rooms WHERE RoomID = %s", (room_id,))
        room = cursor.fetchone()

        if not room:
            return jsonify({"error": "Room not found"}), 404

        return jsonify(room), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_room: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Create a new room
# Required fields: DormID, Room_Number
# Optional: RA (denormalized name field on Rooms)
# Example: POST /rooms with JSON body
@rooms.route("/rooms", methods=["POST"])
def create_room():
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        required_fields = ["DormID", "Room_Number"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Confirm the dorm exists before inserting (FK is ON DELETE RESTRICT,
        # but this gives a clearer 404 instead of a raw FK error)
        cursor.execute("SELECT DormID FROM Dorms WHERE DormID = %s", (data["DormID"],))
        if not cursor.fetchone():
            return jsonify({"error": "Dorm not found"}), 404

        query = """
            INSERT INTO Rooms (DormID, Room_Number, RA)
            VALUES (%s, %s, %s)
        """
        cursor.execute(query, (
            data["DormID"],
            data["Room_Number"],
            data.get("RA"),
        ))

        get_db().commit()
        return jsonify({"message": "Room created successfully", "room_id": cursor.lastrowid}), 201
    except Error as e:
        if e.errno == 1062:  # duplicate entry on (DormID, Room_Number)
            return jsonify({"error": "A room with that number already exists in this dorm"}), 409
        current_app.logger.error(f'Database error in create_room: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Update an existing room's information
# Can update DormID, Room_Number, and/or RA
# Example: PUT /rooms/1 with JSON body containing fields to update
@rooms.route("/rooms/<int:room_id>", methods=["PUT"])
def update_room(room_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        cursor.execute("SELECT RoomID FROM Rooms WHERE RoomID = %s", (room_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Room not found"}), 404

        if "DormID" in data:
            cursor.execute("SELECT DormID FROM Dorms WHERE DormID = %s", (data["DormID"],))
            if not cursor.fetchone():
                return jsonify({"error": "Dorm not found"}), 404

        # Build update query dynamically based on provided fields
        allowed_fields = ["DormID", "Room_Number", "RA"]
        update_fields = [f"{f} = %s" for f in allowed_fields if f in data]
        params = [data[f] for f in allowed_fields if f in data]

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(room_id)
        query = f"UPDATE Rooms SET {', '.join(update_fields)} WHERE RoomID = %s"
        cursor.execute(query, params)
        get_db().commit()

        return jsonify({"message": "Room updated successfully"}), 200
    except Error as e:
        if e.errno == 1062:
            return jsonify({"error": "A room with that number already exists in this dorm"}), 409
        current_app.logger.error(f'Database error in update_room: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get all rules associated with a specific room
# Example: /rooms/1/rules
@rooms.route("/rooms/<int:room_id>/rules", methods=["GET"])
def get_room_rules(room_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT RoomID FROM Rooms WHERE RoomID = %s", (room_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Room not found"}), 404

        cursor.execute("SELECT * FROM Rules WHERE RoomID = %s", (room_id,))
        return jsonify(cursor.fetchall()), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_room_rules: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get all users assigned to a specific room
# Example: /rooms/1/users
@rooms.route("/rooms/<int:room_id>/users", methods=["GET"])
def get_room_users(room_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT RoomID FROM Rooms WHERE RoomID = %s", (room_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Room not found"}), 404

        cursor.execute("SELECT * FROM Users WHERE RoomID = %s", (room_id,))
        return jsonify(cursor.fetchall()), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_room_users: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get the RA assigned to a specific room.
# Derived via Users.RA -> RAs, since Rooms.RA is just a denormalized name
# string and not an actual foreign key. Also returns the raw Rooms.RA text
# for comparison in case the two have drifted out of sync.
# Example: /rooms/1/ra
@rooms.route("/rooms/<int:room_id>/ra", methods=["GET"])
def get_room_ra(room_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT RoomID, RA AS Room_RA_Label FROM Rooms WHERE RoomID = %s", (room_id,))
        room = cursor.fetchone()

        if not room:
            return jsonify({"error": "Room not found"}), 404

        query = """
            SELECT DISTINCT r.UserID, r.First_Name, r.Last_Name, r.Email,
                   r.RA_ID, r.Settled_Reqs, r.Settled_Reps, r.Year
            FROM RAs r
            JOIN Users u ON u.RA = r.UserID
            WHERE u.RoomID = %s
        """
        cursor.execute(query, (room_id,))
        ra_list = cursor.fetchall()

        return jsonify({
            "room_id": room_id,
            "room_ra_label": room["Room_RA_Label"],
            "ra": ra_list
        }), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_room_ra: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get all rooms in a specific dorm
# Example: /dorms/1/rooms
@rooms.route("/dorms/<int:dorm_id>/rooms", methods=["GET"])
def get_dorm_rooms(dorm_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT DormID FROM Dorms WHERE DormID = %s", (dorm_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Dorm not found"}), 404

        cursor.execute("SELECT * FROM Rooms WHERE DormID = %s", (dorm_id,))
        return jsonify(cursor.fetchall()), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_dorm_rooms: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
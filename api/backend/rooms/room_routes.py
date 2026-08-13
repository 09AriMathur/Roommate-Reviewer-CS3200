from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from backend.users.user_routes import VALID_TASK_STATUSES
from mysql.connector import Error

# Create a Blueprint for Room routes
rooms = Blueprint("rooms", __name__)

# Rooms is a weak entity owned by Dorms: a room number only identifies a room within
# its dorm, so every single-room route is addressed as /dorms/<dorm_id>/rooms/<number>
# rather than by a surrogate id. That also means an RA can look a room up by the two
# things they actually know -- the building and the number on the door.


def _room_exists(cursor, dorm_id, room_number):
    cursor.execute(
        "SELECT 1 FROM Rooms WHERE DormID = %s AND Room_Number = %s",
        (dorm_id, room_number),
    )
    return cursor.fetchone() is not None


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

        query += " ORDER BY DormID, Room_Number"
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
# Example: /dorms/2/rooms/201
@rooms.route("/dorms/<int:dorm_id>/rooms/<int:room_number>", methods=["GET"])
def get_room(dorm_id, room_number):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM Rooms WHERE DormID = %s AND Room_Number = %s",
            (dorm_id, room_number),
        )
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
# Optional: RA (foreign key referencing RAs.RA_ID)
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
        # The key is the pair the caller supplied; there is no generated id to return.
        return jsonify({
            "message": "Room created successfully",
            "DormID": data["DormID"],
            "Room_Number": data["Room_Number"],
        }), 201
    except Error as e:
        if e.errno == 1062:  # duplicate entry on the (DormID, Room_Number) key
            return jsonify({"error": "A room with that number already exists in this dorm"}), 409
        current_app.logger.error(f'Database error in create_room: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Update an existing room's information
# Only RA is updatable: DormID and Room_Number are the room's identity, and changing
# them would mean renaming the key that Users and Rules point at.
# Example: PUT /dorms/2/rooms/201 with JSON body containing fields to update
@rooms.route("/dorms/<int:dorm_id>/rooms/<int:room_number>", methods=["PUT"])
def update_room(dorm_id, room_number):
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        if not _room_exists(cursor, dorm_id, room_number):
            return jsonify({"error": "Room not found"}), 404

        if "RA" not in data:
            return jsonify({"error": "No valid fields to update"}), 400

        if data["RA"] is not None:
            cursor.execute("SELECT RA_ID FROM RAs WHERE RA_ID = %s", (data["RA"],))
            if not cursor.fetchone():
                return jsonify({"error": "RA not found"}), 404

        cursor.execute(
            "UPDATE Rooms SET RA = %s WHERE DormID = %s AND Room_Number = %s",
            (data["RA"], dorm_id, room_number),
        )
        get_db().commit()

        return jsonify({"message": "Room updated successfully"}), 200
    except Error as e:
        current_app.logger.error(f'Database error in update_room: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get all rules associated with a specific room
# Example: /dorms/2/rooms/201/rules
@rooms.route("/dorms/<int:dorm_id>/rooms/<int:room_number>/rules", methods=["GET"])
def get_room_rules(dorm_id, room_number):
    cursor = get_db().cursor(dictionary=True)
    try:
        if not _room_exists(cursor, dorm_id, room_number):
            return jsonify({"error": "Room not found"}), 404

        cursor.execute(
            "SELECT * FROM Rules WHERE DormID = %s AND Room_Number = %s",
            (dorm_id, room_number),
        )
        return jsonify(cursor.fetchall()), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_room_rules: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get all users assigned to a specific room
# Example: /dorms/2/rooms/201/users
@rooms.route("/dorms/<int:dorm_id>/rooms/<int:room_number>/users", methods=["GET"])
def get_room_users(dorm_id, room_number):
    cursor = get_db().cursor(dictionary=True)
    try:
        if not _room_exists(cursor, dorm_id, room_number):
            return jsonify({"error": "Room not found"}), 404

        cursor.execute(
            "SELECT * FROM Users WHERE DormID = %s AND Room_Number = %s",
            (dorm_id, room_number),
        )
        return jsonify(cursor.fetchall()), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_room_users: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get every chore belonging to a room, optionally narrowed by status.
# Example: /dorms/3/rooms/406/tasks?status=todo,in_progress
#
# A chore has no room of its own -- it belongs to whoever is assigned it -- so the room
# it lives in is only reachable through the assignee. Deriving that here means the suite
# chart and the RA's room lookup ask one question instead of each pulling the whole
# Tasks table and filtering it in Python.
@rooms.route("/dorms/<int:dorm_id>/rooms/<int:room_number>/tasks", methods=["GET"])
def get_room_tasks(dorm_id, room_number):
    cursor = get_db().cursor(dictionary=True)
    try:
        if not _room_exists(cursor, dorm_id, room_number):
            return jsonify({"error": "Room not found"}), 404

        statuses = [s.strip() for s in request.args.get("status", "").split(",") if s.strip()]
        invalid = [s for s in statuses if s not in VALID_TASK_STATUSES]
        if invalid:
            return jsonify({
                "error": f"Invalid status: {', '.join(invalid)}. "
                         f"Must be one of: {', '.join(sorted(VALID_TASK_STATUSES))}"
            }), 400

        # The assignee's name travels with the chore: the point of a room-wide list is
        # seeing whose turn each one landed on.
        query = """
            SELECT t.*, u.First_Name, u.Last_Name
            FROM Tasks t
            JOIN Users u ON t.Assigned_UserID = u.UserID
            WHERE u.DormID = %s AND u.Room_Number = %s
        """
        params = [dorm_id, room_number]
        if statuses:
            query += f" AND t.status IN ({', '.join(['%s'] * len(statuses))})"
            params.extend(statuses)
        query += " ORDER BY t.due_date, t.Task_ID"

        cursor.execute(query, params)
        return jsonify(cursor.fetchall()), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_room_tasks: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get the RA assigned to a specific room.
# Rooms.RA is a foreign key to RAs.RA_ID, so this just looks up that RA
# directly rather than deriving it through Users.
# Example: /dorms/2/rooms/201/ra
@rooms.route("/dorms/<int:dorm_id>/rooms/<int:room_number>/ra", methods=["GET"])
def get_room_ra(dorm_id, room_number):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT RA FROM Rooms WHERE DormID = %s AND Room_Number = %s",
            (dorm_id, room_number),
        )
        room = cursor.fetchone()

        if not room:
            return jsonify({"error": "Room not found"}), 404

        ra = None
        if room["RA"] is not None:
            cursor.execute("SELECT * FROM RAs WHERE RA_ID = %s", (room["RA"],))
            ra = cursor.fetchone()

        return jsonify({
            "DormID": dorm_id,
            "Room_Number": room_number,
            "ra": ra,
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

        cursor.execute(
            "SELECT * FROM Rooms WHERE DormID = %s ORDER BY Room_Number", (dorm_id,)
        )
        return jsonify(cursor.fetchall()), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_dorm_rooms: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

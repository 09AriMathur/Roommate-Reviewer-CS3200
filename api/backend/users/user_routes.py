from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from mysql.connector import Error

# Create a Blueprint for User routes
users = Blueprint("user", __name__)

@users.route("/users", methods=["GET"])
def get_all_users():
    cursor = get_db().cursor(dictionary=True)
    try:
        current_app.logger.info('GET /user/users')

        query = "SELECT * FROM Users"
        params = []

        cursor.execute(query, params)
        user_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(user_list)} Users')
        return jsonify(user_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_all_users: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

# Get a specific user based on user ID
@users.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Users WHERE UserID = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify(user), 200
    except Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

# Get a specific user and related tasks based on user ID
@users.route("/users/<int:user_id>/tasks", methods=["GET"])
def get_user_tasks(user_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Users WHERE UserID = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Reuse the same cursor for the follow-up queries
        cursor.execute("SELECT * FROM Tasks WHERE Created_UserID = %s", (user_id,))
        user["created_tasks"] = cursor.fetchall()

        cursor.execute("SELECT * FROM Tasks WHERE Assigned_UserID = %s", (user_id,))
        user["assigned_tasks"] = cursor.fetchall()

        return jsonify(user), 200
    except Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

# Create a new user
@users.route("/users", methods=["POST"])
def create_new_user():
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()
        
        required_fields = [
            "First_Name",
            "Last_Name",
            "Email",
            "RA",
            "RoomID",
        ]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
            
        query = """
                    INSERT INTO Users (First_Name, Last_Name, Email, RA, RoomID)
                    VALUES (%s, %s, %s, %s, %s)
                """
        cursor.execute(query, (
            data["First_Name"],
            data["Last_Name"],
            data["Email"],
            data["RA"],
            data["RoomID"],
        ))

        get_db().commit()
        return jsonify({"message": "User created successfully", "UserID": cursor.lastrowid}), 201

    # Error handling
    except Error as e:
        return jsonify({"error": str(e)}), 500

    # Final clean up
    finally:
        cursor.close()


# Update a users existing information
@users.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):

    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (user_id,))
        if not cursor.fetchone():
            return jsonify({"error": "User not found"}), 404

        # Build update query dynamically based on provided fields
        allowed_fields = ["RA", "RoomID", "TasksCompleted", "TasksMissed"]
        update_fields = [f"{f} = %s" for f in allowed_fields if f in data]
        params = [data[f] for f in allowed_fields if f in data]

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(user_id)
        query = f"UPDATE Users SET {', '.join(update_fields)} WHERE UserID = %s"
        cursor.execute(query, params)
        get_db().commit()

        return jsonify({"message": "User updated successfully"}), 200
    except Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get assigned tasks related to a specific user
@users.route("/users/<int:user_id>/tasks/assigned", methods=["GET"])
def get_assigned_tasks(user_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (user_id,))
        user = cursor.fetchone()

        # Reuse the same cursor for the follow-up queries
        cursor.execute("SELECT * FROM Tasks WHERE Assigned_UserID = %s", (user_id,))
        user["assigned_tasks"] = cursor.fetchall()

        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify(user), 200

    except Error as e:
        current_app.logger.error(f'Database error in get_assigned_tasks: {e}')
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()


# Get created tasks related to a specific user
@users.route("/users/<int:user_id>/tasks/created", methods=["GET"])
def get_created_tasks(user_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Reuse the same cursor for the follow-up queries
        cursor.execute("SELECT * FROM Tasks WHERE Created_UserID = %s", (user_id,))
        user["created_tasks"] = cursor.fetchall()

        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify(user), 200

    except Error as e:
        current_app.logger.error(f'Database error in get_created_tasks: {e}')
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()

# Get completed tasks related to a specific user
@users.route("/users/<int:user_id>/tasks/completed", methods=["GET"])
def get_completed_tasks(user_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Reuse the same cursor for the follow-up queries
        cursor.execute("SELECT * FROM Tasks WHERE Assigned_UserID = %s AND status = 'done'", (user_id,))
        user["completed_tasks"] = cursor.fetchall()

        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify(user), 200

    except Error as e:
        current_app.logger.error(f'Database error in get_completed_tasks: {e}')
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()

# Get missed tasks related to a specific user
@users.route("/users/<int:user_id>/tasks/missed", methods=["GET"])
def get_missed_tasks(user_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Reuse the same cursor for the follow-up queries
        cursor.execute("SELECT * FROM Tasks WHERE Assigned_UserID = %s AND status = 'missed'", (user_id,))
        user["missed_tasks"] = cursor.fetchall()

        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify(user), 200

    except Error as e:
        current_app.logger.error(f'Database error in get_missed_tasks: {e}')
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()


# Get todo tasks related to a specific user
@users.route("/users/<int:user_id>/tasks/todo", methods=["GET"])
def get_todo_tasks(user_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Reuse the same cursor for the follow-up queries
        cursor.execute("SELECT * FROM Tasks WHERE Assigned_UserID = %s AND status IN ('todo', 'in_progress')", (user_id,))
        user["todo_tasks"] = cursor.fetchall()

        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify(user), 200

    except Error as e:
        current_app.logger.error(f'Database error in get_todo_tasks: {e}')
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()



# Get roommates associated with a user
@users.route("/users/<int:user_id>/roommates", methods=["GET"])
def get_roommates(user_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT UserID, RoomID FROM Users WHERE UserID = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404

        cursor.execute("SELECT * FROM Users WHERE RoomID = (SELECT RoomID FROM Users WHERE UserID = %s) AND UserID != %s", (user_id, user_id))
        user["roommates"] = cursor.fetchall()

        if not user:
                    return jsonify({"error": "Room or user not found"}), 404

        return jsonify(user), 200

    except Error as e:
        current_app.logger.error(f'Database error in get_roommates: {e}')
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
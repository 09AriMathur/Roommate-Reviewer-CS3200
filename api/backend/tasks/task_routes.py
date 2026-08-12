from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from mysql.connector import Error

# Create a Blueprint for Task routes
tasks = Blueprint("task", __name__)

# Get all tasks
@tasks.route("/tasks", methods=["GET"])
def get_all_tasks():
    cursor = get_db().cursor(dictionary=True)
    try:
        current_app.logger.info('GET /task/tasks')

        query = "SELECT * FROM Tasks WHERE 1=1"
        cursor.execute(query)

        task_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(task_list)} Tasks')
        return jsonify(task_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_all_tasks: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

# Create a new task
@tasks.route("/tasks", methods=["POST"])
def create_new_task():
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()
        
        required_fields = [
            "Task_Name",
            "due_date",
            "Created_UserID",
        ]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
            
        query = """
                    INSERT INTO Tasks (Task_Name, due_date, Created_UserID)
                    VALUES (%s, %s, %s)
                """
        cursor.execute(query, (
            data["Task_Name"],
            data["due_date"],
            data["Created_UserID"],
        ))

        get_db().commit()
        return jsonify({"message": "Task created successfully", "TaskID": cursor.lastrowid}), 201

    # Error handling
    except Error as e:
        return jsonify({"error": str(e)}), 500

    # Final clean up
    finally:
        cursor.close()

# Update an existing task
@tasks.route("/tasks/<task_id>", methods=["PUT"])
def update_task(task_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        cursor.execute("SELECT Task_ID FROM Tasks WHERE Task_ID = %s", (task_id,))
        task = cursor.fetchone()
        if not task:
            return jsonify({"error": "Task not found"}), 404

        VALID_STATUSES = {"todo", "in_progress", "done", "missed"}
        if "Status" in data and data["Status"] not in VALID_STATUSES:
            return jsonify({"error": "Invalid status type"}), 400

        # Build update query dynamically based on provided fields
        allowed_fields = ["due_date", "Status", "Assigned_UserID", "Request_ID"]
        update_fields = [f"{f} = %s" for f in allowed_fields if f in data]
        params = [data[f] for f in allowed_fields if f in data]

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(task_id)
        query = f"UPDATE Tasks SET {', '.join(update_fields)} WHERE Task_ID = %s"
        cursor.execute(query, params)
        get_db().commit()

        return jsonify({"message": "Task updated successfully"}), 200
    except Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

# Delete an existing task
@tasks.route("/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT Task_ID FROM Tasks WHERE Task_ID = %s", (task_id,))
        task = cursor.fetchone()

        if not task:
            return jsonify({"error": "Task not found"}), 404

        cursor.execute("DELETE FROM Tasks WHERE Task_ID = %s", (task_id,))
        get_db().commit()

        return jsonify({"message": "Task deleted successfully"}), 200

    except Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
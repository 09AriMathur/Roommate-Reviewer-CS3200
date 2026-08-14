from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from mysql.connector import Error

# Create a Blueprint for Task routes
tasks = Blueprint("task", __name__)

# A rotation hands out one chore a week. Four weeks is a month of the chart, which is as
# far ahead as a room can sensibly commit and still leave room to swap.
MAX_REPEAT_WEEKS = 4

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

# Get a single task by id
@tasks.route("/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        current_app.logger.info(f'GET /task/tasks/{task_id}')

        cursor.execute("SELECT * FROM Tasks WHERE Task_ID = %s", (task_id,))
        task = cursor.fetchone()

        if not task:
            return jsonify({"error": "Task not found"}), 404

        return jsonify(task), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_task: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

def _room_roster(cursor, user_id):
    """Everyone sharing a room with this user, including them, in a stable order.

    Order is by UserID rather than anything meaningful, because the room has no notion
    of a first or last resident -- what matters is that the rotation walks the same
    circle every time so a resident can predict when their turn comes round.
    """
    cursor.execute(
        """
            SELECT UserID, First_Name, Last_Name FROM Users
            WHERE (DormID, Room_Number) = (
                SELECT DormID, Room_Number FROM Users WHERE UserID = %s
            )
            ORDER BY UserID
        """,
        (user_id,),
    )
    return cursor.fetchall()


def _is_away(cursor, user_id, on_date):
    """Whether this resident has told the app they are gone on that date.

    Same predicate as GET /away/dorms/<d>/rooms/<n>/available, which was written for the
    rotation to use and until now had nothing calling it.
    """
    cursor.execute(
        """
            SELECT 1 FROM UserAway
            WHERE UserID = %s AND %s BETWEEN Start_Date AND End_Date
        """,
        (user_id, on_date),
    )
    return cursor.fetchone() is not None


def _next_assignee(cursor, roster, previous_id, due_on):
    """Whoever's turn it is: the next person round the circle who is not away that day.

    If everyone in the room is away, the turn still has to land on somebody -- an
    unassigned chore shows up on nobody's list and is worse than a badly timed one -- so
    it falls back to the plain next in line.
    """
    ids = [member["UserID"] for member in roster]
    start = ids.index(previous_id) + 1 if previous_id in ids else 0

    for step in range(len(ids)):
        candidate = roster[(start + step) % len(ids)]
        if not _is_away(cursor, candidate["UserID"], due_on):
            return candidate, False

    return roster[start % len(ids)], True


# Create a new chore, optionally as a rotation that repeats weekly around the room.
#
# Assignment used to be a second PUT from the page, which left a window where a failed
# follow-up call stranded a chore with no owner. Passing Assigned_UserID here closes it.
#
# repeat_weeks and rotate are what make the word "rotation" mean something: the chore
# recurs weekly, and each week lands on the next resident in the room who is not away
# that day. Nothing generated the next week before this, so a rotation only existed in
# the seed data and stopped the moment the app was actually used.
@tasks.route("/tasks", methods=["POST"])
def create_new_task():
    db = get_db()
    cursor = db.cursor(dictionary=True)
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

        try:
            first_due = datetime.strptime(str(data["due_date"])[:10], "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "due_date must be YYYY-MM-DD"}), 400

        repeat_weeks = data.get("repeat_weeks", 1)
        if not isinstance(repeat_weeks, int) or not 1 <= repeat_weeks <= MAX_REPEAT_WEEKS:
            return jsonify({
                "error": f"repeat_weeks must be a whole number from 1 to {MAX_REPEAT_WEEKS}"
            }), 400

        rotate = bool(data.get("rotate", False))
        assigned_to = data.get("Assigned_UserID")

        roster = _room_roster(cursor, data["Created_UserID"])
        if rotate and not roster:
            return jsonify({"error": "Cannot rotate a chore: this user has no room"}), 400

        created = []
        # One turn per week. The first turn goes to whoever was named; each turn after
        # that is handed on, so the person creating the chore is not quietly signing
        # themselves up for a month of it.
        previous_id = assigned_to
        for week in range(repeat_weeks):
            due_on = first_due + timedelta(weeks=week)

            if week == 0 and not (rotate and assigned_to is None):
                owner_id = assigned_to
                skipped = False
            elif rotate:
                owner, skipped = _next_assignee(cursor, roster, previous_id, due_on)
                owner_id = owner["UserID"]
            else:
                owner_id = previous_id
                skipped = False

            cursor.execute(
                """
                    INSERT INTO Tasks (Task_Name, due_date, Created_UserID, Assigned_UserID)
                    VALUES (%s, %s, %s, %s)
                """,
                (data["Task_Name"], due_on, data["Created_UserID"], owner_id),
            )
            created.append({
                "TaskID": cursor.lastrowid,
                "due_date": due_on.isoformat(),
                "Assigned_UserID": owner_id,
                # True means the whole room was away that week and the turn landed
                # anyway -- worth saying out loud rather than silently mis-assigning.
                "everyone_away": skipped,
            })
            previous_id = owner_id

        db.commit()
        return jsonify({
            "message": "Task created successfully",
            "TaskID": created[0]["TaskID"],
            "tasks": created,
        }), 201

    # Error handling
    except Error as e:
        db.rollback()
        current_app.logger.error(f'Database error in create_new_task: {e}')
        return jsonify({"error": str(e)}), 500

    # Final clean up
    finally:
        cursor.close()

# Users.TasksCompleted / TasksMissed are denormalized counters, and the completion
# percentage on the resident dashboards is derived entirely from them. Only a finished
# task counts, so 'todo' and 'in_progress' map to nothing.
COUNTER_FOR_STATUS = {"done": "TasksCompleted", "missed": "TasksMissed"}


def _apply_counter_change(cursor, before_status, before_user, after_status, after_user):
    """Keep the two counters in step with a task's status and assignee.

    Both halves matter. Changing status moves a task between counters; changing
    assignee moves a finished task's count from one resident to another. Handling
    them together also covers the case where both change at once.
    """
    old_column = COUNTER_FOR_STATUS.get(before_status)
    new_column = COUNTER_FOR_STATUS.get(after_status)

    if (old_column, before_user) == (new_column, after_user):
        return

    # GREATEST guards against ever driving a counter negative -- the seed values were
    # generated independently of the task rows, so they cannot be assumed accurate.
    if old_column and before_user is not None:
        cursor.execute(
            f"UPDATE Users SET {old_column} = GREATEST({old_column} - 1, 0) "
            "WHERE UserID = %s",
            (before_user,),
        )
    if new_column and after_user is not None:
        cursor.execute(
            f"UPDATE Users SET {new_column} = {new_column} + 1 WHERE UserID = %s",
            (after_user,),
        )


# Update an existing task
@tasks.route("/tasks/<task_id>", methods=["PUT"])
def update_task(task_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        cursor.execute(
            "SELECT Task_ID, status, Assigned_UserID FROM Tasks WHERE Task_ID = %s",
            (task_id,),
        )
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

        # Marking a chore done has to move the resident's completion rate, which is
        # what the counters feed. Done in the same transaction as the task update so
        # the two cannot drift apart.
        _apply_counter_change(
            cursor,
            task["status"],
            task["Assigned_UserID"],
            data.get("Status", task["status"]),
            data["Assigned_UserID"] if "Assigned_UserID" in data
            else task["Assigned_UserID"],
        )

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
        cursor.execute(
            "SELECT Task_ID, status, Assigned_UserID FROM Tasks WHERE Task_ID = %s",
            (task_id,),
        )
        task = cursor.fetchone()

        if not task:
            return jsonify({"error": "Task not found"}), 404

        cursor.execute("DELETE FROM Tasks WHERE Task_ID = %s", (task_id,))

        # Deleting a finished chore has to give back the count it contributed, or the
        # resident keeps credit for a task that no longer exists.
        _apply_counter_change(
            cursor, task["status"], task["Assigned_UserID"], None, None
        )

        get_db().commit()

        return jsonify({"message": "Task deleted successfully"}), 200

    except Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
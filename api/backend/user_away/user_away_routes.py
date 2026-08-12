from datetime import datetime

from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from mysql.connector import Error

# Create a Blueprint for User Away routes
user_away = Blueprint("user_away", __name__)


def _valid_date(value):
    """True if value is a YYYY-MM-DD date string. UserAway carries a
    CHECK (End_Date >= Start_Date) constraint that MySQL enforces, so ranges are
    validated here to return a 400 instead of letting the constraint raise a 500."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


# Get all away periods, optionally filtered by user or by a date they cover
# Example: /away/away?user_id=4&on_date=2026-08-06
@user_away.route("/away", methods=["GET"])
def get_all_away():
    cursor = get_db().cursor(dictionary=True)
    try:
        current_app.logger.info('GET /away/away')

        user_id = request.args.get("user_id")
        on_date = request.args.get("on_date")

        if on_date is not None and not _valid_date(on_date):
            return jsonify({"error": "on_date must be a date in YYYY-MM-DD format"}), 400

        # WHERE 1=1 lets us append AND clauses cleanly without special-casing the first filter
        query = "SELECT * FROM UserAway WHERE 1=1"
        params = []

        if user_id:
            query += " AND UserID = %s"
            params.append(user_id)
        if on_date:
            query += " AND %s BETWEEN Start_Date AND End_Date"
            params.append(on_date)

        query += " ORDER BY Start_Date DESC"

        cursor.execute(query, params)
        away_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(away_list)} Away periods')
        return jsonify(away_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_all_away: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get a single away period
# Example: /away/away/2
@user_away.route("/away/<int:away_id>", methods=["GET"])
def get_away(away_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM UserAway WHERE AwayID = %s", (away_id,))
        away = cursor.fetchone()

        if not away:
            return jsonify({"error": "Away period not found"}), 404

        return jsonify(away), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_away: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get every away period a given user has marked (user story 3.4)
# Example: /away/users/4/away
@user_away.route("/users/<int:user_id>/away", methods=["GET"])
def get_user_away(user_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (user_id,))
        if not cursor.fetchone():
            return jsonify({"error": "User not found"}), 404

        cursor.execute(
            "SELECT * FROM UserAway WHERE UserID = %s ORDER BY Start_Date DESC",
            (user_id,),
        )
        away_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(away_list)} Away periods for user {user_id}')
        return jsonify(away_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_user_away: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Who in a room is actually available on a given date - the roommates NOT away.
# This is the payoff for user story 3.4: the rotation uses it to skip whoever is gone.
# Defaults to today when on_date is omitted.
# Example: /away/rooms/3/available?on_date=2026-08-06
@user_away.route("/rooms/<int:room_id>/available", methods=["GET"])
def get_available_roommates(room_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        on_date = request.args.get("on_date", datetime.now().strftime("%Y-%m-%d"))

        if not _valid_date(on_date):
            return jsonify({"error": "on_date must be a date in YYYY-MM-DD format"}), 400

        cursor.execute("SELECT RoomID FROM Rooms WHERE RoomID = %s", (room_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Room not found"}), 404

        query = """
                    SELECT u.UserID, u.First_Name, u.Last_Name, u.Email,
                           u.TasksCompleted, u.TasksMissed
                    FROM Users u
                    WHERE u.RoomID = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM UserAway a
                          WHERE a.UserID = u.UserID
                            AND %s BETWEEN a.Start_Date AND a.End_Date
                      )
                    ORDER BY u.UserID
                """
        cursor.execute(query, (room_id, on_date))
        available = cursor.fetchall()

        current_app.logger.info(f'{len(available)} roommates available in room {room_id} on {on_date}')
        return jsonify({
            "room_id": room_id,
            "on_date": on_date,
            "available": available,
        }), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_available_roommates: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Mark a date range as away so the rotation skips you (user story 3.4)
@user_away.route("/away", methods=["POST"])
def create_new_away():
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        required_fields = [
            "UserID",
            "Start_Date",
            "End_Date",
        ]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        for field in ("Start_Date", "End_Date"):
            if not _valid_date(data[field]):
                return jsonify({"error": f"{field} must be a date in YYYY-MM-DD format"}), 400

        if data["End_Date"] < data["Start_Date"]:
            return jsonify({"error": "End_Date cannot be earlier than Start_Date"}), 400

        # Confirm the user exists before inserting, so a bad ID gives a clear 404
        # rather than a raw foreign key error
        cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (data["UserID"],))
        if not cursor.fetchone():
            return jsonify({"error": "User not found"}), 404

        query = """
                    INSERT INTO UserAway (UserID, Start_Date, End_Date)
                    VALUES (%s, %s, %s)
                """
        cursor.execute(query, (
            data["UserID"],
            data["Start_Date"],
            data["End_Date"],
        ))

        get_db().commit()
        current_app.logger.info(f'Created Away period {cursor.lastrowid}')
        return jsonify({"message": "Away period created successfully", "AwayID": cursor.lastrowid}), 201

    # Error handling
    except Error as e:
        current_app.logger.error(f'Database error in create_new_away: {e}')
        return jsonify({"error": str(e)}), 500

    # Final clean up
    finally:
        cursor.close()


# Change the dates on an existing away period (user story 3.4)
@user_away.route("/away/<int:away_id>", methods=["PUT"])
def update_away(away_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        cursor.execute("SELECT * FROM UserAway WHERE AwayID = %s", (away_id,))
        away = cursor.fetchone()
        if not away:
            return jsonify({"error": "Away period not found"}), 404

        for field in ("Start_Date", "End_Date"):
            if field in data and not _valid_date(data[field]):
                return jsonify({"error": f"{field} must be a date in YYYY-MM-DD format"}), 400

        # A partial update can still produce an invalid range, so check the dates the
        # row would end up with rather than only the ones supplied
        new_start = data.get("Start_Date", away["Start_Date"].strftime("%Y-%m-%d"))
        new_end = data.get("End_Date", away["End_Date"].strftime("%Y-%m-%d"))
        if new_end < new_start:
            return jsonify({"error": "End_Date cannot be earlier than Start_Date"}), 400

        if "UserID" in data:
            cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (data["UserID"],))
            if not cursor.fetchone():
                return jsonify({"error": "User not found"}), 404

        # Build update query dynamically based on provided fields
        allowed_fields = ["UserID", "Start_Date", "End_Date"]
        update_fields = [f"{f} = %s" for f in allowed_fields if f in data]
        params = [data[f] for f in allowed_fields if f in data]

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(away_id)
        query = f"UPDATE UserAway SET {', '.join(update_fields)} WHERE AwayID = %s"
        cursor.execute(query, params)
        get_db().commit()

        current_app.logger.info(f'Updated Away period {away_id}')
        return jsonify({"message": "Away period updated successfully"}), 200
    except Error as e:
        current_app.logger.error(f'Database error in update_away: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Cancel an away period, putting the user back into the rotation (user story 3.4)
@user_away.route("/away/<int:away_id>", methods=["DELETE"])
def delete_away(away_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT AwayID FROM UserAway WHERE AwayID = %s", (away_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Away period not found"}), 404

        cursor.execute("DELETE FROM UserAway WHERE AwayID = %s", (away_id,))
        get_db().commit()

        current_app.logger.info(f'Deleted Away period {away_id}')
        return jsonify({"message": "Away period deleted successfully"}), 200

    except Error as e:
        current_app.logger.error(f'Database error in delete_away: {e}')
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()

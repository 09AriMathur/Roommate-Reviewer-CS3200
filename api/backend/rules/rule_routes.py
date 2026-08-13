from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from mysql.connector import Error

# Create a Blueprint for Rule routes
rules = Blueprint("rules", __name__)


# Get all rules, with optional filtering by room, RA, or user
# Example: /rule/rules?dorm_id=2&room_number=201
@rules.route("/rules", methods=["GET"])
def get_all_rules():
    cursor = get_db().cursor(dictionary=True)
    try:
        current_app.logger.info('GET /rule/rules')

        dorm_id = request.args.get("dorm_id")
        room_number = request.args.get("room_number")
        ra_id = request.args.get("ra_id")
        user_id = request.args.get("user_id")

        # WHERE 1=1 lets us append AND clauses cleanly without special-casing the first filter
        query = "SELECT * FROM Rules WHERE 1=1"
        params = []

        # A room is identified by its dorm and its number together, so both have to
        # be supplied for the filter to name a single room.
        if dorm_id and room_number:
            query += " AND DormID = %s AND Room_Number = %s"
            params.extend([dorm_id, room_number])
        if ra_id:
            query += " AND RA_ID = %s"
            params.append(ra_id)
        if user_id:
            query += " AND UserID = %s"
            params.append(user_id)

        cursor.execute(query, params)
        rule_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(rule_list)} Rules')
        return jsonify(rule_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_all_rules: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Get a single rule
# Example: /rule/rules/1
@rules.route("/rules/<int:rule_id>", methods=["GET"])
def get_rule(rule_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Rules WHERE RuleID = %s", (rule_id,))
        rule = cursor.fetchone()

        if not rule:
            return jsonify({"error": "Rule not found"}), 404

        return jsonify(rule), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_rule: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Add a new rule
# Required field: Descr
# Optional: DormID + Room_Number, RA_ID, UserID
# Example: POST /rule/rules with JSON body
@rules.route("/rules", methods=["POST"])
def create_rule():
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        if "Descr" not in data or not str(data["Descr"]).strip():
            return jsonify({"error": "Missing required field: Descr"}), 400

        if data.get("DormID") is not None and data.get("Room_Number") is not None:
            cursor.execute(
                "SELECT 1 FROM Rooms WHERE DormID = %s AND Room_Number = %s",
                (data["DormID"], data["Room_Number"]),
            )
            if not cursor.fetchone():
                return jsonify({"error": "Room not found"}), 404

        if data.get("RA_ID") is not None:
            # RAs is keyed by RA_ID; it has no UserID column, so the old query raised
            # error 1054 and turned every RA-scoped rule write into a 500.
            cursor.execute("SELECT RA_ID FROM RAs WHERE RA_ID = %s", (data["RA_ID"],))
            if not cursor.fetchone():
                return jsonify({"error": "RA not found"}), 404

        if data.get("UserID") is not None:
            cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (data["UserID"],))
            if not cursor.fetchone():
                return jsonify({"error": "User not found"}), 404

        query = """
            INSERT INTO Rules (Descr, DormID, Room_Number, RA_ID, UserID)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            data["Descr"].strip(),
            data.get("DormID"),
            data.get("Room_Number"),
            data.get("RA_ID"),
            data.get("UserID"),
        ))

        get_db().commit()
        current_app.logger.info(f'Created Rule {cursor.lastrowid}')
        return jsonify({"message": "Rule created successfully", "RuleID": cursor.lastrowid}), 201
    except Error as e:
        current_app.logger.error(f'Database error in create_rule: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Update an existing rule
# Can update Descr, DormID + Room_Number, RA_ID, and/or UserID
# Example: PUT /rule/rules/1 with JSON body containing fields to update
@rules.route("/rules/<int:rule_id>", methods=["PUT"])
def update_rule(rule_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        cursor.execute("SELECT RuleID FROM Rules WHERE RuleID = %s", (rule_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Rule not found"}), 404

        if "Descr" in data and not str(data["Descr"]).strip():
            return jsonify({"error": "Descr cannot be empty"}), 400

        if data.get("DormID") is not None and data.get("Room_Number") is not None:
            cursor.execute(
                "SELECT 1 FROM Rooms WHERE DormID = %s AND Room_Number = %s",
                (data["DormID"], data["Room_Number"]),
            )
            if not cursor.fetchone():
                return jsonify({"error": "Room not found"}), 404

        if data.get("RA_ID") is not None:
            # RAs is keyed by RA_ID; it has no UserID column, so the old query raised
            # error 1054 and turned every RA-scoped rule write into a 500.
            cursor.execute("SELECT RA_ID FROM RAs WHERE RA_ID = %s", (data["RA_ID"],))
            if not cursor.fetchone():
                return jsonify({"error": "RA not found"}), 404

        if data.get("UserID") is not None:
            cursor.execute("SELECT UserID FROM Users WHERE UserID = %s", (data["UserID"],))
            if not cursor.fetchone():
                return jsonify({"error": "User not found"}), 404

        # Build update query dynamically based on provided fields
        allowed_fields = ["Descr", "DormID", "Room_Number", "RA_ID", "UserID"]
        update_fields = [f"{f} = %s" for f in allowed_fields if f in data]
        params = [data[f] for f in allowed_fields if f in data]

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(rule_id)
        query = f"UPDATE Rules SET {', '.join(update_fields)} WHERE RuleID = %s"
        cursor.execute(query, params)
        get_db().commit()

        current_app.logger.info(f'Updated Rule {rule_id}')
        return jsonify({"message": "Rule updated successfully"}), 200
    except Error as e:
        current_app.logger.error(f'Database error in update_rule: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()


# Delete a rule
# Example: DELETE /rule/rules/1
@rules.route("/rules/<int:rule_id>", methods=["DELETE"])
def delete_rule(rule_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT RuleID FROM Rules WHERE RuleID = %s", (rule_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Rule not found"}), 404

        cursor.execute("DELETE FROM Rules WHERE RuleID = %s", (rule_id,))
        get_db().commit()

        current_app.logger.info(f'Deleted Rule {rule_id}')
        return jsonify({"message": "Rule deleted successfully"}), 200
    except Error as e:
        current_app.logger.error(f'Database error in delete_rule: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

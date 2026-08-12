from flask import Blueprint, jsonify, request, current_app
from backend.db_connection import get_db
from mysql.connector import Error

# Create a Blueprint for Room Report routes
room_reports = Blueprint("room_report", __name__)

# Get all room reports
@room_reports.route("/room_reports", methods=["GET"])
def get_all_room_reports():
    cursor = get_db().cursor(dictionary=True)
    try:
        query = "SELECT * FROM Room_Reports WHERE 1=1"
        cursor.execute(query)

        report_list = cursor.fetchall()

        current_app.logger.info(f'Retrieved {len(report_list)} Room Reports')
        return jsonify(report_list), 200
    except Error as e:
        current_app.logger.error(f'Database error in get_all_room_reports: {e}')
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

# Create a new room report
@room_reports.route("/room_reports", methods=["POST"])
def create_new_room_report():
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()
        
        required_fields = [
            "TaskID",
            "UserID",
        ]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
            
        query = """
                    INSERT INTO Room_Reports (TaskID, UserID)
                    VALUES (%s, %s)
                """
        cursor.execute(query, (
            data["TaskID"],
            data["UserID"],
        ))

        get_db().commit()
        return jsonify({"message": "Room Report created successfully", "ReportID": cursor.lastrowid}), 201

    # Error handling
    except Error as e:
        return jsonify({"error": str(e)}), 500

    # Final clean up
    finally:
        cursor.close()


# Update an existing room report
@room_reports.route("/room_reports/<report_id>", methods=["PUT"])
def update_room_report(report_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        data = request.get_json()

        cursor.execute("SELECT ReportID FROM Room_Reports WHERE ReportID = %s", (report_id,))
        report = cursor.fetchone()
        if not report:
            return jsonify({"error": "Room Report not found"}), 404

        VALID_STATUSES = {"open", "reviewed", "closed"}
        if "Status" in data and data["Status"] not in VALID_STATUSES:
            return jsonify({"error": "Invalid status type"}), 400

        # Build update query dynamically based on provided fields
        allowed_fields = ["Status", "RequestID"]
        update_fields = [f"{f} = %s" for f in allowed_fields if f in data]
        params = [data[f] for f in allowed_fields if f in data]

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(report_id)
        query = f"UPDATE Room_Reports SET {', '.join(update_fields)} WHERE ReportID = %s"
        cursor.execute(query, params)
        get_db().commit()

        return jsonify({"message": "Room Report updated successfully"}), 200
    except Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()

# Delete an existing room report
@room_reports.route("/room_reports/<report_id>", methods=["DELETE"])
def delete_room_report(report_id):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute("SELECT ReportID FROM Room_Reports WHERE ReportID = %s", (report_id,))
        report = cursor.fetchone()

        if not report:
            return jsonify({"error": "Room Report not found"}), 404

        cursor.execute("DELETE FROM Room_Reports WHERE ReportID = %s", (report_id,))
        get_db().commit()

        return jsonify({"message": "Room Report deleted successfully"}), 200

    except Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
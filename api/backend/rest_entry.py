from flask import Flask
from dotenv import load_dotenv
import os
import logging

from backend.db_connection import init_app as init_db
from backend.simple.simple_routes import simple_routes
from backend.rooms.room_routes import rooms
from backend.RA.ra_routes import ras
from backend.users.user_routes import users
from backend.tasks.task_routes import tasks
from backend.room_reports.room_report_routes import room_reports
from backend.requests.request_routes import requests
from backend.user_away.user_away_routes import user_away
from backend.dorms.dorm_routes import dorms
from backend.rules.rule_routes import rules


def create_app():
    app = Flask(__name__)

    app.logger.setLevel(logging.DEBUG)
    app.logger.info('API startup')

    # Load environment variables from the .env file so they are
    # accessible via os.getenv() below.
    load_dotenv()

    # Secret key used by Flask for securely signing session cookies.
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

    # Database connection settings — values come from the .env file.
    app.config["MYSQL_DATABASE_USER"] = os.getenv("DB_USER").strip()
    app.config["MYSQL_DATABASE_PASSWORD"] = os.getenv("MYSQL_ROOT_PASSWORD").strip()
    app.config["MYSQL_DATABASE_HOST"] = os.getenv("DB_HOST").strip()
    app.config["MYSQL_DATABASE_PORT"] = int(os.getenv("DB_PORT").strip())
    app.config["MYSQL_DATABASE_DB"] = os.getenv("DB_NAME").strip()

    # Register the cleanup hook for the database connection.
    app.logger.info("create_app(): initializing database connection")
    init_db(app)

    # Register the routes from each Blueprint with the app object
    # and give a url prefix to each.
    app.logger.info("create_app(): registering blueprints")
    app.register_blueprint(simple_routes)
    app.register_blueprint(rooms, url_prefix="/room")
    app.register_blueprint(ras, url_prefix="/ra")
    app.register_blueprint(users, url_prefix="/user")
    app.register_blueprint(tasks, url_prefix="/task")
    app.register_blueprint(room_reports, url_prefix="/room_report")
    app.register_blueprint(requests, url_prefix="/request")
    app.register_blueprint(user_away, url_prefix="/away")
    app.register_blueprint(dorms, url_prefix="/dorm")
    app.register_blueprint(rules, url_prefix="/rule")

    return app

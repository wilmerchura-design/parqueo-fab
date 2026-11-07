import logging

from flask import Flask
from flask_appbuilder import AppBuilder
from flask_sqlalchemy import SQLAlchemy

logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
logging.getLogger().setLevel(logging.INFO)

app = Flask(__name__)
app.config.from_object("config")
db = SQLAlchemy(app)
appbuilder = AppBuilder()

with app.app_context():
    appbuilder.init_app(app, db.session)
    from app import views  # noqa: E402,F401

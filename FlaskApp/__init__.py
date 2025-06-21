from flask import Flask
from FlaskApp.Blueprints.users import bp_users
from FlaskApp.Blueprints.main import bp_main
from FlaskApp.Blueprints.api import bp_api
from FlaskApp.database import db
from FlaskApp.core import app

app.register_blueprint(bp_users)
app.register_blueprint(bp_main)
app.register_blueprint(bp_api)

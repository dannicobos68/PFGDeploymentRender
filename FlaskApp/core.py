from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import os, re, uuid
from flask_login import LoginManager
from dotenv import load_dotenv
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))



load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL_LOCAL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
"""app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {'ssl': {'ca': 'FlaskApp/ca.pem'}}, 
}
"""
loginMgr = LoginManager(app)


@app.errorhandler(404)
def not_found_error(error):
    return render_template('error/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error/500.html'), 500

# Error 401
@app.errorhandler(401)
def unauthorized(error):
    return render_template('error/401.html'), 401


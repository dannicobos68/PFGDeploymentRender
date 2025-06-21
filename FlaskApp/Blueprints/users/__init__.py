from flask import Blueprint

bp_users = Blueprint('bp_users', __name__, template_folder='templates')
from .routes import *

bp_users.add_url_rule('/', view_func=login, methods=['GET', 'POST'])
bp_users.add_url_rule('/register', view_func=register, methods=['GET', 'POST'])
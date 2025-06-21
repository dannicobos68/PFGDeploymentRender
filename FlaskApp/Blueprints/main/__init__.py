from flask import Flask, request, Blueprint
from urllib.parse import quote, unquote

bp_main = Blueprint('bp_main', __name__, template_folder='templates')
from .routes import *



bp_main.add_url_rule('/index', view_func=index, methods=['GET', 'POST'])
bp_main.add_url_rule('/historial', view_func=historial, methods=['GET', 'POST'])
bp_main.add_url_rule('/chatVideo/<int:video_id>', view_func=chatVideo, methods=['GET', 'POST'])
bp_main.add_url_rule('/logout', view_func=logout, methods=['GET', 'POST'])
bp_main.add_url_rule('/rating', view_func=rating, methods=['POST'])
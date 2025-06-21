from flask import Flask, request, Blueprint
from urllib.parse import quote, unquote


bp_api = Blueprint('bp_api', __name__, template_folder='templates')
from .routes import *

# Definir la función de vista
    
bp_api.add_url_rule('/cargar_video_youtube', view_func=cargar_video_youtube, methods=['GET', 'POST'])
bp_api.add_url_rule('/realizar_pregunta', view_func=realizar_pregunta, methods=['GET', 'POST'])

import os
from datetime import datetime
from flask import Flask, g
from werkzeug.security import generate_password_hash, check_password_hash
from FlaskApp.core import app, loginMgr
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import pymysql
pymysql.install_as_MySQLdb()
import jwt
from time import time
import secrets, string
import ast, pickle, json
from dotenv import load_dotenv

# Cargo variables de entorno
load_dotenv()

# Ruta relativa y absoluta del certificado SSL
ca_cert_relative = os.getenv('DB_CA_CERT')
ca_cert_path = os.getenv('DB_CA_CERT')

# Variables de conexión
user = os.getenv('MYSQL_USER')
password = os.getenv('MYSQL_PASSWORD')
host = os.getenv('MYSQL_HOST')
port = os.getenv('MYSQL_PORT', '12183')  # Si no está definido, usa 12183 por defecto
db_name = os.getenv('MYSQL_DATABASE')

# Construcción de la URI para SQLAlchemy
uri = (
    f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db_name}"
    f"?ssl_ca={ca_cert_path.replace(os.sep, '/')}"
)

# Configuración de Flask SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy()
db.init_app(app)
migrate = Migrate(app, db)

@loginMgr.user_loader
def load_user(id):
    return User.query.get(int(id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
class Videos(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(1000), nullable=False)
    rating = db.Column(db.Integer, nullable=True)
    idUsuario = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    def __repr__(self):
        return f'<Videos {self.titulo}>'
    
class InfoVideo(UserMixin, db.Model):
    __tablename__ = 'infoVideo'
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.Text, nullable=False)
    idVideo = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    idUsuario = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
     
    def __repr__(self):
        return f'<InfoVideo {self.id}>'
    
class Llamada(UserMixin, db.Model):
    __tablename__ = 'llamada'
    id = db.Column(db.Integer, primary_key=True)
    pregunta = db.Column(db.String(10000), nullable=False)
    respuesta = db.Column(db.Text, nullable=False)
    fecha = db.Column(db.DateTime, nullable=False)
    idUsuario = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    idVideo = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    
    def __repr__(self):
        return f'<Llamada {self.id}>'



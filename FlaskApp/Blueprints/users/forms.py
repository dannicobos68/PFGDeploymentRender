from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, BooleanField, DateField, SelectField, IntegerField, SelectMultipleField, TextAreaField, FileField, RadioField
from wtforms.validators import DataRequired, InputRequired, Email, Length, EqualTo
from datetime import datetime

class LoginForm(FlaskForm):
    username = StringField('Escribe el email', render_kw={"class":"form-control form-control-lg", "type":"text", "placeholder":"Correo o nombre de usuario"})  
    password = PasswordField('Contraseña',  render_kw={"class":"form-control form-control-lg", "type":"password", "placeholder":"Contraseña"})
    submit = SubmitField('Iniciar sesión')
    
class RegisterForm(FlaskForm):
    username = StringField('Nombre de usuario', render_kw={"class":"form-control form-control-lg", "type":"text", "placeholder":"Nombre de usuario"})
    email = StringField('Email', render_kw={"class":"form-control form-control-lg", "type":"text", "placeholder":"Correo"})
    password = PasswordField('Contraseña',  render_kw={"class":"form-control form-control-lg", "type":"password", "placeholder":"Contraseña"})
    confirm_password = PasswordField('Confirmar contraseña', render_kw={"class":"form-control form-control-lg", "type":"password", "placeholder":"Confirmar contraseña"})
    submit = SubmitField('Registrarse')
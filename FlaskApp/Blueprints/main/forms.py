from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, BooleanField, DateField, SelectField, IntegerField, SelectMultipleField, TextAreaField, FileField, RadioField
from wtforms.validators import DataRequired, InputRequired, Email, Length, EqualTo
from datetime import datetime


class videoYoutube(FlaskForm):
    url = StringField('URL del video', render_kw={"class":"form-control form-control-lg", "type":"text", "placeholder":"URL del video"})  
    submit = SubmitField('Convertir video')
    

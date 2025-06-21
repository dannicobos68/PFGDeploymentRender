from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_user, current_user, logout_user
from sqlalchemy import or_
import datetime
from FlaskApp.database import User, db, InfoVideo, Videos, Llamada
from flask_login import login_required
from datetime import timedelta
from .forms import videoYoutube

@login_required
def index():
    # Obtener los videos de youtube del usuario logeado
    return render_template('index.html', id_user=current_user.id)

@login_required
def historial():
    videos = Videos.query.filter_by(idUsuario=current_user.id).all()
    print(videos)
    for video in videos:
        print(video.titulo)
    return render_template('historial.html', videos=videos)

@login_required
def rating():
    # Obtener los datos del formulario de valoración enviado por el usuario
    video_id = int(request.form['video_id'])
    rating = int(request.form['rating'])
    print("ID VIDEO: ", video_id)
    print("RATING: ", rating)
    # Actualizar la valoración del video en la base de datos
    video = Videos.query.filter_by(id=video_id).first()
    video.rating = rating
    db.session.commit()
    
    # Devolver una respuesta al cliente (puedes modificar esto según tus necesidades)
    return redirect(url_for('bp_main.historial'))


@login_required
def chatVideo(video_id):
    print("ID VIDEO: ", video_id)
    # Obtener el video
    video = Videos.query.filter_by(id=video_id).first()
    url = video.url
    print("VIDEO: ", video)
    # Cargar el historial de preguntas
    preguntas = cargar_historial_preguntas(current_user.id, video_id)
    return render_template('chatVideo.html', idVideo=video_id, url=url, historial=preguntas)

def cargar_historial_preguntas(id_usuario, id_video):
    """
    Función que carga el historial de preguntas de un video
    """
    preguntas = Llamada.query.filter_by(idUsuario=id_usuario, idVideo=id_video).all()
    # ordenar las preguntas por fecha
    preguntas = sorted(preguntas, key=lambda x: x.fecha)
    return preguntas

@login_required
def logout():
    logout_user()
    return redirect(url_for('bp_users.login'))
import os
import re
import json
import time
import yt_dlp
import tempfile
import subprocess
import numpy as np
from flask import request
from flask_login import current_user, login_required
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
from FlaskApp.core import client
from FlaskApp.database import db, InfoVideo, Videos, Llamada

# --------------------
# Funciones auxiliares
# --------------------

def get_video_title(url):
    ydl_opts = {"quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("title", "Título no encontrado")

def get_text_embedding(text):
    embedding = client.embeddings.create(
        input=text, model="text-embedding-3-small"
    ).data[0].embedding
    return embedding

def split_text(content, chunk_size):
    chunks = []
    start = 0
    while start < len(content):
        end = start + chunk_size
        if end < len(content):
            while end < len(content) and content[end] != ".":
                end += 1
        chunks.append(content[start:end+1])
        start = end + 1
    return chunks

def calculate_cosine_similarity(vector1, vector2):
    return cosine_similarity([vector1], [vector2])[0][0]

# --------------------
# Obtener transcripción con subtítulos o Whisper
# --------------------
def obtener_transcripcion_youtube(url, idiomas=['es','en']):
    # Intentar obtener el video_id
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if not match:
        return None
    video_id = match.group(1)

    # Primero intentamos subtítulos (YouTubeTranscriptApi)
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=idiomas)
        texto = " ".join([t['text'] for t in transcript_list])
        print("Subtítulos oficiales encontrados.")
        return texto
    except Exception:
        print("No hay subtítulos oficiales, usando Whisper...")

    # Descargar audio con yt-dlp y convertir a mp3
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.mp3")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": audio_path,
            "quiet": True,
            "extractor_args": {"youtube": {"player_client": "default"}}
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print("Error al descargar audio:", e)
            return None

        # Convertir a mp3 si es necesario
        if not audio_path.endswith(".mp3"):
            audio_mp3 = audio_path.replace(".webm", ".mp3")
            subprocess.run(["ffmpeg", "-i", audio_path, audio_mp3], check=True)
            audio_path = audio_mp3

        # Transcribir con Whisper
        try:
            from openai import OpenAI
            client_openai = OpenAI()  # Si usas otro cliente, reemplazar
            with open(audio_path, "rb") as f:
                transcription = client_openai.audio.transcriptions.create(
                    file=f,
                    model="whisper-1"
                )
            return transcription.text
        except Exception as e:
            print("Error al transcribir audio con Whisper:", e)
            return None

# --------------------
# Función para cargar un video
# --------------------
@login_required
def cargar_video_youtube():
    datos = request.get_json()
    url = datos['url']
    id_user = current_user.id

    print("URL:", url)
    print("id_user", id_user)

    # Verificar si ya se cargó el video
    videos = Videos.query.filter_by(idUsuario=id_user).all()
    for video in videos:
        if video.url == url:
            return {"error": "El video ya ha sido cargado"}

    print("Cargando transcripción...")
    texto_completo = obtener_transcripcion_youtube(url)
    if not texto_completo:
        return {"error": "No se pudo obtener la transcripción del video"}

    titulo = get_video_title(url)
    print("Título del video:", titulo)

    # Guardar video en la base de datos
    video = Videos(titulo=titulo, url=url, idUsuario=id_user)
    db.session.add(video)
    db.session.flush()
    id_video = video.id
    print("ID del video:", id_video)

    # Dividir texto y generar embeddings
    datafrme = cargar_texto(500, texto_completo, id_user, id_video)
    print("Embeddings generados:", datafrme)

    return {"idVideo": id_video}

# --------------------
# Guardar texto y embeddings en la DB
# --------------------
def cargar_texto(chunk_size, contenido_video, id_user, idVideo):
    textos = split_text(contenido_video, chunk_size)
    print("Generando embeddings...")
    for i, texto in enumerate(textos):
        embedding = get_text_embedding(texto)
        embedding_str = json.dumps(embedding)
        info_linea = InfoVideo(
            texto=texto,
            embedding=embedding_str,
            idUsuario=id_user,
            idVideo=idVideo
        )
        db.session.add(info_linea)
    db.session.commit()
    time.sleep(1)
    return "Embeddings generados"

# --------------------
# Funciones para el chat
# --------------------
def obtener_id_transaccion(idVideo):
    return InfoVideo.query.with_entities(InfoVideo.id).filter(InfoVideo.idVideo == idVideo).first()[0]

def obtener_fila(idVideo, id_transaccion):
    return InfoVideo.query.filter(InfoVideo.idVideo == idVideo, InfoVideo.id == id_transaccion).first()

def generar_respuesta(pregunta, texto):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Eres un chatbot que responde preguntas sobre videos basándose en el texto proporcionado."},
            {"role": "user", "content": f'Pregunta: "{pregunta}"\nContexto: "{texto}"'}
        ]
    )
    return response.choices[0].message.content

def buscar(pregunta, embeddings, idVideo):
    pregunta_embedding = get_text_embedding(pregunta)
    similitud = [calculate_cosine_similarity(e, pregunta_embedding) for e in embeddings]
    indices = np.argsort(similitud)[::-1]
    primer_id = obtener_id_transaccion(idVideo)
    fila = obtener_fila(idVideo, primer_id + int(indices[0]))
    respuesta = generar_respuesta(pregunta, fila.texto)
    return respuesta

@login_required
def realizar_pregunta():
    datos = request.get_json()
    pregunta = datos['pregunta']
    idVideo = datos['idVideo']
    id_usuario = current_user.id

    videos_json = InfoVideo.query.with_entities(InfoVideo.embedding).filter(
        InfoVideo.idUsuario == id_usuario,
        InfoVideo.idVideo == idVideo
    ).all()

    embeddings = [json.loads(v.embedding) for v in videos_json]

    respuesta = buscar(pregunta, embeddings, idVideo)

    # Guardar la pregunta y respuesta
    llamada = Llamada(
        idUsuario=id_usuario,
        idVideo=idVideo,
        pregunta=pregunta,
        respuesta=respuesta,
        fecha=datetime.now()
    )
    db.session.add(llamada)
    db.session.commit()

    return {"respuesta": respuesta}

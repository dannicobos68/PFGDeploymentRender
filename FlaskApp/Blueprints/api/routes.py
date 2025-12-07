import os
import re
import json
import time
import requests
import io
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
    video_id = extraer_video_id(url)
    if not video_id:
        return "Título no encontrado"
    api_url = f"https://piped.kavin.rocks/api/v1/videos/{video_id}"
    r = requests.get(api_url)
    if r.status_code != 200:
        return "Título no encontrado"
    data = r.json()
    return data.get("title", "Título no encontrado")

def extraer_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if not match:
        return None
    return match.group(1)

def get_text_embedding(text):
    embedding = client.embeddings.create(
        input=text, model="text-embedding-3-small"
    ).data[0].embedding
    return embedding

def split_text(content, chunk_size=500):
    sentences = re.split(r'(?<=[.?!])\s+', content)
    chunks, current = [], ""
    for s in sentences:
        if len(current) + len(s) <= chunk_size:
            current += s + " "
        else:
            chunks.append(current.strip())
            current = s + " "
    if current:
        chunks.append(current.strip())
    return chunks

def calculate_cosine_similarity(vector1, vector2):
    return cosine_similarity([vector1], [vector2])[0][0]

# --------------------
# Obtener transcripción con Piped API + Whisper (streaming)
# --------------------
def obtener_transcripcion_youtube(url, idiomas=['es','en']):
    video_id = extraer_video_id(url)
    if not video_id:
        return None

    # Intentar subtítulos oficiales
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=idiomas)
        texto = " ".join([t['text'] for t in transcript_list])
        print("Subtítulos oficiales encontrados.")
        return texto
    except Exception:
        print("No hay subtítulos oficiales, usando Piped API + Whisper...")

    # Obtener audio stream desde Piped API
    try:
        api_url = f"https://piped.kavin.rocks/api/v1/streams/{video_id}"
        r = requests.get(api_url)
        if r.status_code != 200:
            print("Error al obtener streams de Piped API")
            return None
        data = r.json()

        # Tomar primer stream de audio disponible
        audio_url = None
        for stream in data.get('adaptiveStreams', []):
            if stream.get('type') == 'audio':
                audio_url = stream['url']
                break
        if not audio_url:
            print("No se encontró stream de audio")
            return None

        # Descargar audio a memoria
        audio_response = requests.get(audio_url, stream=True)
        audio_bytes = io.BytesIO()
        for chunk in audio_response.iter_content(chunk_size=1024*1024):
            if chunk:
                audio_bytes.write(chunk)
        audio_bytes.seek(0)

        # Transcribir directamente desde memoria con Whisper
        from openai import OpenAI
        client_openai = OpenAI()
        transcription = client_openai.audio.transcriptions.create(
            file=audio_bytes,
            model="whisper-1"
        )
        return transcription.text

    except Exception as e:
        print("Error al transcribir audio con Piped API + Whisper:", e)
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
    cargar_texto(500, texto_completo, id_user, id_video)
    print("Embeddings generados.")

    return {"idVideo": id_video}

# --------------------
# Guardar texto y embeddings en la DB
# --------------------
def cargar_texto(chunk_size, contenido_video, id_user, idVideo):
    textos = split_text(contenido_video, chunk_size)
    print("Generando embeddings...")
    for texto in textos:
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


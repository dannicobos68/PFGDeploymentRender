import os
import re
import json
import time
import tempfile
import numpy as np
import requests
from flask import request
from flask_login import current_user, login_required
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
from FlaskApp.core import client
from FlaskApp.database import db, InfoVideo, Videos, Llamada
from openai import OpenAI
import yt_dlp
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# --------------------
# Funciones auxiliares
# --------------------
def extraer_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None

def get_video_title(url):
    try:
        ydl_opts = {'quiet': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('title', 'Título no encontrado')
    except Exception:
        return "Título no encontrado"

def get_text_embedding(text):
    return client.embeddings.create(input=text, model="text-embedding-3-small").data[0].embedding

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
# Sesión de requests con reintentos
# --------------------
def requests_session(retries=3, backoff_factor=0.3):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(500, 502, 504)
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# --------------------
# Obtener transcripción
# --------------------
def obtener_transcripcion_youtube(url, idiomas=['es','en']):
    video_id = extraer_video_id(url)
    if not video_id:
        return None

    # 1️⃣ Intentar subtítulos oficiales
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=idiomas)
        texto = " ".join([t['text'] for t in transcript_list])
        print("Subtítulos oficiales encontrados.")
        return texto
    except Exception:
        print("No hay subtítulos oficiales, usando audio con yt-dlp + Whisper...")

    # 2️⃣ Obtener URL de audio con yt-dlp
    try:
        ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info.get('url')
        if not audio_url:
            print("No se pudo obtener el audio del video")
            return None

        # Descargar audio en streaming con requests y reintentos
        session = requests_session()
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as tmp_audio:
            with session.get(audio_url, stream=True, timeout=30) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk:
                        tmp_audio.write(chunk)
                tmp_audio.flush()
                tmp_audio.seek(0)

                # Transcribir audio con Whisper
                client_openai = OpenAI()
                transcription = client_openai.audio.transcriptions.create(
                    file=open(tmp_audio.name, "rb"),
                    model="whisper-1"
                )
        return transcription.text

    except Exception as e:
        print(f"Error al transcribir audio: {e}")
        return None

# --------------------
# Cargar video y generar embeddings
# --------------------
@login_required
def cargar_video_youtube():
    datos = request.get_json()
    url = datos['url']
    id_user = current_user.id

    print(f"Procesando video: {url} para usuario {id_user}")

    # Verificar si ya se cargó
    if Videos.query.filter_by(idUsuario=id_user, url=url).first():
        return {"error": "El video ya ha sido cargado"}

    # Obtener transcripción
    texto_completo = obtener_transcripcion_youtube(url)
    if not texto_completo:
        return {"error": "No se pudo obtener la transcripción del video"}

    # Obtener título
    titulo = get_video_title(url)
    print(f"Título del video: {titulo}")

    # Guardar en DB
    video = Videos(titulo=titulo, url=url, idUsuario=id_user)
    db.session.add(video)
    db.session.flush()
    id_video = video.id

    # Dividir texto y generar embeddings
    cargar_texto(500, texto_completo, id_user, id_video)
    print("Embeddings generados.")

    return {"idVideo": id_video}

def cargar_texto(chunk_size, contenido_video, id_user, idVideo):
    textos = split_text(contenido_video, chunk_size)
    print("Generando embeddings...")
    for texto in textos:
        try:
            embedding = get_text_embedding(texto)
            info_linea = InfoVideo(
                texto=texto,
                embedding=json.dumps(embedding),
                idUsuario=id_user,
                idVideo=idVideo
            )
            db.session.add(info_linea)
        except Exception as e:
            print(f"Error generando embedding para un chunk: {e}")
    db.session.commit()
    return "Embeddings generados"

# --------------------
# Funciones de chat
# --------------------
def obtener_id_transaccion(idVideo):
    return InfoVideo.query.with_entities(InfoVideo.id).filter(InfoVideo.idVideo == idVideo).first()[0]

def obtener_fila(idVideo, id_transaccion):
    return InfoVideo.query.filter(InfoVideo.idVideo == idVideo, InfoVideo.id == id_transaccion).first()

def generar_respuesta(pregunta, texto):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un chatbot que responde preguntas sobre videos basándose en el texto proporcionado."},
                {"role": "user", "content": f'Pregunta: "{pregunta}"\nContexto: "{texto}"'}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generando respuesta GPT: {e}")
        return "No se pudo generar la respuesta"

def buscar(pregunta, embeddings, idVideo):
    pregunta_embedding = get_text_embedding(pregunta)
    similitud = [calculate_cosine_similarity(e, pregunta_embedding) for e in embeddings]
    indices = np.argsort(similitud)[::-1]
    primer_id = obtener_id_transaccion(idVideo)
    fila = obtener_fila(idVideo, primer_id + int(indices[0]))
    return generar_respuesta(pregunta, fila.texto)

@login_required
def realizar_pregunta():
    datos = request.get_json()
    pregunta = datos['pregunta']
    idVideo = datos['idVideo']
    id_usuario = current_user.id

    embeddings = [json.loads(v.embedding) for v in InfoVideo.query.with_entities(InfoVideo.embedding).filter(
        InfoVideo.idUsuario == id_usuario,
        InfoVideo.idVideo == idVideo
    ).all()]

    respuesta = buscar(pregunta, embeddings, idVideo)

    # Guardar pregunta y respuesta
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


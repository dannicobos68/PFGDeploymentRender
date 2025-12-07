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

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3"

# --------------------
# Funciones auxiliares
# --------------------
def extraer_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None

def get_video_title(video_id):
    try:
        r = requests.get(
            f"{YOUTUBE_API_URL}/videos",
            params={"id": video_id, "part": "snippet", "key": YOUTUBE_API_KEY},
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        if "items" in data and len(data["items"]) > 0:
            return data["items"][0]["snippet"]["title"]
        return "Título no encontrado"
    except Exception as e:
        print(f"Error al obtener título: {e}")
        return "Título no encontrado"

def get_video_subtitles(video_id, idiomas=['es','en']):
    """
    Intenta obtener subtítulos vía API o servicios públicos. 
    Si no hay, retorna None.
    """
    # YouTube Data API no entrega directamente subtítulos, pero podemos usar 
    # `youtube_transcript_api` que funciona con la API key.
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=idiomas)
        texto = " ".join([t['text'] for t in transcript_list])
        return texto
    except Exception:
        return None

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
# Transcripción fallback con Whisper
# --------------------
def transcribir_audio_con_whisper(video_url):
    try:
        import yt_dlp
        ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = info.get("url")
        if not audio_url:
            return None

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as tmp_audio:
            r = requests.get(audio_url, stream=True, timeout=60)
            r.raise_for_status()
            for chunk in r.iter_content(1024*1024):
                tmp_audio.write(chunk)
            tmp_audio.flush()
            tmp_audio.seek(0)

            client_openai = OpenAI()
            transcription = client_openai.audio.transcriptions.create(
                file=open(tmp_audio.name, "rb"),
                model="whisper-1"
            )
        return transcription.text
    except Exception as e:
        print(f"Error transcribiendo audio: {e}")
        return None

# --------------------
# Cargar video y generar embeddings
# --------------------
@login_required
def cargar_video_youtube():
    datos = request.get_json()
    url = datos['url']
    id_user = current_user.id

    video_id = extraer_video_id(url)
    if not video_id:
        return {"error": "ID de video no válido"}

    # Verificar si ya existe
    if Videos.query.filter_by(idUsuario=id_user, url=url).first():
        return {"error": "El video ya ha sido cargado"}

    # Obtener subtítulos o transcripción
    texto_completo = get_video_subtitles(video_id)
    if not texto_completo:
        print("No hay subtítulos, usando Whisper")
        texto_completo = transcribir_audio_con_whisper(url)
        if not texto_completo:
            return {"error": "No se pudo obtener la transcripción"}

    # Obtener título vía API
    titulo = get_video_title(video_id)

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
            print(f"Error generando embedding: {e}")
    db.session.commit()
    return "Embeddings generados"

# --------------------
# Chat sobre video
# --------------------
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
        print(f"Error generando respuesta: {e}")
        return "No se pudo generar la respuesta"

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

    # Buscar similitud y responder
    pregunta_embedding = get_text_embedding(pregunta)
    similitud = [calculate_cosine_similarity(e, pregunta_embedding) for e in embeddings]
    indices = np.argsort(similitud)[::-1]
    primer_id = InfoVideo.query.with_entities(InfoVideo.id).filter(InfoVideo.idVideo == idVideo).first()[0]
    fila = InfoVideo.query.filter(InfoVideo.idVideo == idVideo, InfoVideo.id == primer_id + int(indices[0])).first()
    respuesta = generar_respuesta(pregunta, fila.texto)

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


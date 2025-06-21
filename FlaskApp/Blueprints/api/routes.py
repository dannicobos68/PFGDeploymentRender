import yt_dlp
from langchain.document_loaders import UnstructuredVTTLoader
from langchain_community.llms import OpenAI
from langchain.chains.summarize import load_summarize_chain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import time
from FlaskApp.core import client
from flask import request
from FlaskApp.database import db, InfoVideo, Videos, Llamada
from flask_login import current_user, login_required
import numpy as np
import ast
from sklearn.metrics.pairwise import cosine_similarity
import openai
import json
from datetime import datetime
import os
import requests
from langchain_core.documents import Document


def get_video_title(url):
    cookies_path = "/etc/secrets/cookies1"
    ydl_opts = {
        'quiet': True,
        'cookiefile': cookies_path,
        'noplaylist': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("title", "Título no encontrado")
    except Exception as e:
        print(f"[ERROR] No se pudo obtener el título del video: {e}")
        return "No se pudo obtener el título del video"


def get_text_embedding(text):
    embedding = client.embeddings.create(input=text, model="text-embedding-3-small").data[0].embedding
    return embedding


@login_required
def cargar_video_youtube():
    datos = request.get_json()
    url = datos['url']
    id_user = current_user.id

    videos = Videos.query.filter_by(idUsuario=id_user).all()
    for video in videos:
        if video.url == url:
            return {"error": "El video ya ha sido cargado"}

    cookies_path = "/etc/secrets/cookies1"
    if not os.path.exists(cookies_path):
        return {"error": "Archivo de cookies no encontrado"}

    ydl_opts = {
        'quiet': True,
        'cookiefile': cookies_path,
        'noplaylist': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitlesformat': 'vtt',
        'subtitleslangs': ['es', 'en'],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Título no encontrado')
            subtitles = info.get('subtitles') or info.get('automatic_captions')
            if not subtitles:
                return {"error": "No se encontraron subtítulos"}

            lang = 'es' if 'es' in subtitles else 'en'
            vtt_url = subtitles[lang][0]['url']

            vtt_content = requests.get(vtt_url).text
            with open("/tmp/tmp_subs.vtt", "w", encoding="utf-8") as f:
                f.write(vtt_content)

            loader = UnstructuredVTTLoader("/tmp/tmp_subs.vtt")
            documents = loader.load()
            text = documents[0].page_content

    except Exception as e:
        return {"error": "No se pudo cargar el video"}

    video = Videos(titulo=title, url=url, idUsuario=id_user)
    db.session.add(video)
    db.session.flush()
    id_video = video.id

    resultado = cargar_texto(500, text, id_user, id_video)
    return {"idVideo": id_video}


def obtener_id_transaccion(idVideo):
    return InfoVideo.query.with_entities(InfoVideo.id).filter(InfoVideo.idVideo == idVideo).first()[0]


def obtener_fila(idVideo, id_transaccion):
    return InfoVideo.query.filter(InfoVideo.idVideo == idVideo, InfoVideo.id == id_transaccion).first()


def generar_respuesta(pregunta, texto):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Eres un chatbot encargado de responder preguntas sobre videos. Para ello se te proporciona un texto y una pregunta. Tu objetivo es hacer lo que el usuario te pida."},
            {"role": "user", "content": f'La pregunta es: "{pregunta}" y la respuesta se encuentra en el siguiente texto: "{texto}"'}
        ]
    )
    return response.choices[0].message.content


def buscar(pregunta, embeddings, idVideo):
    pregunta_embedding = get_text_embedding(pregunta)
    similitud = [calculate_cosine_similarity(embedding, pregunta_embedding) for embedding in embeddings]
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

    videos_json = InfoVideo.query.with_entities(InfoVideo.embedding).filter(InfoVideo.idUsuario == id_usuario, InfoVideo.idVideo == idVideo).all()
    embeddings = [json.loads(video_json.embedding) for video_json in videos_json]

    respuesta = buscar(pregunta, embeddings, idVideo)
    llamada = Llamada(idUsuario=id_usuario, idVideo=idVideo, pregunta=pregunta, respuesta=respuesta, fecha=datetime.now())
    db.session.add(llamada)
    db.session.commit()
    return {"respuesta": respuesta}


def calculate_cosine_similarity(vector1, vector2):
    return cosine_similarity([vector1], [vector2])[0][0]


def split_text(content, chunk_size):
    chunks = []
    start = 0
    while start < len(content):
        end = start + chunk_size
        if end < len(content):
            while end < len(content) and content[end] != ".":
                end += 1
                if end == len(content):
                    break
        chunk = content[start:end+1]
        chunks.append(chunk)
        start = end + 1
    return chunks


def cargar_texto(chunk_size, contenido_video, id_user, idVideo):
    textos = split_text(contenido_video, chunk_size)
    for i, texto in enumerate(textos):
        embedding = get_text_embedding(texto)
        info_linea = InfoVideo(texto=texto, embedding=str(embedding), idUsuario=id_user, idVideo=idVideo)
        db.session.add(info_linea)
    db.session.commit()
    time.sleep(1)
    return "Embeddings generados"


def generar_embeddings(texto):
    summarizer = load_summarize_chain()
    embeddings = summarizer.get_embeddings(texto)
    return embeddings


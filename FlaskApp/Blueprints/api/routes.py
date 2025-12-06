import yt_dlp
from langchain_community.document_loaders.youtube import YoutubeLoader
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


# 🟦 PROXY RESIDENCIAL 
PROXY = "http://haxruvue-1:c159jygnowyp@p.webshare.io:80/"


def get_video_title(url):
    ydl_opts = {
        "quiet": True,
        "proxy": PROXY,    
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("title", "Título no encontrado")
    
    
# Funcion para generar embeddings desde texto
def get_text_embedding(text):
    embedding = client.embeddings.create(input=text, model="text-embedding-3-small").data[0].embedding
    return embedding


@login_required
def cargar_video_youtube():
    # Decodificar la URL
    datos = request.get_json()
    url = datos['url']
    id_user = current_user.id

    print("URL:", url)
    print("id_user:", id_user)

    # Comprobar si ya está cargado
    videos = Videos.query.filter_by(idUsuario=id_user).all()
    for video in videos:
        if video.url == url:
            return {"error": "El video ya ha sido cargado"}

    print("Cargando video de youtube...")

    loader = YoutubeLoader.from_youtube_url(
        url,
        add_video_info=False,
        language=["es", "en"],
        yt_dlp_options={
            "proxy": PROXY
        }
    )

    transcripcion = loader.load()
    print("Transcripción cargada")

    titulo = get_video_title(url)
    print("Titulo del video:", titulo)

    video = Videos(titulo=titulo, url=url, idUsuario=id_user)
    db.session.add(video)
    db.session.flush()
    id_video = video.id

    print("ID del video:", id_video)

    texto = transcripcion[0].page_content
    datafrme = cargar_texto(500, texto, id_user, id_video)

    print("DATAFRAME:", datafrme)

    return {"idVideo": id_video}


def obtener_id_transaccion(idVideo):
    return InfoVideo.query.with_entities(InfoVideo.id).filter(InfoVideo.idVideo == idVideo).first()[0]


def obtener_fila(idVideo, id_transaccion):
    return InfoVideo.query.filter(InfoVideo.idVideo == idVideo, InfoVideo.id == id_transaccion).first()


def generar_respuesta(pregunta, texto):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Eres un chatbot encargado de responder preguntas sobre videos."},
            {"role": "user", "content": f'La pregunta es: "{pregunta}" y la respuesta se encuentra en: "{texto}"'}
        ]
    )
    return response.choices[0].message.content


def buscar(pregunta, embeddings, idVideo):
    pregunta_embedding = get_text_embedding(pregunta)
    similitud = []

    for embedding in embeddings:
        similitud.append(calculate_cosine_similarity(embedding, pregunta_embedding))

    indices = np.argsort(similitud)[::-1]
    primer_id = obtener_id_transaccion(idVideo)

    fila = obtener_fila(idVideo, primer_id + indices[0])
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

        chunks.append(content[start:end+1])
        start = end + 1

    return chunks


def cargar_texto(chunk_size, contenido_video, id_user, idVideo):
    textos = split_text(contenido_video, chunk_size)

    print("Empezando a generar embeddings...")

    for i, texto in enumerate(textos):
        print("Generando embeddings para chunk:", i)
        emb = get_text_embedding(texto)

        info_linea = InfoVideo(
            texto=texto,
            embedding=str(emb),
            idUsuario=id_user,
            idVideo=idVideo
        )

        db.session.add(info_linea)

    db.session.commit()
    time.sleep(1)

    return "Embeddings generados"


def generar_embeddings(texto):
    summarizer = load_summarize_chain()
    embeddings = summarizer.get_embeddings(texto)
    return embeddings





# Funcion para cargar un video local

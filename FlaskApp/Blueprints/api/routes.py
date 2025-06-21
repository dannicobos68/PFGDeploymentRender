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
import os



def get_video_title(url):
    # Ruta al archivo cookies.txt, ajusta según tu estructura de carpetas
    cookies_path = os.path.join(os.path.dirname(__file__), './Cookies antibot YT/www.youtube.com_cookies.txt')

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

    
    
# Funcion para cargar un video de youtube
# Recibe la URL de un video y devuelve el texto del video
def get_text_embedding(text):
    embedding = client.embeddings.create(input=text, model="text-embedding-3-small").data[0].embedding
    return embedding

@login_required
def cargar_video_youtube():
    # Decodificar la URL
    datos = request.get_json()
    url = datos['url']
    id_user = current_user.id
    # Hacer algo con la URL
    print("URL: ", url)
    print("id_user", id_user)
    # Obtener todos los videos de youtube del usuario
    videos = Videos.query.filter_by(idUsuario=id_user).all()
    # Si ya ha cargado el video, devolver un error
    for video in videos:
        if video.url == url:
            return {"error": "El video ya ha sido cargado"}
    
    #print("Idioma: ", idioma)
    print("Cargando video de youtube...")
    loader = YoutubeLoader.from_youtube_url(url, add_video_info=False, language=["es", "en"])
    transcripcion = loader.load()
    print("Transcripción cargada")
    titulo = get_video_title(url)
    print("Titulo del video: ", titulo)
    video = Videos(titulo=titulo, url=url, idUsuario=id_user)
    db.session.add(video)
    db.session.flush()
    id_video = video.id
    print("ID del video: ", id_video)
    texto = transcripcion[0].page_content
    datafrme = cargar_texto(500, texto , id_user, id_video)
    print("DATAFRAME", datafrme)
    
    # Devolver un objeto JSON que indique que se ha completado la carga
    return {"idVideo": id_video}


def obtener_id_transaccion(idVideo):
    """
    Función que obtiene el ID de la transacción a partir del título
    """
    
    return InfoVideo.query.with_entities(InfoVideo.id).filter(InfoVideo.idVideo == idVideo).first()[0]
    #return InfoVideo.query.with_entities(InfoVideo.id).filter(InfoVideo.titulo == titulo).first()[0]

def obtener_fila(idVideo, id_transaccion):
    """
    Función que obtiene la fila de la base de datos a partir del título
    y el id de la transacción
    """
    return InfoVideo.query.filter(InfoVideo.idVideo == idVideo, InfoVideo.id == id_transaccion).first()

def generar_respuesta(pregunta, texto):
    text = pregunta
    resp = texto
    print("Pregunta: ", text)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un chatbot encargado de responder preguntas sobre videos. Para ello se te proporciona un texto y una pregunta. Tu objetivo es hacer lo que el usuario te pida."},
                {"role": "user", "content": f'La pregunta es: "{text}" y la respuesta se encuentra en el siguiente texto: "{resp}"'}
            ]
    )
    return response.choices[0].message.content

def buscar(pregunta, embeddings, idVideo):
    """
    Función que busca la respuesta a una pregunta en un conjunto de embeddings
    """
    # transformar la pregunta en embeddings
    pregunta_embedding = get_text_embedding(pregunta)
    similitud = []
    for embedding in embeddings:
        # Calcular la similitud entre la pregunta y el embedding
        print("EMBEDDING",type( embedding))
        similitud.append(calculate_cosine_similarity(embedding, pregunta_embedding))
    max_similitud = np.argmax(similitud)
    print("El maximo de similitud es: ", max_similitud)
    # Ordenar los indices de mayor a menor similitud
    indices = np.argsort(similitud)[::-1]
    print("Indices: ", indices)
    # Obtener el texto con mayor similitud
    primer_id = obtener_id_transaccion(idVideo)
    print("Primer id: ", primer_id)
    print("El ultimo id es: ", primer_id + len(embeddings)-1)
    fila = obtener_fila(idVideo, primer_id + int(indices[0]))

    print("Fila: ", fila)
    print("Texto: ", fila.texto)
    respuesta = generar_respuesta(pregunta, fila.texto)
    print("Respuesta: ", respuesta)
    return respuesta
        

@login_required
def realizar_pregunta():
    datos = request.get_json()
    pregunta = datos['pregunta']
    idVideo = datos['idVideo']
    print("Pregunta: ", pregunta)
    print("ID Video: ", idVideo)
    id_usuario = current_user.id
    # Obtener todos los embeddings del video del usuario con el titulo del video
    videos_json = InfoVideo.query.with_entities(InfoVideo.embedding).filter(InfoVideo.idUsuario == id_usuario, InfoVideo.idVideo == idVideo).all()
    embeddings = []
    for video_json in videos_json:
        embedding_json = video_json.embedding
        embedding = json.loads(embedding_json)
        embeddings.append(embedding)
    print(type(embeddings[0]))
    url = ""
    respuesta = buscar(pregunta, embeddings, idVideo)
    llamada = Llamada(idUsuario=id_usuario, idVideo=idVideo, pregunta=pregunta, respuesta=respuesta, fecha=datetime.now())
    db.session.add(llamada)
    db.session.commit()
    return {"respuesta": respuesta}

# Funcion para generar embeddings a partir de un video
# Recibe el texto y devuelve los embeddings

def calculate_cosine_similarity(vector1, vector2):
    return cosine_similarity([vector1], [vector2])[0][0]

def split_text(content, chunk_size):
    """
    Función que divide el texto en trozos de tamaño chunk_size 
    """
    chunks = []
    start = 0
    while start < len(content): # Bucle que recorre todo el texto del pdf
        end = start + chunk_size # END = 0 + 1000
        if end < len(content): # Si no se ha llegado al final del pdf 
            # Buscar el último punto "." dentro del rango de caracteres
            while content[end] != "." and end > start:
                end += 1
                if end == len(content):
                    break
        chunk = content[start:end+1]
        chunks.append(chunk)
        start = end + 1
    return chunks

def cargar_texto(chunk_size, contenido_video, id_user, idVideo):
    """
    Carga el texto dado por el título del video y lo procesa para extraer
    y organizar el texto en párrafos.
    """
    # Expresión regular para buscar la frase deseada y extraer el número de página
    # Expresión regular para buscar la frase "Objeto del documento"
    textos = []
    chunks = split_text(contenido_video, chunk_size)
    textos.extend(chunks)
    
    # Eliminar Normativas/ del título
    print("Empezando a generar embeddings...")
    total_tokens = 0
    for i, texto in enumerate(textos):
        print("Generando embeddings para el texto: ", i)
        embedding = get_text_embedding(texto)
        # Buscar en el texto la frase deseada y extraer el número de página
        embedding = str(embedding)
        print("Embedding: ", embedding)
        info_linea = InfoVideo(texto=texto, embedding=embedding, idUsuario=id_user, idVideo=idVideo)
        db.session.add(info_linea)
    db.session.commit()
    # Eliminar las filas que solo tengan un caracter o menos
    # Modificar el índice del dataframe
    time.sleep(1)
    #print("Total de textos: ", len(parrafos), "\n")
    return "Embeddings generados"


def generar_embeddings(texto):
    summarizer = load_summarize_chain()
    embeddings = summarizer.get_embeddings(texto)
    return embeddings




# Funcion para cargar un video local
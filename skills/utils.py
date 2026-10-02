import os
import requests
import unicodedata
from dotenv import load_dotenv

load_dotenv()

# 1. Leemos lo que el cliente configuró en el .env (¡Sin tocar código!)
url_cliente = os.getenv("URL_MOODLE", "http://localhost/webservice/rest/server.php")
TOKEN_LOCAL = os.getenv("TOKEN_LOCAL")

# 2. TRUCO DEVOPS: Traducimos la URL automáticamente para que Docker la entienda
URL_LOCAL = url_cliente.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")

CABECERAS = {"Host": "localhost"}


def quitar_tildes(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn')

def buscar_id_materia(nombre_buscado):
    nombre_limpio = quitar_tildes(nombre_buscado.lower())
    parametros = {"wstoken": TOKEN_LOCAL, "wsfunction": "core_course_get_courses", "moodlewsrestformat": "json"}
    
    # Le pasamos el DNI falso a Moodle
    cursos = requests.get(URL_LOCAL, params=parametros, headers=CABECERAS).json()
    
    if type(cursos) is list:
        for curso in cursos:
            curso_limpio = quitar_tildes(curso.get('fullname', '').lower())
            if nombre_limpio in curso_limpio:
                return curso['id']
    return None
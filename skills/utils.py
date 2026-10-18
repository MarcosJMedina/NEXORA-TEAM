import os
import requests
import unicodedata
from dotenv import load_dotenv

load_dotenv()

# 1. Leemos lo que el cliente configuró en el .env (¡Sin tocar código!)
url_cliente = os.getenv("URL_MOODLE") or os.getenv("MOODLE_URL") or "http://localhost/webservice/rest/server.php"
TOKEN_LOCAL = os.getenv("TOKEN_LOCAL") or os.getenv("MOODLE_TOKEN")

# 2. TRUCO DEVOPS: Traducimos la URL automáticamente para que Docker la entienda
if "ngrok" in url_cliente or url_cliente.startswith("https://"):
    URL_LOCAL = url_cliente
    CABECERAS = {}
else:
    URL_LOCAL = url_cliente.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
    CABECERAS = {"Host": "localhost"}


def quitar_tildes(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn')


def buscar_id_materia(nombre_buscado):
    if not nombre_buscado:
        return None
    nombre_limpio = quitar_tildes(str(nombre_buscado).strip().lower())
    if not nombre_limpio:
        return None

    parametros = {"wstoken": TOKEN_LOCAL, "wsfunction": "core_course_get_courses", "moodlewsrestformat": "json"}
    try:
        cursos = requests.get(URL_LOCAL, params=parametros, headers=CABECERAS, timeout=15).json()
        if not isinstance(cursos, list):
            return None

        # Intento 1: 'in' normal (ignorando portada ID 1)
        for curso in cursos:
            if curso.get('id') == 1:
                continue
            curso_limpio = quitar_tildes(curso.get('fullname', '').strip().lower())
            if not curso_limpio:
                continue
            if nombre_limpio in curso_limpio or curso_limpio in nombre_limpio:
                return curso.get('id')

        # Intento 2: Búsqueda difusa (Fuzzy Matching) por palabras clave (omitiendo palabras <= 3 letras como 'de', 'la')
        palabras_clave = [p for p in nombre_limpio.split() if len(p) > 3]
        for curso in cursos:
            if curso.get('id') == 1:
                continue
            curso_limpio = quitar_tildes(curso.get('fullname', '').strip().lower())
            if not curso_limpio:
                continue
            for palabra in palabras_clave:
                if palabra in curso_limpio:
                    print(f"[FUZZY MATCH] Coincidencia difusa encontrada: '{palabra}' en '{curso.get('fullname')}' (ID: {curso.get('id')})")
                    return curso.get('id')

    except Exception as e:
        print(f"Error al buscar materias en Moodle: {e}")
    return None


def verificar_usuario_en_materia(user_id: int, course_id: int) -> bool:
    if user_id <= 1:
        return False
    if user_id == 2:
        return True
    parametros = {
        'wstoken': TOKEN_LOCAL,
        'wsfunction': 'core_enrol_get_users_courses',
        'moodlewsrestformat': 'json',
        'userid': user_id
    }
    try:
        respuesta = requests.get(URL_LOCAL, params=parametros, headers=CABECERAS)
        cursos = respuesta.json()
        if isinstance(cursos, list):
            for curso in cursos:
                if curso.get('id') == course_id:
                    return True
        return False
    except Exception as e:
        print(f"Error al verificar matricula de usuario {user_id} en curso {course_id}: {e}")
        return False
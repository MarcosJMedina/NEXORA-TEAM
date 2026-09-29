import os
import requests
import unicodedata

URL_LOCAL = os.getenv("MOODLE_URL", "http://localhost/webservice/rest/server.php")
TOKEN_LOCAL = os.getenv("MOODLE_TOKEN", "31b45f753eaa5052fefd25a5b7b39226")

def quitar_tildes(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn')

def buscar_id_materia(nombre_buscado):
    nombre_limpio = quitar_tildes(nombre_buscado.lower())
    parametros = {"wstoken": TOKEN_LOCAL, "wsfunction": "core_course_get_courses", "moodlewsrestformat": "json"}
    try:
        cursos = requests.get(URL_LOCAL, params=parametros).json()
        if isinstance(cursos, list):
            for curso in cursos:
                curso_limpio = quitar_tildes(curso.get('fullname', '').lower())
                if nombre_limpio in curso_limpio:
                    return curso.get('id')
    except Exception as e:
        print(f"Error al buscar materias en Moodle: {e}")
    return None

def obtener_cursos_matriculados(id_usuario):
    """Obtiene la lista de cursos en los que el usuario está matriculado en Moodle."""
    parametros = {
        "wstoken": TOKEN_LOCAL,
        "wsfunction": "core_enrol_get_users_courses",
        "moodlewsrestformat": "json",
        "userid": id_usuario
    }
    try:
        respuesta = requests.get(URL_LOCAL, params=parametros).json()
        if isinstance(respuesta, list):
            return respuesta
    except Exception as e:
        print(f"Error al consultar matriculación en Moodle: {e}")
    return []

def verificar_acceso_materia(id_usuario, nombre_buscado):
    """
    Verifica si el usuario está matriculado en la materia solicitada.
    Retorna:
        tiene_acceso (bool): True si el usuario está matriculado.
        id_materia (int | None): ID del curso.
        nombre_oficial (str | None): Nombre del curso.
        materia_existe (bool): True si el curso existe en Moodle aunque el usuario no esté matriculado.
    """
    nombre_limpio = quitar_tildes(nombre_buscado.lower())
    cursos_usuario = obtener_cursos_matriculados(id_usuario)

    for curso in cursos_usuario:
        curso_limpio = quitar_tildes(curso.get('fullname', '').lower())
        short_limpio = quitar_tildes(curso.get('shortname', '').lower())
        if nombre_limpio in curso_limpio or nombre_limpio in short_limpio:
            return True, curso.get('id'), curso.get('fullname'), True

    # Si no está matriculado, verificamos si la materia existe globalmente en Moodle
    id_materia_global = buscar_id_materia(nombre_buscado)
    if id_materia_global is not None:
        return False, id_materia_global, None, True

    return False, None, None, False
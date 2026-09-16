import requests
import unicodedata

URL_LOCAL = "http://localhost/webservice/rest/server.php"
TOKEN_LOCAL = "31b45f753eaa5052fefd25a5b7b39226"

def quitar_tildes(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn')

def buscar_id_materia(nombre_buscado):
    nombre_limpio = quitar_tildes(nombre_buscado.lower())
    parametros = {"wstoken": TOKEN_LOCAL, "wsfunction": "core_course_get_courses", "moodlewsrestformat": "json"}
    cursos = requests.get(URL_LOCAL, params=parametros).json()
    
    if type(cursos) is list:
        for curso in cursos:
            curso_limpio = quitar_tildes(curso.get('fullname', '').lower())
            if nombre_limpio in curso_limpio:
                return curso['id']
    return None
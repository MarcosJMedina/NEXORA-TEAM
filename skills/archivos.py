import os
import requests
import docx
import pypdf
from crewai.tools import tool
from skills.utils import buscar_id_materia, URL_LOCAL, TOKEN_LOCAL, CABECERAS

# Obtenemos la ruta de la carpeta principal del proyecto
carpeta_principal = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@tool("Buscador Inteligente de Apuntes")
def tool_archivos(nombre_materia: str, tema_a_buscar: str) -> str:
    """
    ¡HERRAMIENTA RAG! Úsala para leer apuntes de una materia.
    - nombre_materia: Nombre de la materia.
    - tema_a_buscar: Palabras clave muy específicas del tema. Si el alumno pide un resumen general o no especifica un tema exacto, DEBES escribir textualmente 'resumen general'.
    """
    print(f"\n🕵️‍♂️ [DEBUG RAG] 1. Buscando materia: '{nombre_materia}'")
    
    id_materia = buscar_id_materia(nombre_materia)
    if not id_materia: 
        print(f"❌ [DEBUG RAG] Materia '{nombre_materia}' no encontrada en Moodle.")
        return f"Error: No encontré la materia {nombre_materia}."
    
    print(f"✅ [DEBUG RAG] 2. ID encontrado: {id_materia}. Pidiendo archivos a Moodle...")
    parametros = {"wstoken": TOKEN_LOCAL, "wsfunction": "core_course_get_contents", "moodlewsrestformat": "json", "courseid": id_materia}
    datos = requests.get(URL_LOCAL, params=parametros, headers=CABECERAS).json()
    
    url_archivo, nombre_archivo = None, None
    
    if type(datos) is list:
        for seccion in datos:
            for modulo in seccion.get('modules', []):
                for contenido in modulo.get('contents', []):
                    if 'fileurl' in contenido: 
                        url_archivo = contenido['fileurl']
                        nombre_archivo = contenido['filename']
                        break
    
    if not url_archivo: 
        return f"No hay archivos en la materia {nombre_materia}."
    
    # 🌐 Traducción de la URL para Docker
    url_archivo = url_archivo.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
    url_descarga = f"{url_archivo}&token={TOKEN_LOCAL}"
    ruta = os.path.join(carpeta_principal, "BOT_" + nombre_archivo)
    
    print(f"⬇️ [DEBUG RAG] 5. Intentando descargar: {nombre_archivo}")
    respuesta = requests.get(url_descarga, headers=CABECERAS)
    
    if respuesta.status_code != 200:
        return "Error de red al descargar el archivo."

    with open(ruta, 'wb') as f: 
        f.write(respuesta.content)
    
    print(f"✅ [DEBUG RAG] 6. Archivo descargado. Extrayendo texto...")
    _, ext = os.path.splitext(ruta.lower())
    texto_extraido = ""
    
    try:
        if ext == ".docx": 
            texto_extraido = "\n".join([p.text for p in docx.Document(ruta).paragraphs])
        elif ext == ".pdf":
            with open(ruta, "rb") as f: 
                texto_extraido = "\n".join([p.extract_text() for p in pypdf.PdfReader(f).pages if p.extract_text()])
        
        if not texto_extraido: 
            return "El archivo está vacío o es una imagen."
            
        print(f"✅ [DEBUG RAG] 7. Texto extraído. Buscando: '{tema_a_buscar}'...")
        LIMITE_CARACTERES = 4000
        
        if tema_a_buscar.lower() != "resumen general" and len(texto_extraido) > LIMITE_CARACTERES:
            parrafos = texto_extraido.split('\n')
            palabras_clave = [p.lower() for p in tema_a_buscar.split() if len(p) > 3]
            fragmentos_utiles = [p for p in parrafos if any(kw in p.lower() for kw in palabras_clave)]
            
            if fragmentos_utiles:
                return f"[RESULTADO RAG DE {nombre_materia}]:\n" + "\n...\n".join(fragmentos_utiles)[:LIMITE_CARACTERES]
            else:
                # 🌟 EL PLAN B: Si no encuentra las palabras, devuelve el resumen general
                print("⚠️ [DEBUG RAG] No encontré las palabras exactas, devolviendo el principio del documento por defecto.")
                return f"[APUNTE DE {nombre_materia} (Resumen General)]:\n" + texto_extraido[:LIMITE_CARACTERES]
                
        return f"[APUNTE DE {nombre_materia}]:\n" + texto_extraido[:LIMITE_CARACTERES]
        
    except Exception as e: 
        return f"Error al leer archivo: {e}"
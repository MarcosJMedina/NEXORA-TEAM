import os
import requests
import docx
import pypdf
from crewai.tools import tool
from skills.utils import buscar_id_materia, URL_LOCAL, TOKEN_LOCAL

# Obtenemos la ruta de la carpeta principal del proyecto
carpeta_principal = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@tool("Buscador Inteligente de Apuntes")
def tool_archivos(nombre_materia: str, tema_a_buscar: str) -> str:
    """¡HERRAMIENTA RAG! Úsala para leer apuntes de una materia."""
    id_materia = buscar_id_materia(nombre_materia)
    if not id_materia: return f"Error: No encontré la materia {nombre_materia}."
    
    parametros = {"wstoken": TOKEN_LOCAL, "wsfunction": "core_course_get_contents", "moodlewsrestformat": "json", "courseid": id_materia}
    datos = requests.get(URL_LOCAL, params=parametros).json()
    url_archivo, nombre_archivo = None, None
    
    if type(datos) is list:
        for seccion in datos:
            for modulo in seccion.get('modules', []):
                for contenido in modulo.get('contents', []):
                    if 'fileurl' in contenido: 
                        url_archivo, nombre_archivo = contenido['fileurl'], contenido['filename']
                        break
    
    if not url_archivo: return f"No hay archivos en la materia {nombre_materia}."
    
    ruta = os.path.join(carpeta_principal, "BOT_" + nombre_archivo)
    with open(ruta, 'wb') as f: f.write(requests.get(f"{url_archivo}&token={TOKEN_LOCAL}").content)
    
    _, ext = os.path.splitext(ruta.lower())
    texto_extraido = ""
    try:
        if ext == ".docx": 
            texto_extraido = "\n".join([p.text for p in docx.Document(ruta).paragraphs])
        elif ext == ".pdf":
            with open(ruta, "rb") as f: 
                texto_extraido = "\n".join([p.extract_text() for p in pypdf.PdfReader(f).pages if p.extract_text()])
        
        if not texto_extraido: return "El archivo está vacío o es una imagen."
        
        LIMITE_CARACTERES = 4000
        if tema_a_buscar.lower() != "resumen general" and len(texto_extraido) > LIMITE_CARACTERES:
            print(f"🔍 [RAG] Buscando '{tema_a_buscar}' en el documento...")
            parrafos = texto_extraido.split('\n')
            palabras_clave = [p.lower() for p in tema_a_buscar.split() if len(p) > 3]
            
            fragmentos_utiles = [p for p in parrafos if any(kw in p.lower() for kw in palabras_clave)]
            
            if fragmentos_utiles:
                texto_filtrado = "\n...\n".join(fragmentos_utiles)
                return f"[RESULTADO RAG DE {nombre_materia}]:\n" + texto_filtrado[:LIMITE_CARACTERES]
            else:
                return f"Leí el archivo de {nombre_materia} pero no encontré menciones exactas sobre ese tema."
                
        return f"[APUNTE DE {nombre_materia}]:\n" + texto_extraido[:LIMITE_CARACTERES]
    except Exception as e: 
        return f"Error al leer archivo: {e}"
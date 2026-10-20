"""
Script independiente para indexar documentos de Moodle en Qdrant.
Utiliza las variables de entorno configuradas en el archivo .env (URL_MOODLE, TOKEN_LOCAL).
También mantiene compatibilidad con la carpeta local ./moodles_pdfs si existen archivos estáticos.
"""

import os
import sys
import requests
import docx
import pypdf
from dotenv import load_dotenv

# Asegurar carga del .env del proyecto
load_dotenv()

from vector_qdrant import inicializar_qdrant, indexar_lote, indexar_texto, COLECCION_NAME

# =====================================================================
# CONFIGURACIÓN Y CREDENCIALES DE MOODLE
# =====================================================================
URL_MOODLE = os.getenv("URL_MOODLE") or os.getenv("MOODLE_URL") or "http://localhost/webservice/rest/server.php"
TOKEN_LOCAL = os.getenv("TOKEN_LOCAL") or os.getenv("MOODLE_TOKEN")
CARPETA_PDFS = os.getenv("CARPETA_PDFS", "./moodles_pdfs")

# Traducción de URL para Docker / Entorno local
if "ngrok" in URL_MOODLE or URL_MOODLE.startswith("https://"):
    URL_ENDPOINT = URL_MOODLE
    CABECERAS = {}
else:
    URL_ENDPOINT = URL_MOODLE.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
    CABECERAS = {"Host": "localhost"}


# =====================================================================
# DIVISIÓN EN CHUNKS (TEXT SPLITTER)
# =====================================================================
def dividir_en_chunks(texto: str, chunk_size: int = 1000, chunk_overlap: int = 150) -> list[str]:
    """Divide el texto respetando saltos de línea y oraciones."""
    # Intentar usar RecursiveCharacterTextSplitter si está instalado
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        return splitter.split_text(texto)
    except ImportError:
        pass

    # Splitter nativo fallback
    texto = texto.strip()
    if not texto:
        return []
    chunks = []
    inicio = 0
    total = len(texto)
    while inicio < total:
        fin = inicio + chunk_size
        if fin >= total:
            chunk = texto[inicio:].strip()
            if chunk:
                chunks.append(chunk)
            break
        corte = texto.rfind('\n', inicio, fin)
        if corte == -1 or corte <= inicio + chunk_size // 2:
            corte = texto.rfind('. ', inicio, fin)
        if corte == -1 or corte <= inicio + chunk_size // 2:
            corte = fin
        else:
            corte += 1
        chunk = texto[inicio:corte].strip()
        if chunk:
            chunks.append(chunk)
        inicio = max(inicio + 1, corte - chunk_overlap)
    return chunks


# =====================================================================
# EXTRACCIÓN Y DESCARGA DESDE MOODLE
# =====================================================================
def extraer_texto_archivo(ruta_local: str) -> str:
    """Extrae texto de archivos .pdf o .docx."""
    _, ext = os.path.splitext(ruta_local.lower())
    texto = ""
    try:
        if ext == ".docx":
            doc = docx.Document(ruta_local)
            texto = "\n".join([p.text for p in doc.paragraphs if p.text])
        elif ext == ".pdf":
            with open(ruta_local, "rb") as f:
                reader = pypdf.PdfReader(f)
                texto = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
    except Exception as e:
        print(f"⚠️ Error extrayendo texto de {ruta_local}: {e}")
    return texto


def indexar_desde_moodle():
    """Descarga e indexa en Qdrant todos los documentos visibles de los cursos de Moodle."""
    if not TOKEN_LOCAL:
        print("⚠️ [INDEXADOR] No se encontró TOKEN_LOCAL en el .env. Omitiendo escaneo de Moodle.")
        return 0

    print(f"🌐 [INDEXADOR] Conectando a Moodle en {URL_ENDPOINT}...")
    parametros_cursos = {
        "wstoken": TOKEN_LOCAL,
        "wsfunction": "core_course_get_courses",
        "moodlewsrestformat": "json"
    }

    try:
        resp = requests.get(URL_ENDPOINT, params=parametros_cursos, headers=CABECERAS, timeout=20)
        cursos = resp.json()
        if not isinstance(cursos, list):
            print(f"⚠️ [INDEXADOR] Respuesta no válida al listar cursos: {cursos}")
            return 0
    except Exception as e:
        print(f"❌ [INDEXADOR] No se pudo conectar a la API de Moodle: {e}")
        return 0

    total_fragmentos = 0
    carpeta_temp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_indexador")
    os.makedirs(carpeta_temp, exist_ok=True)

    for curso in cursos:
        course_id = curso.get("id")
        course_name = curso.get("fullname", f"Curso_{course_id}")
        if course_id == 1:
            # Omitir portada del sitio
            continue

        print(f"\n📚 [INDEXADOR] Procesando materia: '{course_name}' (ID: {course_id})")

        parametros_contenidos = {
            "wstoken": TOKEN_LOCAL,
            "wsfunction": "core_course_get_contents",
            "moodlewsrestformat": "json",
            "courseid": course_id
        }

        try:
            datos_curso = requests.get(URL_ENDPOINT, params=parametros_contenidos, headers=CABECERAS, timeout=25).json()
        except Exception as e:
            print(f"⚠️ Error obteniendo contenidos de curso {course_id}: {e}")
            continue

        if not isinstance(datos_curso, list):
            continue

        for seccion in datos_curso:
            if seccion.get("visible") == 0 or seccion.get("uservisible") is False:
                continue

            sec_nombre = seccion.get("name", "General")
            for modulo in seccion.get("modules", []):
                if modulo.get("visible") == 0 or modulo.get("uservisible") is False:
                    continue

                for cont in modulo.get("contents", []):
                    if "fileurl" not in cont:
                        continue
                    nombre_archivo = cont.get("filename", "documento")
                    _, ext = os.path.splitext(nombre_archivo.lower())
                    if ext not in [".pdf", ".docx"]:
                        continue

                    url_archivo = cont["fileurl"]
                    if "token=" not in url_archivo:
                        url_descarga = f"{url_archivo}&token={TOKEN_LOCAL}"
                    else:
                        url_descarga = url_archivo

                    ruta_descarga = os.path.join(carpeta_temp, f"{course_id}_{nombre_archivo}")
                    print(f"  ⬇️ Descargando: {nombre_archivo} (Sección: {sec_nombre})")

                    try:
                        res = requests.get(url_descarga, headers=CABECERAS, timeout=30)
                        if res.status_code != 200:
                            print(f"  ⚠️ Error de descarga (HTTP {res.status_code})")
                            continue
                        with open(ruta_descarga, "wb") as f_out:
                            f_out.write(res.content)

                        texto_doc = extraer_texto_archivo(ruta_descarga)
                        if not texto_doc.strip():
                            continue

                        chunks = dividir_en_chunks(texto_doc, chunk_size=1000, chunk_overlap=150)
                        metas = [
                            {
                                "fuente": nombre_archivo,
                                "archivo": nombre_archivo,
                                "materia": course_name,
                                "id_materia": course_id,
                                "seccion": sec_nombre,
                                "chunk": i
                            }
                            for i in range(len(chunks))
                        ]

                        indexar_lote(chunks, metas)
                        total_fragmentos += len(chunks)
                        print(f"  ✅ {len(chunks)} fragmentos indexados de '{nombre_archivo}'.")

                        # Limpieza de archivo temporal
                        try:
                            os.remove(ruta_descarga)
                        except OSError:
                            pass

                    except Exception as err:
                        print(f"  ⚠️ Error al procesar {nombre_archivo}: {err}")

    # Limpiar directorio temporal
    try:
        os.rmdir(carpeta_temp)
    except OSError:
        pass

    return total_fragmentos


def indexar_carpeta_local():
    """Indexa PDFs estáticos ubicados en CARPETA_PDFS (compatibilidad con Dev 2)."""
    if not os.path.exists(CARPETA_PDFS):
        return 0

    archivos_pdf = [f for f in os.listdir(CARPETA_PDFS) if f.lower().endswith(".pdf")]
    if not archivos_pdf:
        return 0

    print(f"\n📁 [INDEXADOR LOCAL] Procesando carpeta {CARPETA_PDFS} ({len(archivos_pdf)} archivos)...")
    total_local = 0

    for arch in archivos_pdf:
        ruta = os.path.join(CARPETA_PDFS, arch)
        texto = extraer_texto_archivo(ruta)
        if not texto.strip():
            continue

        chunks = dividir_en_chunks(texto, chunk_size=1000, chunk_overlap=150)
        metas = [
            {
                "fuente": arch,
                "archivo": arch,
                "materia": "Local",
                "chunk": i
            }
            for i in range(len(chunks))
        ]
        indexar_lote(chunks, metas)
        total_local += len(chunks)

    return total_local


def main():
    print("=" * 60)
    print("🚀 INICIANDO INDEXADOR QDRANT PARA MOODLE (NEXORA)")
    print("=" * 60)

    inicializar_qdrant()

    # 1. Indexar desde la API de Moodle usando URL_MOODLE y TOKEN_LOCAL
    total_moodle = indexar_desde_moodle()

    # 2. Indexar carpeta local de PDFs si existe
    total_local = indexar_carpeta_local()

    total_general = total_moodle + total_local
    print("\n" + "=" * 60)
    print(f"🎉 Proceso finalizado. Total: {total_general} fragmentos indexados en Qdrant.")
    print("=" * 60)


if __name__ == "__main__":
    main()

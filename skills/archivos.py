import os
import re
import unicodedata
import requests
import docx
import pypdf
import chromadb
from chromadb.utils import embedding_functions
from crewai.tools import tool
from skills.utils import buscar_id_materia, URL_LOCAL, TOKEN_LOCAL, CABECERAS

# Ruta base del proyecto y carpeta de persistencia de ChromaDB
carpeta_principal = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(carpeta_principal, "chroma_data")

# Inicialización diferida (Lazy) del cliente de ChromaDB y función de embedding local
_cliente_chroma = None
_embedding_fn = None


def obtener_cliente_chroma():
    """Inicializa o retorna la instancia persistente del cliente ChromaDB."""
    global _cliente_chroma
    if _cliente_chroma is None:
        os.makedirs(CHROMA_PATH, exist_ok=True)
        _cliente_chroma = chromadb.PersistentClient(path=CHROMA_PATH)
    return _cliente_chroma


def obtener_embedding_function():
    """
    Retorna la función de embedding por defecto de ChromaDB (Sentence Transformers / all-MiniLM-L6-v2),
    operando de forma 100% local sin necesidad de claves de API externas.
    """
    global _embedding_fn
    if _embedding_fn is None:
        try:
            _embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        except Exception as e:
            print(f"⚠️ [CHROMA] Advertencia al instanciar DefaultEmbeddingFunction: {e}")
            _embedding_fn = None
    return _embedding_fn


def sanitizar_nombre_coleccion(materia: str) -> str:
    """
    ChromaDB exige nombres de colección de 3 a 63 caracteres, únicamente
    con caracteres alfanuméricos, guiones y guiones bajos [a-zA-Z0-9_-],
    comenzando y terminando en un alfanumérico.
    """
    texto = unicodedata.normalize('NFKD', str(materia)).encode('ASCII', 'ignore').decode('utf-8').lower()
    limpio = re.sub(r'[^a-z0-9_-]', '_', texto)
    limpio = re.sub(r'_+', '_', limpio).strip('_-')
    nombre_col = f"col_{limpio}"[:63].rstrip('_-')
    if len(nombre_col) < 3:
        nombre_col = "col_materia"
    return nombre_col


def dividir_en_chunks(texto: str, chunk_size: int = 800, chunk_overlap: int = 150) -> list[str]:
    """
    Text Splitter básico con solapamiento (overlap) para mantener la continuidad contextual.
    Intenta cortar preferentemente en saltos de línea o puntos para no cortar oraciones al medio.
    """
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


def obtener_archivos_visibles_moodle(nombre_materia: str):
    """
    Obtiene la lista de archivos válidos (.pdf o .docx) y visibles de una materia en Moodle respetando permisos.
    Retorna: (id_materia, archivos_a_procesar, error_o_aviso)
    """
    id_materia = buscar_id_materia(nombre_materia)
    if not id_materia:
        print(f"❌ [DEBUG RAG] Materia '{nombre_materia}' no encontrada en Moodle.")
        return None, [], f"Error: No encontré la materia {nombre_materia}."

    parametros = {
        "wstoken": TOKEN_LOCAL,
        "wsfunction": "core_course_get_contents",
        "moodlewsrestformat": "json",
        "courseid": id_materia
    }
    try:
        datos = requests.get(URL_LOCAL, params=parametros, headers=CABECERAS, timeout=20).json()
    except Exception as e:
        return id_materia, [], f"Error de conexión con Moodle: {e}"

    archivos_a_procesar = []
    if isinstance(datos, list):
        for seccion in datos:
            # BARRERA DE PERMISOS: Omitir secciones ocultas para el estudiante
            if seccion.get('visible') == 0 or seccion.get('uservisible') is False:
                continue

            sec_nombre = seccion.get('name', 'General')
            for modulo in seccion.get('modules', []):
                # BARRERA DE PERMISOS: Omitir recursos o módulos ocultos
                if modulo.get('visible') == 0 or modulo.get('uservisible') is False:
                    continue

                for contenido in modulo.get('contents', []):
                    if 'fileurl' in contenido:
                        nombre_arch = contenido.get('filename', 'documento')
                        _, ext = os.path.splitext(nombre_arch.lower())
                        if ext in [".pdf", ".docx"]:
                            archivos_a_procesar.append({
                                'url': contenido['fileurl'],
                                'nombre': nombre_arch,
                                'seccion': sec_nombre
                            })

    if not archivos_a_procesar:
        return id_materia, [], f"No hay archivos o contenidos visibles en la materia {nombre_materia}."

    return id_materia, archivos_a_procesar, None


@tool("listador_de_archivos")
def tool_listar_archivos(nombre_materia: str) -> str:
    """
    ¡HERRAMIENTA PARA NOMBRAR Y LISTAR ARCHIVOS!
    Úsala cuando el alumno te pida nombrar, listar o saber qué archivos, PDFs o Words
    hay disponibles en una materia específica de Moodle.
    - nombre_materia: Nombre de la materia (ej. 'base de datos', 'sistemas operativos').
    """
    print(f"\n📂 [LISTADOR] Listando archivos oficiales de la materia: '{nombre_materia}'")
    id_materia, archivos_visibles, error = obtener_archivos_visibles_moodle(nombre_materia)
    if error:
        return error

    lineas = [f"Archivos y documentos oficiales disponibles en '{nombre_materia}' (Total: {len(archivos_visibles)}):"]
    for i, arch in enumerate(archivos_visibles, 1):
        nombre = arch['nombre']
        _, ext = os.path.splitext(nombre.lower())
        tipo = "PDF" if ext == ".pdf" else ("Word" if ext in [".docx", ".doc"] else ext.upper().lstrip('.'))
        sec = arch.get('seccion', 'General')
        lineas.append(f"{i}. [{tipo}] {nombre} (Sección: {sec})")

    lineas.append("\nPregunta cordialmente al alumno cuál de estos documentos desea que le resumas o expliques en detalle.")
    return "\n".join(lineas)


@tool("buscador_de_apuntes")
def tool_archivos(nombre_materia: str, tema_a_buscar: str) -> str:
    """
    ¡HERRAMIENTA RAG! Úsala para leer, resumir o explicar apuntes o archivos específicos de una materia.
    - nombre_materia: Nombre de la materia.
    - tema_a_buscar: Nombre del archivo específico que el alumno eligió (ej. 'Normalizacion.docx', 'el segundo archivo') o palabras clave del tema a buscar. Si el alumno pide un resumen general o no especifica un tema exacto, DEBES escribir textualmente 'resumen general'.
    """
    print(f"\n🕵️‍♂️ [DEBUG RAG] 1. Buscando materia: '{nombre_materia}' | Tema/Archivo: '{tema_a_buscar}'")

    tema_lower = str(tema_a_buscar).lower().strip()
    # Si la petición es para listar archivos, derivar automáticamente
    palabras_listar = [
        "listar", "lista", "nombr", "cuales", "que archivo", "que doc", 
        "archivos", "documentos", "material", "que hay", "que tenemos",
        "cada uno de los archivos", "mostrar", "ver archivos"
    ]
    if any(k in tema_lower for k in palabras_listar):
        print(f"🔄 [AUTO-ROUTER] Petición de listado detectada en tool_archivos ('{tema_a_buscar}'). Derivando a tool_listar_archivos...")
        return tool_listar_archivos(nombre_materia)

    id_materia, archivos_a_procesar, error = obtener_archivos_visibles_moodle(nombre_materia)
    if error:
        return error

    print(f"✅ [DEBUG RAG] 2. ID encontrado: {id_materia} con {len(archivos_a_procesar)} archivo(s) válido(s) a procesar.")

    # Inicialización de ChromaDB y Embedding Function
    cliente = obtener_cliente_chroma()
    ef = obtener_embedding_function()

    # Nombramos la colección basándonos en el id_materia (representa a la MATERIA COMPLETA)
    nombre_col = sanitizar_nombre_coleccion(str(id_materia))

    if ef:
        coleccion = cliente.get_or_create_collection(name=nombre_col, embedding_function=ef)
    else:
        coleccion = cliente.get_or_create_collection(name=nombre_col)

    texto_extraido = ""

    # Si la colección está vacía (count() == 0), iteramos sobre archivos_a_procesar,
    # descargamos cada uno, extraemos el texto, dividimos en chunks y hacemos upsert acumulando los datos
    if coleccion.count() == 0:
        todos_los_chunks = []
        todos_los_ids = []
        todos_los_metadatas = []

        for arch_idx, arch in enumerate(archivos_a_procesar):
            url_archivo = arch['url']
            nombre_archivo = arch['nombre']

            # 🌐 Traducción de la URL para Docker y descarga segura
            if "ngrok" in url_archivo or url_archivo.startswith("https://"):
                url_descarga = f"{url_archivo}&token={TOKEN_LOCAL}" if "token=" not in url_archivo else url_archivo
                cabeceras_descarga = {}
            else:
                url_archivo_docker = url_archivo.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
                url_descarga = f"{url_archivo_docker}&token={TOKEN_LOCAL}" if "token=" not in url_archivo else url_archivo_docker
                cabeceras_descarga = CABECERAS

            ruta = os.path.join(carpeta_principal, f"BOT_{id_materia}_{nombre_archivo}")
            print(f"⬇️ [DEBUG RAG] Intentando descargar ({arch_idx+1}/{len(archivos_a_procesar)}): {nombre_archivo}")
            try:
                respuesta = requests.get(url_descarga, headers=cabeceras_descarga, timeout=25)
                if respuesta.status_code != 200:
                    print(f"⚠️ [DEBUG RAG] Error al descargar {nombre_archivo}: HTTP {respuesta.status_code}")
                    continue

                with open(ruta, 'wb') as f:
                    f.write(respuesta.content)

                _, ext = os.path.splitext(nombre_archivo.lower())
                texto_archivo = ""

                if ext == ".docx":
                    doc = docx.Document(ruta)
                    texto_archivo = "\n".join([p.text for p in doc.paragraphs if p.text])
                elif ext == ".pdf":
                    with open(ruta, "rb") as f:
                        reader = pypdf.PdfReader(f)
                        texto_archivo = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])

                if texto_archivo and texto_archivo.strip():
                    texto_extraido += f"\n--- [{nombre_archivo}] ---\n" + texto_archivo
                    chunks_arch = dividir_en_chunks(texto_archivo, chunk_size=800, chunk_overlap=150)
                    for c_i, ch in enumerate(chunks_arch):
                        chunk_id = f"materia_{id_materia}_doc_{arch_idx}_chunk_{c_i}"
                        todos_los_ids.append(chunk_id)
                        todos_los_chunks.append(ch)
                        todos_los_metadatas.append({
                            "materia": nombre_materia,
                            "id_materia": id_materia,
                            "archivo": nombre_archivo,
                            "chunk": c_i
                        })
            except Exception as e:
                print(f"⚠️ [DEBUG RAG] Error procesando archivo {nombre_archivo}: {e}")
                continue

        if todos_los_chunks and coleccion:
            try:
                coleccion.upsert(
                    documents=todos_los_chunks,
                    ids=todos_los_ids,
                    metadatas=todos_los_metadatas
                )
                print(f"✅ [CHROMA] Guardados {len(todos_los_chunks)} fragmentos vectoriales de {len(archivos_a_procesar)} archivo(s) en '{nombre_col}'.")
            except Exception as e:
                print(f"⚠️ [CHROMA] Error al insertar en ChromaDB: {e}")
    else:
        print(f"⚡ [CACHE CHROMA] Colección '{nombre_col}' encontrada en disco con {coleccion.count()} fragmentos. Omitiendo descarga...")

    # =========================================================================
    # DETECCIÓN DE DOCUMENTO ESPECÍFICO SOLICITADO POR EL ALUMNO
    # =========================================================================
    archivo_detectado = None
    # 1. Por referencia numérica u ordinal ("primer", "segundo", "tercer", "1", "2", "3")
    ordenes_map = {
        "primer": 0, "primero": 0, "1": 0, "uno": 0,
        "segundo": 1, "2": 1, "dos": 1,
        "tercer": 2, "tercero": 2, "3": 2, "tres": 2,
        "cuarto": 3, "4": 3, "cuatro": 3,
        "quinto": 4, "5": 4, "cinco": 4
    }
    for k_ord, idx_num in ordenes_map.items():
        if re.search(r'\b(?:el\s+|archivo\s+|documento\s+|pdf\s+|word\s+)?' + re.escape(k_ord) + r'(?:\s+archivo|\s+documento|\s+pdf|\s+word)?\b', tema_lower):
            if idx_num < len(archivos_a_procesar):
                archivo_detectado = archivos_a_procesar[idx_num]['nombre']
                break

    # 2. Por coincidencia en el nombre del archivo
    if not archivo_detectado:
        for arch in archivos_a_procesar:
            nom_arch_limpio = arch['nombre'].lower()
            nom_sin_ext = os.path.splitext(nom_arch_limpio)[0]
            if nom_arch_limpio in tema_lower or (len(nom_sin_ext) > 3 and nom_sin_ext in tema_lower):
                archivo_detectado = arch['nombre']
                break
            palabras_nom = [p for p in re.split(r'[_ \-\.]', nom_sin_ext) if len(p) > 3]
            if palabras_nom and any(p in tema_lower for p in palabras_nom):
                archivo_detectado = arch['nombre']
                break

    # Si se detectó un archivo específico, recuperamos directamente sus fragmentos
    if archivo_detectado and coleccion:
        print(f"🎯 [RAG CHROMA] Documento específico detectado para consulta: '{archivo_detectado}'")
        try:
            datos_archivo = coleccion.get(where={"archivo": archivo_detectado}, limit=6)
            docs_arch = datos_archivo.get('documents', [])
            if docs_arch:
                es_consulta_puntual = not any(k in tema_lower for k in ["resumen", "explicar", "explica", "de que trata", "sintesis"]) and tema_lower != archivo_detectado.lower()
                if es_consulta_puntual and len(docs_arch) > 3:
                    consulta_arch = coleccion.query(
                        query_texts=[tema_a_buscar],
                        where={"archivo": archivo_detectado},
                        n_results=min(4, len(docs_arch))
                    )
                    frags_arch = consulta_arch.get('documents', [[]])[0]
                    if frags_arch:
                        return f"[EXTRACTO DEL DOCUMENTO '{archivo_detectado}' (Materia: {nombre_materia})]:\n" + "\n\n---\n\n".join(frags_arch)

                return f"[CONTENIDO DEL DOCUMENTO '{archivo_detectado}' (Materia: {nombre_materia})]:\n" + "\n\n---\n\n".join(docs_arch)
        except Exception as e:
            print(f"⚠️ [RAG CHROMA] Error al consultar archivo específico en ChromaDB: {e}")

    # REGLA 5: PLAN B y Anti-Alucinaciones
    total_docs = coleccion.count() if coleccion else 0
    if total_docs == 0:
        if texto_extraido:
            return f"[APUNTE DE {nombre_materia}]:\n" + texto_extraido[:4000]
        return f"No hay contenido disponible para la materia {nombre_materia}."

    k = min(4, total_docs)
    palabras_tema = [p for p in tema_lower.split() if len(p) > 2]
    es_resumen = (
        tema_lower in ["resumen general", "resumen", "general", "todos", "apuntes", "apunte", ""]
        or any(k_w in tema_lower for k_w in ["resumen", "de que trata", "que trata", "temas", "explicacion general", "sintesis"])
        or tema_lower == nombre_materia.lower().strip()
        or (len(palabras_tema) <= 2 and any(p in nombre_materia.lower() for p in palabras_tema))
    )

    if es_resumen:
        print(f"📖 [RAG ChromaDB] Resumen general solicitado. Recuperando primeros fragmentos...")
        datos_primeros = coleccion.get(limit=k)
        docs = datos_primeros.get('documents', [])
        if docs:
            return f"[APUNTE DE {nombre_materia}]:\n" + "\n\n---\n\n".join(docs)
        if texto_extraido:
            return f"[APUNTE DE {nombre_materia}]:\n" + texto_extraido[:4000]
        return f"No se pudo extraer contenido para el resumen de {nombre_materia}."

    print(f"🔍 [RAG ChromaDB] Buscando semánticamente: '{tema_a_buscar}' en '{nombre_materia}'...")
    try:
        consulta = coleccion.query(
            query_texts=[tema_a_buscar],
            n_results=k
        )

        fragmentos = consulta.get('documents', [[]])[0]
        distancias = consulta.get('distances', [[]])[0] if 'distances' in consulta and consulta['distances'] else []
        metas = consulta.get('metadatas', [[]])[0] if 'metadatas' in consulta else []

        if not fragmentos:
            if texto_extraido:
                return f"[APUNTE DE {nombre_materia}]:\n" + texto_extraido[:4000]
            return f"Leí el archivo de {nombre_materia} pero no encontré menciones exactas sobre ese tema."

        fragmentos_relevantes = []
        for i, doc in enumerate(fragmentos):
            if distancias and i < len(distancias) and distancias[i] > 2.0:
                continue
            nombre_origen = metas[i].get('archivo', '') if i < len(metas) else ''
            prefijo = f"📄 [Archivo: {nombre_origen}]\n" if nombre_origen else ""
            fragmentos_relevantes.append(f"{prefijo}{doc}")

        # Si el filtro estricto descartó todo pero ChromaDB trajo resultados, los aprovechamos
        if not fragmentos_relevantes and fragmentos:
            for i, f in enumerate(fragmentos):
                nombre_origen = metas[i].get('archivo', '') if i < len(metas) else ''
                prefijo = f"📄 [Archivo: {nombre_origen}]\n" if nombre_origen else ""
                fragmentos_relevantes.append(f"{prefijo}{f}")

        if not fragmentos_relevantes:
            if texto_extraido:
                return f"[APUNTE DE {nombre_materia}]:\n" + texto_extraido[:4000]
            print(f"⚠️ [RAG ChromaDB] Ningún fragmento superó el umbral de similitud.")
            return f"Leí el archivo de {nombre_materia} pero no encontré menciones exactas sobre ese tema."

        return f"[RESULTADO RAG DE {nombre_materia}]:\n" + "\n\n---\n\n".join(fragmentos_relevantes)

    except Exception as e:
        print(f"❌ [RAG ERROR]: {e}")
        return f"Error en la consulta vectorial: {e}"
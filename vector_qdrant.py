import os
import uuid
from dotenv import load_dotenv

load_dotenv()

# =====================================================================
# CONFIGURACIÓN DE CONEXIÓN CON QDRANT (DEVOPS RESILIENTE)
# =====================================================================
# Si estamos dentro del contenedor Docker usa el alias 'qdrant', si es local usa 'localhost'
_default_host = "qdrant" if os.path.exists("/.dockerenv") else "localhost"
QDRANT_HOST = os.getenv("QDRANT_HOST", _default_host)
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLECCION_NAME = os.getenv("QDRANT_COLLECTION", "moodle_docs")

# Imports tolerantes a fallos para entornos de testing / aislamiento
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        VectorParams,
        PointStruct,
        Filter,
        FieldCondition,
        MatchValue
    )
except ImportError:
    QdrantClient = None
    Distance = None
    VectorParams = None
    PointStruct = None
    Filter = None
    FieldCondition = None
    MatchValue = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


# =====================================================================
# LAZY INITIALIZATION (Evita bloqueos de memoria y fallos en arranque)
# =====================================================================
_encoder_instance = None
_client_instance = None


def obtener_encoder():
    """Retorna la instancia del modelo de embeddings (all-MiniLM-L6-v2) con carga perezosa."""
    global _encoder_instance
    if _encoder_instance is None and SentenceTransformer is not None:
        try:
            _encoder_instance = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            print(f"⚠️ [QDRANT] Advertencia al cargar SentenceTransformer: {e}")
            _encoder_instance = None
    return _encoder_instance


def obtener_cliente_qdrant():
    """Retorna la instancia del cliente Qdrant asegurando tolerancia a desconexión."""
    global _client_instance
    if _client_instance is None and QdrantClient is not None:
        try:
            _client_instance = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        except Exception as e:
            print(f"⚠️ [QDRANT] No se pudo conectar a Qdrant en {QDRANT_HOST}:{QDRANT_PORT} - {e}")
            _client_instance = None
    return _client_instance


# Proxies transparentes para máxima compatibilidad con el código del dev 2
class _LazyEncoderProxy:
    def encode(self, *args, **kwargs):
        enc = obtener_encoder()
        if enc is None:
            # Fallback en caso de no tener sentence_transformers disponible
            if isinstance(args[0], list):
                return [[0.0] * 384 for _ in args[0]]
            return [0.0] * 384
        return enc.encode(*args, **kwargs)

    def __getattr__(self, name):
        enc = obtener_encoder()
        if enc is not None:
            return getattr(enc, name)
        raise AttributeError(f"SentenceTransformer no disponible (atributo {name})")


class _LazyQdrantProxy:
    def __getattr__(self, name):
        cli = obtener_cliente_qdrant()
        if cli is not None:
            return getattr(cli, name)
        raise ConnectionError(f"Cliente Qdrant no inicializado al invocar {name}")


encoder = _LazyEncoderProxy()
qdrant_client = _LazyQdrantProxy()


# =====================================================================
# MÉTODOS NATIVOS DE QDRANT PARA EL ECOSISTEMA NEXORA
# =====================================================================
def inicializar_qdrant(collection_name: str = COLECCION_NAME):
    """Crea la colección vectorial en Qdrant si no existe."""
    cli = obtener_cliente_qdrant()
    if cli is None or VectorParams is None or Distance is None:
        return
    try:
        colecciones = [c.name for c in cli.get_collections().collections]
        if collection_name not in colecciones:
            cli.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            print(f"✅ [QDRANT] Colección '{collection_name}' creada exitosamente.")
    except Exception as e:
        print(f"⚠️ [QDRANT] Error inicializando colección '{collection_name}': {e}")


def indexar_texto(texto: str, metadata: dict = None, collection_name: str = COLECCION_NAME):
    """Indexa un único texto con metadatos asociados en Qdrant."""
    cli = obtener_cliente_qdrant()
    if cli is None or PointStruct is None:
        return
    metadata = metadata or {}
    try:
        inicializar_qdrant(collection_name)
        vector = encoder.encode(texto).tolist() if hasattr(encoder.encode(texto), "tolist") else encoder.encode(texto)
        point_id = str(uuid.uuid4())
        cli.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"texto": texto, **metadata}
                )
            ]
        )
    except Exception as e:
        print(f"⚠️ [QDRANT] Error al indexar texto: {e}")


def indexar_lote(textos: list[str], metadatas: list[dict] = None, collection_name: str = COLECCION_NAME):
    """Indexa un lote de textos de forma optimizada y en una única llamada upsert."""
    cli = obtener_cliente_qdrant()
    if not textos or cli is None or PointStruct is None:
        return
    metadatas = metadatas or [{} for _ in textos]
    try:
        inicializar_qdrant(collection_name)
        vectores = encoder.encode(textos)
        if hasattr(vectores, "tolist"):
            vectores = vectores.tolist()

        puntos = []
        for t, v, m in zip(textos, vectores, metadatas):
            puntos.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=v,
                payload={"texto": t, **m}
            ))

        cli.upsert(collection_name=collection_name, points=puntos)
        print(f"✅ [QDRANT] Upsert masivo exitoso: {len(puntos)} fragmentos guardados en '{collection_name}'.")
    except Exception as e:
        print(f"⚠️ [QDRANT] Error al indexar lote en '{collection_name}': {e}")


def buscar_contexto(pregunta: str, limite: int = 3, id_materia: int = None, archivo: str = None, collection_name: str = COLECCION_NAME) -> str:
    """Busca similitud semántica en Qdrant y devuelve los textos concatenados."""
    cli = obtener_cliente_qdrant()
    if cli is None:
        return ""
    try:
        vector_pregunta = encoder.encode(pregunta)
        if hasattr(vector_pregunta, "tolist"):
            vector_pregunta = vector_pregunta.tolist()

        filtro = None
        condiciones = []
        if id_materia is not None and FieldCondition is not None and MatchValue is not None:
            condiciones.append(FieldCondition(key="id_materia", match=MatchValue(value=id_materia)))
        if archivo and FieldCondition is not None and MatchValue is not None:
            condiciones.append(FieldCondition(key="archivo", match=MatchValue(value=archivo)))
        if condiciones and Filter is not None:
            filtro = Filter(must=condiciones)

        resultados = cli.search(
            collection_name=collection_name,
            query_vector=vector_pregunta,
            query_filter=filtro,
            limit=limite
        )
        contextos = [hit.payload.get("texto", "") for hit in resultados if hit.payload and "texto" in hit.payload]
        return "\n\n".join(contextos) if contextos else ""
    except Exception as e:
        print(f"⚠️ [QDRANT] Error en buscar_contexto: {e}")
        return ""


def contar_documentos_materia(id_materia: int = None, collection_name: str = COLECCION_NAME) -> int:
    """Cuenta los fragmentos vectoriales almacenados para una materia dada o en total."""
    cli = obtener_cliente_qdrant()
    if cli is None:
        return 0
    try:
        filtro = None
        if id_materia is not None and FieldCondition is not None and MatchValue is not None and Filter is not None:
            filtro = Filter(must=[FieldCondition(key="id_materia", match=MatchValue(value=id_materia))])
        
        conteo = cli.count(collection_name=collection_name, count_filter=filtro)
        return conteo.count
    except Exception:
        return 0


def recuperar_documentos_archivo(nombre_archivo: str, limite: int = 6, collection_name: str = COLECCION_NAME) -> list[str]:
    """Recupera los fragmentos pertenecientes a un archivo específico en Qdrant."""
    cli = obtener_cliente_qdrant()
    if cli is None or Filter is None or FieldCondition is None or MatchValue is None:
        return []
    try:
        filtro = Filter(must=[FieldCondition(key="archivo", match=MatchValue(value=nombre_archivo))])
        puntos, _ = cli.scroll(
            collection_name=collection_name,
            scroll_filter=filtro,
            limit=limite,
            with_payload=True
        )
        return [p.payload.get("texto", "") for p in puntos if p.payload and "texto" in p.payload]
    except Exception as e:
        print(f"⚠️ [QDRANT] Error recuperando documento '{nombre_archivo}': {e}")
        return []


def recuperar_primeros_documentos(id_materia: int = None, limite: int = 4, collection_name: str = COLECCION_NAME) -> list[str]:
    """Recupera los primeros fragmentos almacenados de una materia para resúmenes generales."""
    cli = obtener_cliente_qdrant()
    if cli is None:
        return []
    try:
        filtro = None
        if id_materia is not None and Filter is not None and FieldCondition is not None and MatchValue is not None:
            filtro = Filter(must=[FieldCondition(key="id_materia", match=MatchValue(value=id_materia))])
        
        puntos, _ = cli.scroll(
            collection_name=collection_name,
            scroll_filter=filtro,
            limit=limite,
            with_payload=True
        )
        return [p.payload.get("texto", "") for p in puntos if p.payload and "texto" in p.payload]
    except Exception as e:
        print(f"⚠️ [QDRANT] Error recuperando primeros documentos: {e}")
        return []


def buscar_puntos_semanticos(pregunta: str, limite: int = 4, id_materia: int = None, collection_name: str = COLECCION_NAME) -> list[dict]:
    """Realiza una búsqueda semántica detallada retornando texto, archivo de origen y score."""
    cli = obtener_cliente_qdrant()
    if cli is None:
        return []
    try:
        vector_pregunta = encoder.encode(pregunta)
        if hasattr(vector_pregunta, "tolist"):
            vector_pregunta = vector_pregunta.tolist()

        filtro = None
        if id_materia is not None and Filter is not None and FieldCondition is not None and MatchValue is not None:
            filtro = Filter(must=[FieldCondition(key="id_materia", match=MatchValue(value=id_materia))])

        resultados = cli.search(
            collection_name=collection_name,
            query_vector=vector_pregunta,
            query_filter=filtro,
            limit=limite
        )

        salida = []
        for hit in resultados:
            if not hit.payload:
                continue
            salida.append({
                "texto": hit.payload.get("texto", ""),
                "archivo": hit.payload.get("archivo", ""),
                "materia": hit.payload.get("materia", ""),
                "score": hit.score
            })
        return salida
    except Exception as e:
        print(f"⚠️ [QDRANT] Error en búsqueda semántica: {e}")
        return []

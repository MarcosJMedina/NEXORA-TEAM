from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLECCION_NAME = "moodle_docs"

# Carga modelo ligero de embeddings
encoder = SentenceTransformer("all-MiniLM-L6-v2")
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

def inicializar_qdrant():
    collections = [c.name for c in qdrant_client.get_collections().collections]
    if COLECCION_NAME not in collections:
        qdrant_client.create_collection(
            collection_name=COLECCION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )

def indexar_texto(texto: str, metadata: dict):
    vector = encoder.encode(texto).tolist()
    point_id = str(uuid.uuid4())
    qdrant_client.upsert(
        collection_name=COLECCION_NAME,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload={"texto": texto, **metadata}
            )
        ]
    )

def buscar_contexto(pregunta: str, limite: int = 3) -> str:
    vector_pregunta = encoder.encode(pregunta).tolist()
    resultados = qdrant_client.search(
        collection_name=COLECCION_NAME,
        query_vector=vector_pregunta,
        limit=limite
    )
    contextos = [hit.payload["texto"] for hit in resultados]
    return "\n\n".join(contextos) if contextos else ""
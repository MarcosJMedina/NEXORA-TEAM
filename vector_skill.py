from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

DIRECTORIO_CHROMA = "./chroma_db"

def buscar_contexto(pregunta: str, k: int = 3) -> str:
    """Busca en ChromaDB los k fragmentos de texto más similares a la pregunta."""
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    
    # Cargar la base vectorial guardada
    vectorstore = Chroma(
        persist_directory=DIRECTORIO_CHROMA,
        embedding_function=embeddings
    )
    
    # Búsqueda por similitud
    resultados = vectorstore.similarity_search(pregunta, k=k)
    
    if not resultados:
        return "No se encontró información relevante en los PDFs."

    # Unir los textos encontrados
    contexto = "\n\n".join([doc.page_content for doc in resultados])
    return contexto
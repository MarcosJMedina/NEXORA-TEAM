import os
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from vector_qdrant import inicializar_qdrant, indexar_texto

CARPETA_PDFS = "./moodles_pdfs"

def procesar_pdfs():
    inicializar_qdrant()
    if not os.path.exists(CARPETA_PDFS):
        os.makedirs(CARPETA_PDFS)
        print("Carpeta ./moodles_pdfs creada. Agrega PDFs aquí.")
        return

    loader = PyPDFDirectoryLoader(CARPETA_PDFS)
    documentos = loader.load()

    if not documentos:
        print("No se encontraron PDFs.")
        return

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    fragmentos = splitter.split_documents(documentos)

    for frag in fragmentos:
        indexar_texto(frag.page_content, {"fuente": frag.metadata.get("source", "moodle")})

    print(f"Indexados {len(fragmentos)} fragmentos en Qdrant.")

if __name__ == "__main__":
    procesar_pdfs()
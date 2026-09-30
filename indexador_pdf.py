import os
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

CARPETA_PDFS = "./moodle_pdfs"
DIRECTORIO_CHROMA = "./chroma_db"

def procesar_pdfs():
    print("🔍 Cargando archivos PDF desde ./moodle_pdfs...")
    if not os.path.exists(CARPETA_PDFS):
        os.makedirs(CARPETA_PDFS)
        print("⚠️ Se creó la carpeta ./moodle_pdfs. Pon tus archivos PDF ahí.")
        return

    loader = PyPDFDirectoryLoader(CARPETA_PDFS)
    documentos = loader.load()

    if not documentos:
        print("⚠️ No se encontraron archivos PDF dentro de ./moodle_pdfs")
        return

    print(f"📄 Se cargaron {len(documentos)} páginas de PDF. Fragmentando texto...")
    
    # Divide el texto en partes de 1000 caracteres con 150 de solapamiento
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    fragmentos = splitter.split_documents(documentos)

    print(f"🧩 Generando vectores con Ollama para {len(fragmentos)} fragmentos...")
    embeddings = OllamaEmbeddings(model="nomic-embed-text")

    # Guarda los vectores directamente en el disco duro dentro de ./chroma_db
    vectorstore = Chroma.from_documents(
        documents=fragmentos,
        embedding=embeddings,
        persist_directory=DIRECTORIO_CHROMA
    )
    print("✅ ¡Éxito! La base de datos vectorial ChromaDB ha sido creada/actualizada.")

if __name__ == "__main__":
    procesar_pdfs()
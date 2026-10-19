from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import requests
import os
from dotenv import load_dotenv

from database import inicializar_bd, sincronizar_usuario, obtener_rol_usuario, obtener_conexion
from vector_qdrant import inicializar_qdrant, buscar_contexto
from moodle_service import validar_token_moodle

load_dotenv()

app = FastAPI(title="Nexora AI Web API")
NGROK_LLM_URL = os.getenv("NGROK_LLM_URL", "")

class ConsultaRequest(BaseModel):
    id_moodle: int
    pregunta: str

@app.on_event("startup")
def startup():
    try:
        inicializar_bd()
        inicializar_qdrant()
        print("Base de datos e IA inicializadas correctamente.")
    except Exception as e:
        print(f"Advertencia durante el inicio: {e}")

def llamar_ngrok_llm(prompt: str) -> str:
    url = f"{NGROK_LLM_URL}/v1/chat/completions"
    payload = {
        "model": "grok-or-llama",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    headers = {"Content-Type": "application/json"}
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error conectando a la API de Ngrok: {e}"
    return "No se pudo obtener respuesta del modelo remoto."

@app.post("/api/chat")
def chat(req: ConsultaRequest, wstoken: str = Header(None)):
    # 1. Validar Roles
    rol = obtener_rol_usuario(req.id_moodle)
    if rol == "bloqueado":
        return {"respuesta": "Tu rol actual no tiene acceso al bot.", "tokens_consumidos": 0}

    pregunta_limpia = req.pregunta.lower().strip()

    # 2. Respuestas inmediatas (0 TOKENS)
    if pregunta_limpia in ["hola", "buenos dias", "buenas tardes", "chau", "gracias"]:
        return {
            "respuesta": "¡Hola! Soy la IA de Nexora. ¿En qué puedo ayudarte hoy?",
            "tokens_consumidos": 0
        }

    # 3. Búsqueda Vectorial en Qdrant (0 TOKENS)
    contexto = buscar_contexto(req.pregunta)

    # 4. Invocación al LLM remoto vía Ngrok (Consume tokens solo aquí)
    prompt = f"""
    Eres el asistente oficial del instituto. Responde la duda del usuario basándote únicamente en el contexto:
    --- CONTEXTO ---
    {contexto}
    ---------------
    Pregunta: {req.pregunta}
    """

    respuesta_ia = llamar_ngrok_llm(prompt)
    tokens = len(prompt.split())

    # 5. Guardar en MariaDB
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO historial_chat (id_moodle, pregunta, respuesta, tokens_consumidos) VALUES (%s, %s, %s, %s)",
                (req.id_moodle, req.pregunta, respuesta_ia, tokens)
            )
        conn.close()
    except Exception as e:
        print(f"Error guardando historial: {e}")

    return {
        "respuesta": respuesta_ia,
        "tokens_consumidos": tokens
    }
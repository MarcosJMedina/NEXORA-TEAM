from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# IMPORTAMOS A TUS AGENTES DESDE EL OTRO ARCHIVO
from bot_crewai import consultar_oficina 

app = FastAPI()

# Permite que tu archivo HTML (Front-End) hable con este servidor de Python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Esto define qué datos obligatorios llegan desde el Front-End
class ChatRequest(BaseModel):
    user_id: int
    course_id: int
    message: str

# Esta es la "dirección" (Endpoint) que recibirá tus mensajes
@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    print(f"\n==============================================")
    print(f"📩 NUEVO MENSAJE DESDE EL FRONTEND: {request.message}")
    print(f"==============================================\n")
    
    try:
        # AQUÍ OCURRE LA MAGIA: Le pasamos el mensaje a tus agentes
        resultado_agentes = consultar_oficina(request.message)
        
        # CrewAI a veces devuelve un objeto complejo, lo convertimos a texto por seguridad
        bot_response = str(resultado_agentes) 
        
    except Exception as e:
        print(f"❌ [ERROR EN EL SERVIDOR]: {e}")
        bot_response = "Disculpa, mis agentes están teniendo problemas técnicos en este momento."
        
    # Python devuelve la respuesta en un paquete JSON al JavaScript
    return {
        "success": True,
        "response": bot_response
    }

if __name__ == "__main__":
    print("🚀 Iniciando Servidor de Agentes en http://127.0.0.1:3000")
    uvicorn.run(app, host="127.0.0.1", port=3000)
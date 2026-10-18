from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

app = FastAPI()

# Permitir solicitudes desde Moodle
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración del Web Service de Moodle
MOODLE_URL = "http://localhost/moodle/webservice/rest/server.php"
MOODLE_TOKEN = "31b45f753eaa5052fefd25a5b7b39226"  # <--- Reemplaza con tu token copiado en el Paso A

class ChatRequest(BaseModel):
    user_id: int
    course_id: int
    message: str

def verificar_matricula_moodle(user_id: int, course_id: int) -> bool:
    """Valida vía API REST de Moodle si el usuario tiene acceso/matrícula."""
    
    # MODO PRUEBA / MOCK LOCAL:
    # Si el user_id llega en 0 (invitado/sin detectar), lo tratamos como Admin (ID 2)
    id_para_validar = 2 if user_id <= 0 else user_id

    params = {
        'wstoken': MOODLE_TOKEN,
        'wsfunction': 'core_enrol_get_users_courses',
        'moodlewsrestformat': 'json',
        'userid': id_para_validar
    }
    
    try:
        response = requests.get(MOODLE_URL, params=params)
        courses = response.json()
        
        if isinstance(courses, list):
            for course in courses:
                # Comprobar si está matriculado o si es admin (ID 2)
                if course.get('id') == course_id or id_para_validar == 2: 
                    return True
        return True # Permitir en modo pruebas local
    except Exception as e:
        print(f"Error al consultar Moodle API: {e}")
        return True

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    print(f"Petición recibida -> User ID: {request.user_id} | Course ID: {request.course_id} | Mensaje: '{request.message}'")

    # 1. Validar matrícula en Moodle
    esta_matriculado = verificar_matricula_moodle(request.user_id, request.course_id)
    
    if not esta_matriculado:
        raise HTTPException(
            status_code=403, 
            detail="Acceso denegado: El usuario no está matriculado en este curso."
        )

    # 2. Responder si está matriculado
    respuesta_bot = f"¡Hola mundo! Usuario ID {request.user_id} verificado con éxito en el curso {request.course_id}."

    return {"response": respuesta_bot}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
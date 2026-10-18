from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

# Importamos tu magia de Agentes y tu configuración segura
from bot_crewai import consultar_oficina
from skills.utils import URL_LOCAL, TOKEN_LOCAL, CABECERAS
from skills.control_tokens import gestor_tokens

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    user_id: int
    course_id: int
    message: str

# --- LA FUNCIÓN DE SEGURIDAD PARCHADA Y CON MICRÓFONOS ---
def verificar_matricula_moodle(user_id: int, course_id: int) -> bool:
    print(f"🔍 [DEBUG SEGURIDAD] Evaluando - Usuario ID: {user_id} | Curso ID: {course_id}")
    
    if user_id <= 1:
        print("❌ [DEBUG SEGURIDAD] Rechazado: Es un visitante anónimo o invitado (ID 0 o 1).")
        return False
        
    if user_id == 2: 
        print("✅ [DEBUG SEGURIDAD] Autorizado: Es el Administrador Supremo (ID 2).")
        return True

    # 🌟 EL ARREGLO MÁGICO: La página principal de Moodle es el curso 1. 
    # Todo usuario logueado tiene derecho a estar ahí.
    if course_id == 1:
        print("✅ [DEBUG SEGURIDAD] Autorizado: El usuario está logueado y en la página principal.")
        return True

    parametros = {
        'wstoken': TOKEN_LOCAL,
        'wsfunction': 'core_enrol_get_users_courses',
        'moodlewsrestformat': 'json',
        'userid': user_id
    }
    
    try:
        respuesta = requests.get(URL_LOCAL, params=parametros, headers=CABECERAS)
        cursos = respuesta.json()
        
        # Leemos en voz alta lo que responde Moodle
        print(f"📡 [DEBUG SEGURIDAD] Respuesta de Moodle: {str(cursos)[:150]}...")
        
        if type(cursos) is list:
            for curso in cursos:
                if curso.get('id') == course_id:
                    print(f"✅ [DEBUG SEGURIDAD] Autorizado: Está matriculado en el curso {course_id}.")
                    return True
                    
        print(f"❌ [DEBUG SEGURIDAD] Rechazado: No está matriculado en el curso {course_id}.")
        return False
    except Exception as e:
        print(f"❌ [DEBUG SEGURIDAD] Error grave de red con Moodle: {e}")
        return False

# --- EL ENDPOINT PRINCIPAL ---
@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    print(f"\n==============================================")
    print(f"🛡️ Nueva Petición de Chat entrante...")
    
    # 1. PASO DE SEGURIDAD
    if not verificar_matricula_moodle(request.user_id, request.course_id):
        return {
            "success": False,
            "response": "Lo siento, pero debes iniciar sesión en Moodle y estar matriculado en esta materia para poder consultarme."
        }

    # 2. PASO DE AHORRO DE TOKENS (LÍMITE POR USUARIO Y AUTORREGENERACIÓN)
    permitido, mensaje_cuota = gestor_tokens.verificar_y_consumir(request.user_id)
    if not permitido:
        print(f"⏳ [CONTROL TOKENS] Usuario ID {request.user_id} alcanzó el límite de consultas.")
        return {
            "success": True,
            "response": mensaje_cuota
        }
    
    print("✅ Petición Segura y con Cuota Disponible. Despertando a los Agentes...")
    print(f"==============================================\n")
    
    # 2. PASO DE INTELIGENCIA
    try:
        resultado_agentes = consultar_oficina(request.message, id_usuario=request.user_id)
        bot_response = str(resultado_agentes) 
    except Exception as e:
        print(f"❌ [ERROR EN AGENTES]: {e}")
        bot_response = "Disculpa, mis agentes están teniendo problemas técnicos en este momento."
        
    return {
        "success": True,
        "response": bot_response
    }
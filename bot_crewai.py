import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM

# El parche de caché para Groq
import crewai.llms.cache as _crewai_cache
_crewai_cache.mark_cache_breakpoint = lambda msg: msg

# =================================================================
# IMPORTAMOS LAS SKILLS DESDE NUESTRA NUEVA CARPETA MODULAR
# =================================================================
from skills.calendario import tool_calendario
from skills.archivos import tool_archivos

load_dotenv()
historial_chats = {}

# =================================================================
# CONFIGURACIÓN DE LOS AGENTES
# =================================================================
modelo_ia = "groq/openai/gpt-oss-20b"
ia_orquestador = LLM(model=modelo_ia, api_key=os.getenv("GROQ_API_KEY_ERICK"))
ia_archivos = LLM(model=modelo_ia, api_key=os.getenv("GROQ_API_KEY_AMIGO1"))
ia_calendario = LLM(model=modelo_ia, api_key=os.getenv("GROQ_API_KEY_AMIGO2"))

agente_orquestador = Agent(
    role="Asistente Principal y Rostro de la Universidad",
    goal="Clasificar las intenciones del alumno y ser el ÚNICO que habla directamente con él.",
    backstory="Sos el asistente virtual principal de Moodle. Eres empático, amable y pedagógico. Derivas búsquedas a tus colegas, pero TÚ te encargas de redactar la respuesta bonita al alumno.",
    verbose=True, allow_delegation=False, llm=ia_orquestador
)

agente_calendario = Agent(
    role="Investigador de Fechas (Backoffice)",
    goal="Buscar fechas en el calendario y entregar datos crudos.",
    backstory="Sos una máquina de buscar fechas. NO HABLAS CON EL ALUMNO. Usas tu tool_calendario para extraer la info.",
    verbose=True, allow_delegation=False, llm=ia_calendario, tools=[tool_calendario]
)

agente_archivos = Agent(
    role="Analista de Apuntes (Backoffice)",
    goal="Buscar, leer y resumir apuntes de las materias y entregar datos crudos.",
    backstory="Sos un ratón de biblioteca. NO HABLAS CON EL ALUMNO. Usas tu tool_archivos para leer PDFs y devolver el texto puro.",
    verbose=True, allow_delegation=False, llm=ia_archivos, tools=[tool_archivos]
)

# =================================================================
# LÓGICA PRINCIPAL (PIPELINE)
# =================================================================
def consultar_oficina(mensaje_alumno, id_usuario=4501):
    print(f"\n👤 Alumno {id_usuario}: '{mensaje_alumno}'")
    
    if id_usuario not in historial_chats:
        historial_chats[id_usuario] = []
    
    memoria_texto = "\n".join(historial_chats[id_usuario][-6:])
    if not memoria_texto: memoria_texto = "Esta es la primera interacción."

    # PASO 1: ORQUESTADOR CLASIFICA
    tarea_clasificacion = Task(
        description=f"""
        Historial de la charla: {memoria_texto}
        Mensaje NUEVO: "{mensaje_alumno}"
        
        Elige UNA opción:
        - "CALENDARIO": Pide fechas/exámenes Y menciona una materia.
        - "ARCHIVOS": Pide resúmenes/apuntes Y menciona una materia.
        - "CHARLA": Saluda, charla o pide ayuda pero NO MENCIONA la materia.
        
        REGLA: Si no menciona una materia exacta, elige CHARLA|Ninguna.
        Responde ÚNICAMENTE: ACCION|MATERIA
        """,
        expected_output="ACCION|MATERIA",
        agent=agente_orquestador
    )

    oficina_recepcion = Crew(agents=[agente_orquestador], tasks=[tarea_clasificacion], verbose=True, cache=False)
    decision_raw = str(oficina_recepcion.kickoff()).strip()
    
    try:
        accion, materia = decision_raw.split('|')
    except ValueError:
        accion, materia = "CHARLA", "Ninguna"

    accion = accion.strip().upper()
    materia = materia.strip()
    if materia.lower() in ["ninguna", "ninguno", "no menciona", ""]: accion = "CHARLA"

    # PASO 2: PIPELINE DE TRABAJO
    tareas_finales = []
    agentes_involucrados = [agente_orquestador]

    if accion == "CALENDARIO":
        tareas_finales.append(Task(
            description=f"Busca fechas para '{materia}'. Extrae los datos crudos, no saludes.",
            expected_output="Fechas o aviso de que no hay.", agent=agente_calendario
        ))
        agentes_involucrados.insert(0, agente_calendario)
        
    elif accion == "ARCHIVOS":
        tareas_finales.append(Task(
            description=f"Lee apuntes de '{materia}'. Busca sobre: '{mensaje_alumno}'. Entrega resumen crudo, no saludes.",
            expected_output="Datos extraídos del PDF.", agent=agente_archivos
        ))
        agentes_involucrados.insert(0, agente_archivos)

    # PASO 3: RESPUESTA FINAL
    tareas_finales.append(Task(
        description=f"""
        Historial: {memoria_texto}
        Mensaje ACTUAL: "{mensaje_alumno}"
        
        1. TÚ ERES EL ÚNICO que habla con el alumno. Usa la info buscada por tus colegas para redactar la respuesta.
        2. Si no hubo búsqueda, responde empáticamente.
        
        🚨 REGLA ESTRICTA 🚨: Si el alumno habla de temas NO ACADÉMICOS (deportes, recetas, etc.), TIENES PROHIBIDO seguirle la corriente. Niégate cortésmente.
        """,
        expected_output="Respuesta pedagógica y segura.",
        agent=agente_orquestador
    ))

    oficina_respuesta = Crew(agents=agentes_involucrados, tasks=tareas_finales, verbose=True, cache=False)
    resultado = str(oficina_respuesta.kickoff())
    
    historial_chats[id_usuario].append(f"Alumno: {mensaje_alumno}")
    historial_chats[id_usuario].append(f"Tú: {resultado}")
    return resultado
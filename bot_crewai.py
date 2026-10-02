import os
import json
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM

# El parche de caché para Groq
import crewai.llms.cache as _crewai_cache
_crewai_cache.mark_cache_breakpoint = lambda msg: msg

# =================================================================
# 1. CARGAMOS EL PANEL DE CONTROL DEL CLIENTE (Módulo 1)
# =================================================================
path_config = os.path.join(os.path.dirname(__file__), "config.json")
if os.path.exists(path_config):
    with open(path_config, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    config = {"skills": {"calendario": {"enabled": True}, "archivos": {"enabled": True}}}

usar_calendario = config.get("skills", {}).get("calendario", {}).get("enabled", True)
usar_archivos = config.get("skills", {}).get("archivos", {}).get("enabled", True)

# =================================================================
# 2. IMPORTAMOS LAS SKILLS SEGÚN EL JSON
# =================================================================
tools_calendario = []
if usar_calendario:
    from skills.calendario import tool_calendario
    tools_calendario = [tool_calendario]

tools_archivos = []
if usar_archivos:
    from skills.archivos import tool_archivos
    tools_archivos = [tool_archivos]

load_dotenv()
historial_chats = {}

# =================================================================
# 3. CONFIGURACIÓN DE LOS AGENTES (Con tu Proxy DevOps - Módulo 2)
# =================================================================
# Nos conectamos a tu infraestructura Docker
cerebro_maestro = LLM(
    model="openai/modelo-universidad", 
    api_key="sk-llave-maestra-universidad",
    base_url="http://litellm-proxy:4000"
)

agente_orquestador = Agent(
    role="Asistente Principal y Rostro de la Universidad",
    goal="Clasificar las intenciones del alumno y ser el ÚNICO que habla directamente con él.",
    backstory="Sos el asistente virtual principal de Moodle. Eres empático, amable y pedagógico. Derivas búsquedas a tus colegas, pero TÚ te encargas de redactar la respuesta bonita al alumno.",
    verbose=True, allow_delegation=False, llm=cerebro_maestro
)

agente_calendario = Agent(
    role="Investigador de Fechas (Backoffice)",
    goal="Buscar fechas en el calendario y entregar datos crudos.",
    backstory="Sos una máquina de buscar fechas. NO HABLAS CON EL ALUMNO. Usas tu tool_calendario para extraer la info.",
    verbose=True, allow_delegation=False, llm=cerebro_maestro, 
    tools=tools_calendario # El bot solo recibe la herramienta si el JSON dice "True"
)

agente_archivos = Agent(
    role="Analista de Apuntes (Backoffice)",
    goal="Buscar, leer y resumir apuntes de las materias y entregar datos crudos.",
    backstory="Sos un ratón de biblioteca. NO HABLAS CON EL ALUMNO. Usas tu tool_archivos para leer PDFs y devolver el texto puro.",
    verbose=True, allow_delegation=False, llm=cerebro_maestro, 
    tools=tools_archivos # El bot solo recibe la herramienta si el JSON dice "True"
)

# =================================================================
# 4. LÓGICA PRINCIPAL (PIPELINE)
# =================================================================
def consultar_oficina(mensaje_alumno, id_usuario=4501):
    print(f"\n👤 Alumno {id_usuario}: '{mensaje_alumno}'")
    
    if id_usuario not in historial_chats:
        historial_chats[id_usuario] = []
    
    memoria_texto = "\n".join(historial_chats[id_usuario][-6:])
    if not memoria_texto: memoria_texto = "Esta es la primera interacción."

    # --- ARMAMOS LAS OPCIONES DEL ORQUESTADOR DINÁMICAMENTE ---
    opciones_prompt = '- "CHARLA": Saluda, charla o pide ayuda pero NO MENCIONA la materia.\n'
    if usar_calendario:
        opciones_prompt += '        - "CALENDARIO": Pide fechas/exámenes Y menciona una materia.\n'
    if usar_archivos:
        opciones_prompt += '        - "ARCHIVOS": Pide resúmenes/apuntes Y menciona una materia.\n'

    # PASO 1: ORQUESTADOR CLASIFICA
    tarea_clasificacion = Task(
        description=f"""
        Historial de la charla: {memoria_texto}
        Mensaje NUEVO: "{mensaje_alumno}"
        
        Elige UNA opción:
        {opciones_prompt}
        
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

    if accion == "CALENDARIO" and usar_calendario:
        tareas_finales.append(Task(
            description=f"Busca fechas para '{materia}'. Extrae los datos crudos, no saludes.",
            expected_output="Fechas o aviso de que no hay.", agent=agente_calendario
        ))
        agentes_involucrados.insert(0, agente_calendario)
        
    elif accion == "ARCHIVOS" and usar_archivos:
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
        2. LEE EL HISTORIAL: Si ya saludaste al alumno, TIENES PROHIBIDO volver a decirle "Hola".
        3. Si no hubo búsqueda, responde empáticamente.
        
        🚨 REGLA ESTRICTA 🚨: Si el alumno habla de temas NO ACADÉMICOS, niégate cortésmente.
        """,
        expected_output="Respuesta pedagógica y segura.",
        agent=agente_orquestador
    ))

    oficina_respuesta = Crew(agents=agentes_involucrados, tasks=tareas_finales, verbose=True, cache=False)
    resultado = str(oficina_respuesta.kickoff())
    
    historial_chats[id_usuario].append(f"Alumno: {mensaje_alumno}")
    historial_chats[id_usuario].append(f"Tú: {resultado}")
    return resultado
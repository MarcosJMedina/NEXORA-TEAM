import os
import sys
import json

# Compatibilidad de codificación UTF-8 para consola en Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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
    from skills.archivos import tool_archivos, tool_listar_archivos
    tools_archivos = [tool_archivos, tool_listar_archivos]

load_dotenv()
historial_chats = {}

# =================================================================
# 3. CONFIGURACIÓN DE LOS AGENTES (Con tu Proxy DevOps y Anti-Alucinaciones)
# =================================================================
PROXY_URL = os.getenv("LITELLM_PROXY_URL", "http://litellm-proxy:4000")
MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "sk-llave-maestra-universidad")
MODELO_UNIVERSIDAD = "openai/modelo-universidad"

# Nos conectamos a tu infraestructura Docker con temperatura estricta a cero
cerebro_maestro = LLM(
    model=MODELO_UNIVERSIDAD, 
    api_key=MASTER_KEY,
    base_url=PROXY_URL,
    temperature=0.0
)

# Aliases semánticos para compatibilidad con suites de pruebas unitarias
ia_orquestador = cerebro_maestro
ia_archivos = cerebro_maestro
ia_calendario = cerebro_maestro

agente_orquestador = Agent(
    role="Asistente Principal y Rostro de la Universidad",
    goal="Clasificar las intenciones del alumno y responder con total fidelidad a los datos de Moodle sin alucinar ni inventar información.",
    backstory="Sos el asistente virtual principal de Moodle. Eres empático, amable y pedagógico. "
              "Derivas búsquedas a tus colegas de backoffice y TÚ te encargas de redactar la respuesta final al alumno. "
              "BARRERA ANTI-ALUCINACIONES: Tu conocimiento se restringe rigurosamente a lo que tus colegas extraigan de Moodle. "
              "Si una información no está presente en los apuntes o el calendario, JAMÁS debes inventarla ni asumir respuestas. "
              "Admites con honestidad y amabilidad cuando un dato no se encuentra en el material oficial.",
    verbose=True, allow_delegation=False, llm=cerebro_maestro
)

agente_calendario = Agent(
    role="Investigador de Fechas (Backoffice)",
    goal="Buscar fechas en el calendario de Moodle y entregar datos fidedignos sin suposiciones.",
    backstory="Sos una máquina de buscar fechas en Moodle. NO HABLAS CON EL ALUMNO. Usas tu tool_calendario para extraer la info. "
              "Reportas estrictamente los eventos encontrados. Si no hay eventos, lo informas con exactitud sin inventar fechas aproximadas ni plazos hipotéticos.",
    verbose=True, allow_delegation=False, llm=cerebro_maestro, 
    tools=tools_calendario # El bot solo recibe la herramienta si el JSON dice "True"
)

agente_archivos = Agent(
    role="Analista de Apuntes y Documentos (Backoffice)",
    goal="Listar archivos y buscar, leer y resumir apuntes de las materias entregando información fidedigna y estrictamente anclada al texto de los documentos, con cero tolerancia a la invención de datos.",
    backstory="Sos un analista documental riguroso. NO HABLAS CON EL ALUMNO. Usas tu tool_listar_archivos para consultar qué documentos existen en Moodle, y tool_archivos para leer PDFs o DOCX de Moodle y devolver el texto puro. "
              "BARRERA ANTI-ALUCINACIONES: Te ciñes exclusivamente al texto extraído del documento. "
              "Tienes terminantemente prohibido suponer, extrapolar o inventar información que no esté explícitamente escrita en los apuntes. ",
              
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
        opciones_prompt += '        - "ARCHIVOS": Pide listar/nombrar archivos, o pide resúmenes, explicaciones de temas, PDFs o Words específicos Y menciona una materia (o continúa la materia del historial).\n'

    # PASO 1: ORQUESTADOR CLASIFICA
    tarea_clasificacion = Task(
        description=f"""
        Historial de la charla: {memoria_texto}
        Mensaje NUEVO: "{mensaje_alumno}"
        
        Elige UNA opción:
        {opciones_prompt}
        
        REGLA 1 (MEMORIA DE MATERIA): Si el mensaje menciona una materia, extrae esa materia. Si el mensaje NO menciona la materia pero el alumno está pidiendo nombrar, resumir o explicar un archivo/apunte de la materia de la que se venía hablando en el historial reciente, MANTÉN esa materia del historial. Si no hay materia identificable en el mensaje ni en el historial, elige CHARLA|Ninguna.
        REGLA 2 (EXTRACCIÓN LIMPIA): Al extraer la MATERIA, extrae SOLO las palabras clave principales, eliminando artículos o frases extrañas. Ejemplo: Si el mensaje es 'dame el pdf de la materia de sistemas operativos', la MATERIA debe ser 'sistemas operativos'.
        
        Responde ÚNICAMENTE: ACCION|MATERIA
        """,
        expected_output="ACCION|MATERIA",
        agent=agente_orquestador
    )

    oficina_recepcion = Crew(agents=[agente_orquestador], tasks=[tarea_clasificacion], verbose=True, cache=False)
    decision_raw = str(oficina_recepcion.kickoff()).strip()
    
    # 1. Parseo ultra-robusto de decision_raw
    accion = "CHARLA"
    materia = "Ninguna"

    import re
    if '|' in decision_raw:
        partes = [p.strip() for p in decision_raw.split('|') if p.strip()]
        if len(partes) >= 2:
            accion = partes[0].upper()
            materia = partes[1].split('\n')[0].strip()
    else:
        match = re.search(r'\b(CALENDARIO|ARCHIVOS|CHARLA)\b', decision_raw, re.IGNORECASE)
        if match:
            accion = match.group(1).upper()
            resto = decision_raw[match.end():].strip().lstrip(':|- ')
            if resto:
                materia = resto.split('\n')[0].strip()

    for opc in ["CALENDARIO", "ARCHIVOS", "CHARLA"]:
        if opc in accion:
            accion = opc
            break

    # 2. Respaldo Semántico Inteligente: Si el clasificador no detectó la materia o tuvo un fallo de formato
    materias_conocidas = [
        "practica profesionalizante", "probabilidad y estadisticas",
        "sistemas operativos", "programacion 1", "ingles tecnico",
        "bases de datos", "base de datos", "programacion",
        "probabilidad", "estadistica", "ingles"
    ]
    mensaje_norm = mensaje_alumno.lower()

    if materia.lower() in ["ninguna", "ninguno", "no menciona", "", "accion"]:
        for mat in materias_conocidas:
            if mat in mensaje_norm:
                materia = mat
                break

    # Si aún no hay materia, buscar en el historial reciente
    if materia.lower() in ["ninguna", "ninguno", "no menciona", "", "accion"]:
        for linea_h in reversed(historial_chats.get(id_usuario, [])):
            for mat in materias_conocidas:
                if mat in linea_h.lower():
                    materia = mat
                    break
            if materia.lower() not in ["ninguna", "ninguno", "no menciona", ""]:
                break

    # Determinar acción si hay materia válida identificada
    if materia.lower() not in ["ninguna", "ninguno", "no menciona", ""]:
        if any(p in mensaje_norm for p in ["examen", "fecha", "parcial", "final", "entrega", "cuando", "calendario"]):
            accion = "CALENDARIO"
        elif accion == "CHARLA":
            accion = "ARCHIVOS"
    else:
        accion = "CHARLA"

    # =================================================================
    # BARRERA DE PERMISOS Y FEATURE FLAGS DINÁMICAS (Módulo 1 + Módulo 4)
    # =================================================================
    if accion in ["CALENDARIO", "ARCHIVOS"]:
        # 1. Validación de Feature Flag (config.json)
        skill_activa = (accion == "CALENDARIO" and usar_calendario) or (accion == "ARCHIVOS" and usar_archivos)
        if not skill_activa:
            servicio = "el calendario de eventos" if accion == "CALENDARIO" else "la consulta de apuntes y archivos"
            respuesta_flag = (
                f"Disculpa, pero el servicio de {servicio} se encuentra temporalmente "
                f"deshabilitado por la administración universitaria."
            )
            historial_chats[id_usuario].append(f"Alumno: {mensaje_alumno}")
            historial_chats[id_usuario].append(f"Tú: {respuesta_flag}")
            return respuesta_flag

        # 2. Validación de Matrícula del Alumno en la Materia Consultada (Seguridad Semántica)
        if id_usuario > 2:
            from skills.utils import buscar_id_materia, verificar_usuario_en_materia
            id_materia_consultada = buscar_id_materia(materia)
            if id_materia_consultada and not verificar_usuario_en_materia(id_usuario, id_materia_consultada):
                respuesta_no_acceso = (
                    f"No tienes acceso a los contenidos de '{materia}' "
                    f"porque no estás matriculado en dicha materia."
                )
                historial_chats[id_usuario].append(f"Alumno: {mensaje_alumno}")
                historial_chats[id_usuario].append(f"Tú: {respuesta_no_acceso}")
                return respuesta_no_acceso

    # PASO 2: RECUPERACIÓN DIRECTA DE DATOS Y CONSTRUCCIÓN DEL CONTEXTO
    info_recuperada = ""
    tareas_finales = []
    agentes_involucrados = [agente_orquestador]

    if accion == "CALENDARIO" and usar_calendario:
        try:
            from skills.calendario import tool_calendario
            info_recuperada = tool_calendario(materia)
        except Exception as e:
            info_recuperada = f"Aviso de calendario: No se encontraron eventos para {materia} ({e})."

        tareas_finales.append(Task(
            description=f"Busca fechas de exámenes y entregas para '{materia}'. "
                        f"DATOS OFICIALES DE MOODLE:\n\"\"\"\n{info_recuperada}\n\"\"\"\n"
                        f"Extrae únicamente los datos crudos devueltos por la herramienta. "
                        f"REGLA ESTRICTA: No inventes fechas ni eventos si la herramienta no los reporta. No saludes.",
            expected_output="Fechas reales encontradas en el calendario o aviso exacto de que no hay fechas pendientes.", 
            agent=agente_calendario
        ))
        agentes_involucrados.insert(0, agente_calendario)
        
    elif accion == "ARCHIVOS" and usar_archivos:
        peticion_listar = any(p in mensaje_alumno.lower() for p in [
            "nombr", "list", "cuales", "que archivo", "que doc", "archivos", "documentos", "material", "que hay", "que tenemos"
        ])

        try:
            from skills.archivos import tool_listar_archivos, tool_archivos
            if peticion_listar:
                info_recuperada = tool_listar_archivos(materia)
            else:
                info_recuperada = tool_archivos(materia, mensaje_alumno)
        except Exception as e:
            info_recuperada = f"Aviso de documentos: {e}"

        if peticion_listar:
            instruccion_accion = (
                f"🚨 ACCIÓN PRIORITARIA DE LISTADO: El alumno solicita nombrar o listar los archivos de '{materia}'.\n"
                f"PRESENTA la lista oficial completa de archivos disponibles devuelta por Moodle sin omitir ninguno."
            )
        else:
            instruccion_accion = (
                f"ACCIONES REQUERIDAS SEGÚN LA SOLICITUD:\n"
                f"1. Si el alumno solicita nombrar o listar archivos: Entrega la lista oficial completa de documentos.\n"
                f"2. Si el alumno solicita explicar o resumir un archivo específico o tema: Analiza y sintetiza fielmente el texto extraído del documento."
            )

        tareas_finales.append(Task(
            description=f"El alumno consulta sobre la materia '{materia}'. Mensaje ACTUAL: '{mensaje_alumno}'. Historial: {memoria_texto}\n\n"
                        f"DATOS Y TEXTOS REALES RECUPERADOS DE MOODLE PARA '{materia}':\n"
                        f"\"\"\"\n{info_recuperada}\n\"\"\"\n\n"
                        f"{instruccion_accion}\n\n"
                        f"REGLAS ESTRICTAS ANTI-ALUCINACIÓN Y ENFOQUE CONCRETO:\n"
                        f"1. Extrae y sintetiza ÚNICAMENTE información que esté explícitamente provista en los datos provistos arriba.\n"
                        f"2. TIENES TERMINANTEMENTE PROHIBIDO inventar conceptos, definiciones, autores o datos ajenos al texto.\n"
                        f"3. Si el texto no menciona el tema o no contiene la respuesta requerida, indícalo expresamente: 'El documento de la materia no contiene información sobre este tema'. No saludes.",
            expected_output="Lista de archivos oficiales o datos concretos extraídos del documento solicitado.", 
            agent=agente_archivos
        ))
        agentes_involucrados.insert(0, agente_archivos)

    # PASO 3: RESPUESTA FINAL (PROFESOR CON CAPACIDAD DE RAZONAMIENTO Y DATOS REALES)
    tareas_finales.append(Task(
        description=f"""
        Historial: {memoria_texto}
        Mensaje ACTUAL: "{mensaje_alumno}"
        
        INFORMACIÓN OFICIAL RECUPERADA DE MOODLE PARA '{materia}':
        \"\"\"
        {info_recuperada}
        \"\"\"
        
        1. TÚ ERES EL PROFESOR / TUTOR PEDAGÓGICO DE LA UNIVERSIDAD.
           Lee con atención el mensaje del alumno, RAZONA, PIENSA y comprende su verdadera intención.
           No dependas de si una palabra exacta está o no; usa tu capacidad de razonamiento para responder exactamente lo que el alumno necesita.
        2. ROL DE PROFESOR GUÍA (RAZONAMIENTO Y PEDAGOGÍA):
           - Si el alumno te pide que le nombres o listes los archivos de la materia, o saber qué material hay:
             Presenta la lista ordenada de los documentos oficiales devueltos arriba (con sus números o viñetas claras, tipo PDF/Word y sección).
             Luego pregúntale cordialmente cuál de esos archivos desea que le resumas o le expliques en detalle.
           - Si el alumno solicita explicar o resumir un archivo específico (ej. 'el primero', 'el segundo', o por nombre) o un tema:
             Razona sobre el texto oficial provisto arriba y bríndale una explicación pedagógica, clara, profunda y precisa sustentada fielmente en el documento.
           - Si el alumno pide un resumen general:
             Explica los conceptos esenciales apoyándote estrictamente en el material provisto.
        3. LEE EL HISTORIAL: Si ya saludaste al alumno en mensajes previos del historial, TIENES PROHIBIDO volver a decirle "Hola".
        4. 🚨 BARRERA ANTI-ALUCINACIONES (REGLA FUNDAMENTAL) 🚨:
           - Si tus colegas de backoffice trajeron información de apuntes o calendario o está provista arriba, básate EXCLUSIVA Y RIGUROSAMENTE en esos datos.
           - Si la información extraída de los apuntes NO responde a la pregunta del alumno, infórmaselo con transparencia y amabilidad. Recomiéndale consultar con el profesor o revisar material complementario.
           - TIENES ESTRICTAMENTE PROHIBIDO inventar definiciones, autores, fórmulas, archivos o datos que no provengan del material oficial de Moodle.
        5. Si no hubo búsqueda o es una consulta general, responde empáticamente.
        6. 🚨 REGLA DE CONTEXTO ACADÉMICO 🚨: Si el alumno habla de temas NO ACADÉMICOS (deportes, recetas, ocio, política, etc.), TIENES PROHIBIDO seguirle la corriente. Niégate cortésmente y reorienta la charla al estudio.
        """,
        expected_output="Respuesta pedagógica, empática, segura y 100% veraz sustentada en los datos provistos.",
        agent=agente_orquestador
    ))

    oficina_respuesta = Crew(agents=agentes_involucrados, tasks=tareas_finales, verbose=True, cache=False)
    resultado = str(oficina_respuesta.kickoff())
    
    historial_chats[id_usuario].append(f"Alumno: {mensaje_alumno}")
    historial_chats[id_usuario].append(f"Tú: {resultado}")
    return resultado
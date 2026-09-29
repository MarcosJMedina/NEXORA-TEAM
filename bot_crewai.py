import os
import sys

# Compatibilidad de codificación UTF-8 para consola en Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
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
from skills.utils import verificar_acceso_materia

load_dotenv()
historial_chats = {}

# =================================================================
# CONFIGURACIÓN DE LOS AGENTES
# =================================================================
modelo_ia = "groq/openai/gpt-oss-20b"
ia_orquestador = LLM(model=modelo_ia, api_key=os.getenv("GROQ_API_KEY_ERICK"), temperature=0.0)
ia_archivos = LLM(model=modelo_ia, api_key=os.getenv("GROQ_API_KEY_AMIGO1"), temperature=0.0)
ia_calendario = LLM(model=modelo_ia, api_key=os.getenv("GROQ_API_KEY_AMIGO2"), temperature=0.0)

agente_orquestador = Agent(
    role="Asistente Principal y Rostro de la Universidad",
    goal="Clasificar las intenciones del alumno y responder con total fidelidad a los datos de Moodle sin alucinar ni inventar información.",
    backstory="Sos el asistente virtual principal de Moodle. Eres empático, amable y pedagógico. "
              "Derivas búsquedas a tus colegas de backoffice y TÚ te encargas de redactar la respuesta final al alumno. "
              "BARRERA ANTI-ALUCINACIONES: Tu conocimiento se restringe rigurosamente a lo que tus colegas extraigan de Moodle. "
              "Si una información no está presente en los apuntes o el calendario, JAMÁS debes inventarla ni asumir respuestas. "
              "Admites con honestidad y amabilidad cuando un dato no se encuentra en el material oficial.",
    verbose=True, allow_delegation=False, llm=ia_orquestador
)

agente_calendario = Agent(
    role="Investigador de Fechas (Backoffice)",
    goal="Buscar fechas en el calendario de Moodle y entregar datos fidedignos sin suposiciones.",
    backstory="Sos una máquina de buscar fechas en Moodle. NO HABLAS CON EL ALUMNO. Usas tu tool_calendario para extraer la info. "
              "Reportas estrictamente los eventos encontrados. Si no hay eventos, lo informas con exactitud sin inventar fechas aproximadas ni plazos hipotéticos.",
    verbose=True, allow_delegation=False, llm=ia_calendario, tools=[tool_calendario]
)

agente_archivos = Agent(
    role="Analista de Apuntes (Backoffice)",
    goal="Buscar, leer y resumir apuntes de las materias entregando información fidedigna y estrictamente anclada al texto de los documentos, con cero tolerancia a la invención de datos.",
    backstory="Sos un analista documental riguroso. NO HABLAS CON EL ALUMNO. Usas tu tool_archivos para leer PDFs o DOCX de Moodle y devolver el texto puro. "
              "BARRERA ANTI-ALUCINACIONES: Te ciñes exclusivamente al texto extraído del documento. "
              "Tienes terminantemente prohibido suponer, extrapolar o inventar información que no esté explícitamente escrita en los apuntes. "
              "Si el documento no responde a la consulta del alumno, reportas claramente que el material no contiene esa información.",
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

    # =================================================================
    # BARRERA DE PERMISOS: VALIDACIÓN DE MATRÍCULA EN MOODLE
    # =================================================================
    if accion in ["CALENDARIO", "ARCHIVOS"]:
        tiene_acceso, id_materia, nombre_oficial, materia_existe = verificar_acceso_materia(id_usuario, materia)
        if not tiene_acceso:
            if materia_existe:
                respuesta_seguridad = (
                    f"Acceso denegado: No tienes acceso a la materia '{materia}' porque no te encuentras "
                    f"matriculado en ella. Si crees que se trata de un error, por favor contacta "
                    f"a tu profesor o al departamento de alumnos."
                )
            else:
                respuesta_seguridad = (
                    f"No encontré la materia '{materia}' en la plataforma Moodle. "
                    f"Por favor verifica el nombre de la asignatura."
                )
            
            historial_chats[id_usuario].append(f"Alumno: {mensaje_alumno}")
            historial_chats[id_usuario].append(f"Tú: {respuesta_seguridad}")
            return respuesta_seguridad

        if nombre_oficial:
            materia = nombre_oficial

    # PASO 2: PIPELINE DE TRABAJO
    tareas_finales = []
    agentes_involucrados = [agente_orquestador]

    if accion == "CALENDARIO":
        tareas_finales.append(Task(
            description=f"Busca fechas de exámenes y entregas para '{materia}'. Extrae únicamente los datos crudos devueltos por la herramienta. "
                        f"REGLA ESTRICTA: No inventes fechas ni eventos si la herramienta no los reporta. No saludes.",
            expected_output="Fechas reales encontradas en el calendario o aviso exacto de que no hay fechas pendientes.", agent=agente_calendario
        ))
        agentes_involucrados.insert(0, agente_calendario)
        
    elif accion == "ARCHIVOS":
        tareas_finales.append(Task(
            description=f"Lee los apuntes de '{materia}' para responder sobre: '{mensaje_alumno}'.\n"
                        f"REGLAS ESTRICTAS ANTI-ALUCINACIÓN:\n"
                        f"1. Extrae y sintetiza ÚNICAMENTE información que esté explícitamente escrita en el documento leído.\n"
                        f"2. TIENES TERMINANTEMENTE PROHIBIDO inventar conceptos, definiciones, autores o datos ajenos al texto.\n"
                        f"3. Si el texto no menciona el tema o no contiene la respuesta requerida, indícalo expresamente: 'El documento de la materia no contiene información sobre este tema'. No saludes.",
            expected_output="Datos extraídos fielmente del documento o confirmación explícita de ausencia de información en el material.", agent=agente_archivos
        ))
        agentes_involucrados.insert(0, agente_archivos)

    # PASO 3: RESPUESTA FINAL
    tareas_finales.append(Task(
        description=f"""
        Historial: {memoria_texto}
        Mensaje ACTUAL: "{mensaje_alumno}"
        
        1. TÚ ERES EL ÚNICO que habla con el alumno. Redacta una respuesta empática, clara y pedagógica.
        2. 🚨 BARRERA ANTI-ALUCINACIONES (REGLA FUNDAMENTAL) 🚨:
           - Si tus colegas de backoffice trajeron información de apuntes o calendario, básate EXCLUSIVA Y RIGUROSAMENTE en esos datos.
           - Si la información extraída de los apuntes NO responde a la pregunta del alumno o tus colegas indican que no figura en el material, infórmaselo con transparencia y amabilidad. Recomiéndale consultar con el profesor o revisar material complementario.
           - TIENES ESTRICTAMENTE PROHIBIDO inventar definiciones, autores, fórmulas o datos que no provengan del material oficial de Moodle.
        3. 🚨 REGLA DE CONTEXTO ACADÉMICO 🚨: Si el alumno habla de temas NO ACADÉMICOS (deportes, recetas, ocio, etc.), TIENES PROHIBIDO seguirle la corriente. Niégate cortésmente y reorienta la charla al estudio.
        """,
        expected_output="Respuesta pedagógica, empática, segura y 100% veraz sustentada en los datos provistos.",
        agent=agente_orquestador
    ))

    oficina_respuesta = Crew(agents=agentes_involucrados, tasks=tareas_finales, verbose=True, cache=False)
    resultado = str(oficina_respuesta.kickoff())
    
    historial_chats[id_usuario].append(f"Alumno: {mensaje_alumno}")
    historial_chats[id_usuario].append(f"Tú: {resultado}")
    return resultado
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# =====================================================================
# CONFIGURACIÓN DE SHIMS / MOCKS PARA DEPENDENCIAS EXTERNAS PESADAS
# Permite ejecutar los tests unitarios y de integración de inmediato.
# =====================================================================
class MockLLM:
    def __init__(self, model=None, api_key=None, temperature=None):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature

class MockAgent:
    def __init__(self, role=None, goal=None, backstory=None, verbose=False, allow_delegation=False, llm=None, tools=None):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.verbose = verbose
        self.allow_delegation = allow_delegation
        self.llm = llm
        self.tools = tools or []

class MockTask:
    def __init__(self, description=None, expected_output=None, agent=None):
        self.description = description
        self.expected_output = expected_output
        self.agent = agent

class MockCrew:
    instancias_creadas = []

    def __init__(self, agents=None, tasks=None, verbose=False, cache=False):
        self.agents = agents or []
        self.tasks = tasks or []
        self.verbose = verbose
        self.cache = cache
        MockCrew.instancias_creadas.append(self)

    def kickoff(self):
        # Implementación por defecto modificable en tests
        return "RESPUESTA_MOCK_DEFAULT"

crewai_mod = types.ModuleType("crewai")
crewai_mod.LLM = MockLLM
crewai_mod.Agent = MockAgent
crewai_mod.Task = MockTask
crewai_mod.Crew = MockCrew

sys.modules["crewai"] = crewai_mod
sys.modules["crewai.llms"] = types.ModuleType("crewai.llms")
sys.modules["crewai.llms.cache"] = types.ModuleType("crewai.llms.cache")
sys.modules["crewai.tools"] = types.ModuleType("crewai.tools")
sys.modules["crewai.tools"].tool = lambda name: (lambda f: f)
sys.modules["dotenv"] = types.ModuleType("dotenv")
sys.modules["dotenv"].load_dotenv = lambda: None
sys.modules["requests"] = types.ModuleType("requests")
sys.modules["docx"] = types.ModuleType("docx")
sys.modules["pypdf"] = types.ModuleType("pypdf")

# Ahora importamos bot_crewai con los mocks configurados
import bot_crewai


# =====================================================================
# 1. TEST UNITARIO: CONFIGURACIÓN Y PROMPTS ANTI-ALUCINACIONES
# =====================================================================
class TestUnitarioConfiguracionYPrompts(unittest.TestCase):
    """
    Verifica que las configuraciones de temperatura y los System Prompts
    cumplan estrictamente con las barreras anti-alucinaciones requeridas.
    """

    def test_temperatura_estricta_cero(self):
        """Todos los agentes LLM deben tener temperatura fijada exactamente en 0.0"""
        self.assertEqual(
            bot_crewai.ia_orquestador.temperature, 0.0,
            "ia_orquestador debe tener temperature=0.0"
        )
        self.assertEqual(
            bot_crewai.ia_archivos.temperature, 0.0,
            "ia_archivos debe tener temperature=0.0"
        )
        self.assertEqual(
            bot_crewai.ia_calendario.temperature, 0.0,
            "ia_calendario debe tener temperature=0.0"
        )

    def test_prompt_agente_archivos_anti_alucinacion(self):
        """El agente de archivos debe tener prohibido extrapolar o inventar datos fuera del texto de Moodle"""
        backstory = bot_crewai.agente_archivos.backstory
        goal = bot_crewai.agente_archivos.goal

        self.assertIn("BARRERA ANTI-ALUCINACIONES", backstory)
        self.assertIn("texto extraído del documento", backstory)
        self.assertIn("prohibido suponer, extrapolar o inventar información", backstory)
        self.assertIn("cero tolerancia a la invención de datos", goal)

    def test_prompt_agente_calendario_estricto(self):
        """El agente de calendario no debe asumir fechas que no figuren en la tool"""
        backstory = bot_crewai.agente_calendario.backstory
        goal = bot_crewai.agente_calendario.goal

        self.assertIn("sin suposiciones", goal)
        self.assertIn("Reportas estrictamente los eventos encontrados", backstory)
        self.assertIn("sin inventar fechas aproximadas", backstory)

    def test_prompt_agente_orquestador_grounding(self):
        """El orquestador debe restringirse exclusivamente a los datos provistos por Moodle"""
        backstory = bot_crewai.agente_orquestador.backstory
        goal = bot_crewai.agente_orquestador.goal

        self.assertIn("sin alucinar ni inventar información", goal)
        self.assertIn("BARRERA ANTI-ALUCINACIONES", backstory)
        self.assertIn("Tu conocimiento se restringe rigurosamente a lo que tus colegas extraigan de Moodle", backstory)
        self.assertIn("JAMÁS debes inventarla ni asumir respuestas", backstory)


# =====================================================================
# 2. TEST CON MOCKS: PIPELINE Y COMPORTAMIENTO DE BARRERAS
# =====================================================================
class TestMocksPipelineAntiAlucinaciones(unittest.TestCase):
    """
    Verifica que el pipeline 'consultar_oficina' construya correctamente las tareas
    y aplique las reglas de anti-alucinaciones durante la ejecución simulada.
    """

    def setUp(self):
        bot_crewai.historial_chats.clear()
        MockCrew.instancias_creadas.clear()

    def test_flujo_archivos_inyecta_barreras_y_agente(self):
        """
        Al consultar apuntes de una materia, el pipeline debe incluir al agente_archivos
        y definir tareas con reglas explícitas de anti-alucinación.
        """
        respuestas_kickoff = iter([
            "ARCHIVOS|Programacion 1",  # Decisión del clasificador
            "El apunte define algoritmo como una secuencia de pasos ordenados."  # Respuesta final
        ])

        with patch.object(MockCrew, "kickoff", side_effect=lambda: next(respuestas_kickoff)):
            resultado = bot_crewai.consultar_oficina(
                mensaje_alumno="¿Qué es un algoritmo según el apunte de Programacion 1?",
                id_usuario=101
            )

            # Debe haber ejecutado 2 crews: recepción (clasificación) y respuesta
            self.assertEqual(len(MockCrew.instancias_creadas), 2)
            oficina_respuesta = MockCrew.instancias_creadas[1]

            # Agentes involucrados deben ser el agente_archivos y el agente_orquestador
            self.assertIn(bot_crewai.agente_archivos, oficina_respuesta.agents)
            self.assertIn(bot_crewai.agente_orquestador, oficina_respuesta.agents)

            # Comprobar directivas en la tarea de archivos
            tarea_archivos = oficina_respuesta.tasks[0]
            self.assertIn("REGLAS ESTRICTAS ANTI-ALUCINACIÓN", tarea_archivos.description)
            self.assertIn("TIENES TERMINANTEMENTE PROHIBIDO inventar conceptos", tarea_archivos.description)

            # Comprobar directivas en la tarea del orquestador
            tarea_orquestador = oficina_respuesta.tasks[1]
            self.assertIn("BARRERA ANTI-ALUCINACIONES (REGLA FUNDAMENTAL)", tarea_orquestador.description)
            self.assertIn("TIENES ESTRICTAMENTE PROHIBIDO inventar definiciones", tarea_orquestador.description)

            # El historial debe actualizarse
            self.assertEqual(len(bot_crewai.historial_chats[101]), 2)
            self.assertIn("El apunte define algoritmo", resultado)

    def test_flujo_calendario_inyecta_reglas_estrictas(self):
        """Al consultar fechas, el pipeline debe incluir al agente_calendario con reglas de precisión"""
        respuestas_kickoff = iter([
            "CALENDARIO|Base de Datos",  # Clasificación
            "Tienes examen parcial el 15/10/2026 a las 18:00."  # Respuesta final
        ])

        with patch.object(MockCrew, "kickoff", side_effect=lambda: next(respuestas_kickoff)):
            resultado = bot_crewai.consultar_oficina(
                mensaje_alumno="¿Cuándo es el examen de Base de Datos?",
                id_usuario=102
            )

            oficina_respuesta = MockCrew.instancias_creadas[1]
            self.assertIn(bot_crewai.agente_calendario, oficina_respuesta.agents)

            tarea_calendario = oficina_respuesta.tasks[0]
            self.assertIn("No inventes fechas ni eventos si la herramienta no los reporta", tarea_calendario.description)
            self.assertIn("15/10/2026", resultado)

    def test_flujo_charla_sin_materia_no_llama_backoffice(self):
        """Si el alumno solo saluda o no menciona materias, no se invocan agentes de backoffice"""
        respuestas_kickoff = iter([
            "CHARLA|Ninguna",  # Clasificación
            "¡Hola! ¿En qué puedo ayudarte hoy con tus materias de Moodle?"  # Respuesta final
        ])

        with patch.object(MockCrew, "kickoff", side_effect=lambda: next(respuestas_kickoff)):
            resultado = bot_crewai.consultar_oficina(
                mensaje_alumno="Hola, buenas tardes",
                id_usuario=103
            )

            oficina_respuesta = MockCrew.instancias_creadas[1]
            # Únicamente el orquestador participa
            self.assertEqual(oficina_respuesta.agents, [bot_crewai.agente_orquestador])
            self.assertEqual(len(oficina_respuesta.tasks), 1)
            self.assertIn("REGLA DE CONTEXTO ACADÉMICO", oficina_respuesta.tasks[0].description)


if __name__ == "__main__":
    unittest.main(verbosity=2)

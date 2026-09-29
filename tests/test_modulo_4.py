import unittest
from unittest.mock import patch

# Cargar mocks antes de importar código de aplicación
import tests.conftest_mocks as conftest_mocks
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
        conftest_mocks.MockCrew.instancias_creadas.clear()
        # En las pruebas del módulo 4 simulamos que el alumno tiene acceso para validar los agentes
        self.patch_permisos = patch("bot_crewai.verificar_acceso_materia", side_effect=lambda u, m: (True, 10, m, True))
        self.patch_permisos.start()

    def tearDown(self):
        self.patch_permisos.stop()

    def test_flujo_archivos_inyecta_barreras_y_agente(self):
        """
        Al consultar apuntes de una materia, el pipeline debe incluir al agente_archivos
        y definir tareas con reglas explícitas de anti-alucinación.
        """
        respuestas_kickoff = iter([
            "ARCHIVOS|Programacion 1",  # Decisión del clasificador
            "El apunte define algoritmo como una secuencia de pasos ordenados."  # Respuesta final
        ])

        with patch.object(conftest_mocks.MockCrew, "kickoff", side_effect=lambda: next(respuestas_kickoff)):
            resultado = bot_crewai.consultar_oficina(
                mensaje_alumno="¿Qué es un algoritmo según el apunte de Programacion 1?",
                id_usuario=101
            )

            # Debe haber ejecutado 2 crews: recepción (clasificación) y respuesta
            self.assertEqual(len(conftest_mocks.MockCrew.instancias_creadas), 2)
            oficina_respuesta = conftest_mocks.MockCrew.instancias_creadas[1]

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

        with patch.object(conftest_mocks.MockCrew, "kickoff", side_effect=lambda: next(respuestas_kickoff)):
            resultado = bot_crewai.consultar_oficina(
                mensaje_alumno="¿Cuándo es el examen de Base de Datos?",
                id_usuario=102
            )

            oficina_respuesta = conftest_mocks.MockCrew.instancias_creadas[1]
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

        with patch.object(conftest_mocks.MockCrew, "kickoff", side_effect=lambda: next(respuestas_kickoff)):
            resultado = bot_crewai.consultar_oficina(
                mensaje_alumno="Hola, buenas tardes",
                id_usuario=103
            )

            oficina_respuesta = conftest_mocks.MockCrew.instancias_creadas[1]
            # Únicamente el orquestador participa
            self.assertEqual(oficina_respuesta.agents, [bot_crewai.agente_orquestador])
            self.assertEqual(len(oficina_respuesta.tasks), 1)
            self.assertIn("REGLA DE CONTEXTO ACADÉMICO", oficina_respuesta.tasks[0].description)


if __name__ == "__main__":
    unittest.main(verbosity=2)

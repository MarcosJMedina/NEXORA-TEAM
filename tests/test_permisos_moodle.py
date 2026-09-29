import unittest
from unittest.mock import MagicMock, patch

import tests.conftest_mocks as conftest_mocks
import skills.utils as utils
import skills.archivos as archivos
import bot_crewai


class TestPermisosMatriculacionMoodle(unittest.TestCase):
    """
    Pruebas para verificar que un usuario logueado NO acceda a materias
    en las que no esté matriculado.
    """

    def setUp(self):
        bot_crewai.historial_chats.clear()
        conftest_mocks.MockCrew.instancias_creadas.clear()

    @patch("skills.utils.obtener_cursos_matriculados")
    @patch("skills.utils.buscar_id_materia")
    def test_usuario_no_matriculado_bloqueado_en_archivos(self, mock_buscar_id, mock_cursos_usuario):
        """Un usuario que consulta apuntes de una materia no matriculada debe ser bloqueado de inmediato."""
        # El alumno 999 solo está matriculado en Programación 1
        mock_cursos_usuario.return_value = [{"id": 10, "fullname": "Programacion 1", "shortname": "PROG1"}]
        # Arquitectura existe globalmente en la universidad
        mock_buscar_id.return_value = 20

        # Clasificador decide que pide ARCHIVOS de Arquitectura
        with patch.object(conftest_mocks.MockCrew, "kickoff", return_value="ARCHIVOS|Arquitectura"):
            respuesta = bot_crewai.consultar_oficina(
                mensaje_alumno="¿Me pasas el apunte de Arquitectura?",
                id_usuario=999
            )

            # Debe retornar mensaje de acceso denegado
            self.assertIn("Acceso denegado", respuesta)
            self.assertIn("no te encuentras matriculado", respuesta)

            # Solo debe haberse creado 1 crew (el clasificador).
            # NUNCA debe crearse el segundo crew de backoffice
            self.assertEqual(len(conftest_mocks.MockCrew.instancias_creadas), 1)

    @patch("skills.utils.obtener_cursos_matriculados")
    @patch("skills.utils.buscar_id_materia")
    def test_usuario_no_matriculado_bloqueado_en_calendario(self, mock_buscar_id, mock_cursos_usuario):
        """Un usuario que consulta fechas de una materia no matriculada debe ser bloqueado."""
        mock_cursos_usuario.return_value = [{"id": 10, "fullname": "Programacion 1", "shortname": "PROG1"}]
        mock_buscar_id.return_value = 30

        with patch.object(conftest_mocks.MockCrew, "kickoff", return_value="CALENDARIO|Fisica"):
            respuesta = bot_crewai.consultar_oficina(
                mensaje_alumno="¿Cuándo es el examen de Fisica?",
                id_usuario=999
            )

            self.assertIn("Acceso denegado", respuesta)
            self.assertIn("no te encuentras matriculado", respuesta)
            self.assertEqual(len(conftest_mocks.MockCrew.instancias_creadas), 1)

    @patch("skills.utils.obtener_cursos_matriculados")
    def test_usuario_matriculado_acceso_permitido(self, mock_cursos_usuario):
        """Un usuario matriculado en la materia debe poder avanzar al pipeline de backoffice."""
        mock_cursos_usuario.return_value = [{"id": 10, "fullname": "Programacion 1", "shortname": "PROG1"}]

        respuestas_kickoff = iter([
            "ARCHIVOS|Programacion 1",
            "Aquí tienes el resumen del apunte de Programacion 1..."
        ])

        with patch.object(conftest_mocks.MockCrew, "kickoff", side_effect=lambda: next(respuestas_kickoff)):
            respuesta = bot_crewai.consultar_oficina(
                mensaje_alumno="Explícame variables según Programacion 1",
                id_usuario=101
            )

            # Acceso permitido: se ejecutó la oficina de respuesta
            self.assertEqual(len(conftest_mocks.MockCrew.instancias_creadas), 2)
            self.assertIn("Aquí tienes el resumen", respuesta)


class TestContenidosOcultosMoodle(unittest.TestCase):
    """
    Pruebas para verificar que la IA NO acceda a contenidos, temas o secciones
    ocultos (visible=0 o uservisible=False) en Moodle.
    """

    @patch("skills.archivos.buscar_id_materia", return_value=10)
    def test_filtro_ignora_secciones_y_modulos_ocultos(self, mock_buscar):
        """Verifica que se ignoren archivos que residen en secciones o módulos con visible=0 o uservisible=False."""
        estructura_moodle_mock = [
            {
                "id": 1,
                "name": "Sección Oculta de Exámenes",
                "visible": 0,
                "uservisible": False,
                "modules": [
                    {
                        "id": 101,
                        "name": "Examen Secreto",
                        "visible": 0,
                        "uservisible": False,
                        "contents": [{"filename": "examen_filtrado.pdf", "fileurl": "http://moodle/examen"}]
                    }
                ]
            },
            {
                "id": 2,
                "name": "Sección Visible",
                "visible": 1,
                "uservisible": True,
                "modules": [
                    {
                        "id": 102,
                        "name": "Material Oculto",
                        "visible": 0,
                        "uservisible": False,
                        "contents": [{"filename": "respuestas_ocultas.pdf", "fileurl": "http://moodle/respuestas"}]
                    },
                    {
                        "id": 103,
                        "name": "Apunte Visible 1",
                        "visible": 1,
                        "uservisible": True,
                        "contents": [{"filename": "apunte_permitido.docx", "fileurl": "http://moodle/apunte"}]
                    }
                ]
            }
        ]

        mock_resp_json = MagicMock()
        mock_resp_json.json.return_value = estructura_moodle_mock
        mock_resp_content = MagicMock()
        mock_resp_content.content = b"fake binary content"

        with patch("skills.archivos.requests.get", side_effect=[mock_resp_json, mock_resp_content]):
            with patch("skills.archivos.docx.Document") as mock_docx:
                mock_par = MagicMock()
                mock_par.text = "Contenido público y permitido de la materia."
                mock_docx.return_value.paragraphs = [mock_par]

                with patch("builtins.open", MagicMock()):
                    resultado = archivos.tool_archivos("Programacion 1", "resumen general")

                    # Debe haber leído el archivo visible
                    self.assertIn("Contenido público y permitido", resultado)

    @patch("skills.archivos.buscar_id_materia", return_value=10)
    def test_todos_contenidos_ocultos_retorna_aviso(self, mock_buscar):
        """Si todo el contenido de la materia está oculto, no debe acceder y debe notificar."""
        estructura_oculta = [
            {
                "id": 1,
                "name": "Tema 1",
                "visible": 0,
                "uservisible": False,
                "modules": [
                    {"contents": [{"filename": "privado.pdf", "fileurl": "http://moodle/privado"}]}
                ]
            }
        ]
        mock_resp = MagicMock()
        mock_resp.json.return_value = estructura_oculta

        with patch("skills.archivos.requests.get", return_value=mock_resp):
            resultado = archivos.tool_archivos("Programacion 1", "tema")
            self.assertIn("No hay archivos o contenidos visibles", resultado)


class TestServidorFastAPIPropagacionUsuario(unittest.TestCase):
    """
    Verifica que server.py reciba y propague el user_id autenticado del frontend.
    """

    @patch("server.consultar_oficina")
    def test_chat_endpoint_pasa_user_id(self, mock_consultar_oficina):
        mock_consultar_oficina.return_value = "Respuesta del bot"
        import server

        # Simular Request del frontend
        req = server.ChatRequest(user_id=777, course_id=10, message="Hola bot")
        res = server.chat_endpoint(req)

        mock_consultar_oficina.assert_called_once_with("Hola bot", id_usuario=777)
        self.assertTrue(res["success"])
        self.assertEqual(res["response"], "Respuesta del bot")


if __name__ == "__main__":
    unittest.main(verbosity=2)

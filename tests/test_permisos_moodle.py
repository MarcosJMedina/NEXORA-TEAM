import unittest
from unittest.mock import MagicMock, patch

import tests.conftest_mocks as conftest_mocks
import skills.utils as utils
import skills.archivos as archivos
import bot_crewai


class TestPermisosMatriculacionMoodle(unittest.TestCase):
    """
    Pruebas para verificar que la seguridad perimetral en server.py
    valide adecuadamente la matrícula de los alumnos.
    """

    @patch("server.requests.get")
    def test_usuario_no_matriculado_bloqueado_en_servidor(self, mock_requests):
        """Un usuario que consulta un curso en el que no está matriculado debe ser bloqueado."""
        import server
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"id": 10, "fullname": "Programacion 1"}]
        mock_requests.return_value = mock_resp

        # Alumno 999 no está matriculado en curso 20
        autorizado = server.verificar_matricula_moodle(user_id=999, course_id=20)
        self.assertFalse(autorizado)

    @patch("server.requests.get")
    def test_usuario_matriculado_acceso_permitido_en_servidor(self, mock_requests):
        """Un usuario matriculado en el curso debe ser autorizado."""
        import server
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"id": 10, "fullname": "Programacion 1"}]
        mock_requests.return_value = mock_resp

        autorizado = server.verificar_matricula_moodle(user_id=999, course_id=10)
        self.assertTrue(autorizado)

    def test_usuario_invitado_o_anonimo_bloqueado(self):
        """Usuarios con ID 0 o 1 (invitados/anónimos) deben ser bloqueados sin consultar Moodle."""
        import server
        self.assertFalse(server.verificar_matricula_moodle(user_id=0, course_id=10))
        self.assertFalse(server.verificar_matricula_moodle(user_id=1, course_id=10))

    def test_admin_y_portada_autorizados(self):
        """El administrador supremo (ID 2) y la portada (curso 1) están siempre autorizados."""
        import server
        self.assertTrue(server.verificar_matricula_moodle(user_id=2, course_id=10))
        self.assertTrue(server.verificar_matricula_moodle(user_id=50, course_id=1))


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
        mock_resp_content.status_code = 200

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

    @patch("skills.archivos.buscar_id_materia", return_value=10)
    def test_listar_archivos_materia_formato_y_filtro(self, mock_buscar):
        """Verifica que tool_listar_archivos liste solo los archivos visibles con su sección y tipo."""
        estructura_mock = [
            {
                "id": 1,
                "name": "Unidad 1 - Fundamentos",
                "visible": 1,
                "uservisible": True,
                "modules": [
                    {
                        "id": 101,
                        "name": "Apunte 1",
                        "visible": 1,
                        "uservisible": True,
                        "contents": [{"filename": "Unidad1_Introduccion.pdf", "fileurl": "http://moodle/u1"}]
                    },
                    {
                        "id": 102,
                        "name": "Documento Oculto",
                        "visible": 0,
                        "uservisible": False,
                        "contents": [{"filename": "Secreto.pdf", "fileurl": "http://moodle/sec"}]
                    }
                ]
            }
        ]
        mock_resp = MagicMock()
        mock_resp.json.return_value = estructura_mock

        with patch("skills.archivos.requests.get", return_value=mock_resp):
            lista = archivos.tool_listar_archivos("Programacion 1")
            self.assertIn("Unidad1_Introduccion.pdf", lista)
            self.assertIn("[PDF]", lista)
            self.assertNotIn("Secreto.pdf", lista)


class TestServidorFastAPIPropagacionUsuario(unittest.TestCase):
    """
    Verifica que server.py reciba y propague el user_id autenticado del frontend
    y aplique la Capa 1 de validación perimetral de matrícula.
    """

    @patch("server.verificar_matricula_moodle", return_value=True)
    @patch("server.consultar_oficina")
    def test_chat_endpoint_pasa_user_id(self, mock_consultar_oficina, mock_verificar):
        mock_consultar_oficina.return_value = "Respuesta del bot"
        import server

        # Simular Request del frontend
        req = server.ChatRequest(user_id=777, course_id=10, message="Hola bot")
        res = server.chat_endpoint(req)

        mock_verificar.assert_called_once_with(777, 10)
        mock_consultar_oficina.assert_called_once_with("Hola bot", id_usuario=777)
        self.assertTrue(res["success"])
        self.assertEqual(res["response"], "Respuesta del bot")

    @patch("server.verificar_matricula_moodle", return_value=False)
    @patch("server.consultar_oficina")
    def test_chat_endpoint_rechaza_no_matriculado(self, mock_consultar_oficina, mock_verificar):
        import server

        req = server.ChatRequest(user_id=888, course_id=99, message="Quiero entrar")
        res = server.chat_endpoint(req)

        mock_verificar.assert_called_once_with(888, 99)
        mock_consultar_oficina.assert_not_called()
        self.assertFalse(res["success"])
        self.assertIn("debes iniciar sesión en Moodle", res["response"])


class TestSeguridadSemanticaMaterias(unittest.TestCase):
    """
    Pruebas para verificar que bot_crewai bloquee consultas de materias
    en las que el alumno no está matriculado, incluso si la petición pasó el servidor.
    """

    @patch("skills.utils.requests.get")
    def test_verificar_usuario_en_materia_autoriza_si_matriculado(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"id": 5, "fullname": "Matematica"}]
        mock_requests.return_value = mock_resp

        self.assertTrue(utils.verificar_usuario_en_materia(user_id=10, course_id=5))
        self.assertFalse(utils.verificar_usuario_en_materia(user_id=10, course_id=8))

    @patch("skills.utils.requests.get")
    def test_verificar_usuario_en_materia_admin_siempre_true(self, mock_requests):
        self.assertTrue(utils.verificar_usuario_en_materia(user_id=2, course_id=99))
        mock_requests.assert_not_called()

    @patch("skills.utils.buscar_id_materia", return_value=15)
    @patch("skills.utils.verificar_usuario_en_materia", return_value=False)
    def test_consultar_oficina_bloquea_materia_no_matriculada(self, mock_verif, mock_buscar):
        bot_crewai.historial_chats.clear()
        conftest_mocks.MockCrew.instancias_creadas.clear()

        # Simulamos que el clasificador devuelve que pide ARCHIVOS de Inteligencia Artificial
        with patch.object(conftest_mocks.MockCrew, "kickoff", return_value="ARCHIVOS|Inteligencia Artificial"):
            respuesta = bot_crewai.consultar_oficina("Explicame el tema 1", id_usuario=3)

            # Debe bloquear de inmediato sin llamar a los agentes de backoffice
            self.assertIn("No tienes acceso a los contenidos de 'Inteligencia Artificial'", respuesta)
            # Solo se debió haber ejecutado el clasificador (1 crew), no la oficina de respuesta
            self.assertEqual(len(conftest_mocks.MockCrew.instancias_creadas), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

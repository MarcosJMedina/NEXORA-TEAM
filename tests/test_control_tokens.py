import time
import unittest
from unittest.mock import patch, MagicMock

import tests.conftest_mocks as conftest_mocks
from skills.control_tokens import GestorCuotaTokens
import server


class TestControlTokensYAutorregeneracion(unittest.TestCase):
    """
    Pruebas para el sistema de ahorro de tokens y autorregeneración por tiempo.
    """

    def setUp(self):
        self.gestor = GestorCuotaTokens()
        self.gestor.max_preguntas = 3
        self.gestor.ventana_minutos = 10  # 600 segundos
        self.gestor.enabled = True
        self.gestor.usuarios.clear()

    def test_consumo_gradual_hasta_limite(self):
        """Un usuario puede hacer preguntas hasta el límite establecido (3 preguntas)."""
        user_id = 501

        # Pregunta 1
        ok, msg = self.gestor.verificar_y_consumir(user_id)
        self.assertTrue(ok)
        self.assertEqual(self.gestor.usuarios[user_id]["preguntas_restantes"], 2)

        # Pregunta 2
        ok, msg = self.gestor.verificar_y_consumir(user_id)
        self.assertTrue(ok)
        self.assertEqual(self.gestor.usuarios[user_id]["preguntas_restantes"], 1)

        # Pregunta 3
        ok, msg = self.gestor.verificar_y_consumir(user_id)
        self.assertTrue(ok)
        self.assertEqual(self.gestor.usuarios[user_id]["preguntas_restantes"], 0)

        # Pregunta 4 (Debe detenerse la IA)
        ok, msg = self.gestor.verificar_y_consumir(user_id)
        self.assertFalse(ok)
        self.assertIn("Límite de consultas alcanzado", msg)
        self.assertIn("3 preguntas", msg)
        self.assertIn("Tus tokens se autorregenerarán automáticamente", msg)

    def test_admin_sin_limite(self):
        """El administrador supremo (ID 2) no tiene restricciones de cuota."""
        admin_id = 2
        for _ in range(10):
            ok, msg = self.gestor.verificar_y_consumir(admin_id)
            self.assertTrue(ok)

    def test_autoregeneracion_automatica_por_tiempo(self):
        """Al transcurrir la ventana de tiempo, los tokens se regeneran automáticamente."""
        user_id = 601
        tiempo_base = 1000000.0

        with patch("time.time", return_value=tiempo_base):
            # Agota las 3 preguntas
            for _ in range(3):
                self.gestor.verificar_y_consumir(user_id)
            
            # Intento bloqueado
            ok, _ = self.gestor.verificar_y_consumir(user_id)
            self.assertFalse(ok)

        # Simular avance del tiempo después de los 10 minutos (601 segundos después)
        tiempo_futuro = tiempo_base + 601.0
        with patch("time.time", return_value=tiempo_futuro):
            # La nueva consulta debe autorizarse y autorregenerar la cuota
            ok, msg = self.gestor.verificar_y_consumir(user_id)
            self.assertTrue(ok)
            # El saldo debe ser 2 (3 iniciales - 1 consumida en la nueva ventana)
            self.assertEqual(self.gestor.usuarios[user_id]["preguntas_restantes"], 2)

    @patch("server.consultar_oficina")
    @patch("server.verificar_matricula_moodle", return_value=True)
    def test_server_endpoint_bloquea_y_no_llama_agentes(self, mock_verificar, mock_consultar_oficina):
        """El endpoint /api/chat debe frenar la petición sin llamar a los agentes cuando se agote la cuota."""
        # Configurar gestor global del servidor
        server.gestor_tokens.max_preguntas = 2
        server.gestor_tokens.ventana_minutos = 5
        server.gestor_tokens.usuarios.clear()

        user_id = 701
        req = server.ChatRequest(user_id=user_id, course_id=1, message="Pregunta 1")
        mock_consultar_oficina.return_value = "Respuesta agentes"

        # Pregunta 1
        res1 = server.chat_endpoint(req)
        self.assertTrue(res1["success"])
        self.assertEqual(res1["response"], "Respuesta agentes")

        # Pregunta 2
        res2 = server.chat_endpoint(req)
        self.assertTrue(res2["success"])
        self.assertEqual(res2["response"], "Respuesta agentes")

        # Pregunta 3 -> Debe ser bloqueada sin llamar a los agentes
        mock_consultar_oficina.reset_mock()
        res3 = server.chat_endpoint(req)
        self.assertTrue(res3["success"])
        self.assertIn("Límite de consultas alcanzado", res3["response"])
        mock_consultar_oficina.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)

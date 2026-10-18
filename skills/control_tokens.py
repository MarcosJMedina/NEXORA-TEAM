import os
import time
import json
from datetime import datetime

# =====================================================================
# CONFIGURACIÓN ESTÁNDAR DE TOKENS Y LÍMITES POR USUARIO
# =====================================================================
# 1. Tokens estándar de Entrada (Prompt Context Window): 4096 tokens
MAX_TOKENS_ENTRADA_DEF = 4096

# 2. Tokens estándar de Salida (Max Completion Tokens): 1024 tokens
MAX_TOKENS_SALIDA_DEF = 1024

# 3. Cantidad de preguntas permitidas por alumno en cada ventana: 5 preguntas
MAX_PREGUNTAS_DEF = 5

# 4. Tiempo de regeneración automática: 10 minutos (600 segundos)
VENTANA_MINUTOS_DEF = 10


class GestorCuotaTokens:
    """
    Controlador de cuotas y autorregeneración automática de tokens/preguntas
    para estudiantes en Moodle.
    """

    def __init__(self):
        self.usuarios = {}  # {user_id: {"preguntas_restantes": int, "proxima_recarga": float}}
        self._cargar_configuracion()

    def _cargar_configuracion(self):
        """Carga configuración desde config.json o variables de entorno con respaldos estándar."""
        self.max_tokens_entrada = int(os.getenv("MAX_TOKENS_ENTRADA", MAX_TOKENS_ENTRADA_DEF))
        self.max_tokens_salida = int(os.getenv("MAX_TOKENS_SALIDA", MAX_TOKENS_SALIDA_DEF))
        self.max_preguntas = int(os.getenv("MAX_PREGUNTAS_USUARIO", MAX_PREGUNTAS_DEF))
        self.ventana_minutos = int(os.getenv("TIEMPO_REGENERACION_MINUTOS", VENTANA_MINUTOS_DEF))
        self.enabled = True

        # Intentar leer desde config.json si existe
        ruta_config = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        if os.path.exists(ruta_config):
            try:
                with open(ruta_config, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    limite_cfg = data.get("limite_tokens", {})
                    self.enabled = limite_cfg.get("enabled", True)
                    self.max_preguntas = limite_cfg.get("max_preguntas", self.max_preguntas)
                    self.ventana_minutos = limite_cfg.get("ventana_minutos", self.ventana_minutos)
                    self.max_tokens_entrada = limite_cfg.get("max_tokens_entrada", self.max_tokens_entrada)
                    self.max_tokens_salida = limite_cfg.get("max_tokens_salida", self.max_tokens_salida)
            except Exception as e:
                print(f"⚠️ [CONTROL TOKENS] No se pudo leer config.json: {e}")

    @property
    def ventana_segundos(self) -> int:
        return self.ventana_minutos * 60

    def verificar_y_consumir(self, user_id: int) -> tuple[bool, str]:
        """
        Verifica si el usuario tiene cupo disponible de preguntas/tokens.
        Si tiene cupo, consume una pregunta y retorna (True, "").
        Si se agotó el cupo, retorna (False, mensaje_explicativo_con_tiempo_restante).
        """
        if not self.enabled:
            return True, ""

        # El Administrador Supremo (ID 2) no tiene restricciones
        if user_id == 2:
            return True, ""

        ahora = time.time()
        registro = self.usuarios.get(user_id)

        # Caso 1: Primera interacción o la ventana expiró -> Autorregeneración automática
        if not registro or ahora >= registro["proxima_recarga"]:
            proxima_recarga = ahora + self.ventana_segundos
            self.usuarios[user_id] = {
                "preguntas_restantes": self.max_preguntas - 1,
                "proxima_recarga": proxima_recarga
            }
            return True, ""

        # Caso 2: Dentro de la ventana y le quedan preguntas disponibles
        if registro["preguntas_restantes"] > 0:
            registro["preguntas_restantes"] -= 1
            return True, ""

        # Caso 3: Límite alcanzado -> Detener IA y avisar motivo y tiempo de espera
        segundos_restantes = max(1, int(registro["proxima_recarga"] - ahora))
        minutos = segundos_restantes // 60
        segundos = segundos_restantes % 60
        hora_desbloqueo = datetime.fromtimestamp(registro["proxima_recarga"]).strftime("%H:%M:%S")

        tiempo_formateado = f"{minutos}m {segundos}s" if minutos > 0 else f"{segundos}s"

        mensaje = (
            f"⏳ Límite de consultas alcanzado: Has agotado tu cupo de {self.max_preguntas} preguntas "
            f"disponibles para cuidar los recursos y tokens del sistema. "
            f"Tus tokens se autorregenerarán automáticamente en {tiempo_formateado} "
            f"(podrás volver a consultar a partir de las {hora_desbloqueo})."
        )

        return False, mensaje

    def reiniciar_usuario(self, user_id: int):
        """Reinicia la cuota de un usuario (útil para pruebas o soporte)."""
        if user_id in self.usuarios:
            del self.usuarios[user_id]


# Instancia global compartida del gestor de cuotas
gestor_tokens = GestorCuotaTokens()

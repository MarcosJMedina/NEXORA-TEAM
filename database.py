import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "mariadb")
DB_USER = os.getenv("DB_USER", "nexora_user")
DB_PASS = os.getenv("DB_PASS", "nexora_password")
DB_NAME = os.getenv("DB_NAME", "moodle_nexora")

def obtener_conexion():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )

def inicializar_bd():
    """Crea las tablas de usuarios, roles e historial."""
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id_moodle INT PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            rol VARCHAR(50) DEFAULT 'estudiante',
            fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_chat (
            id INT AUTO_INCREMENT PRIMARY KEY,
            id_moodle INT NOT NULL,
            pregunta TEXT NOT NULL,
            respuesta TEXT NOT NULL,
            tokens_consumidos INT DEFAULT 0,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_moodle) REFERENCES usuarios(id_moodle)
        );
        """)
    conn.close()

def sincronizar_usuario(id_moodle: int, nombre: str, email: str, rol: str = "estudiante"):
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        sql = """
        INSERT INTO usuarios (id_moodle, nombre, email, rol)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE nombre=%s, email=%s, rol=%s;
        """
        cursor.execute(sql, (id_moodle, nombre, email, rol, nombre, email, rol))
    conn.close()

def obtener_rol_usuario(id_moodle: int) -> str:
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("SELECT rol FROM usuarios WHERE id_moodle = %s", (id_moodle,))
        user = cursor.fetchone()
    conn.close()
    return user["rol"] if user else "invitado"
import pymysql

# Configura tus credenciales locales de MariaDB
DB_HOST = "127.0.0.1"
DB_USER = "root"
DB_PASSWORD = ""        # Tu contraseña de MariaDB si tienes una
DB_NAME = "moodle"     # Nombre de tu base de datos
DB_PORT = 3306

def obtener_conexion():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        autocommit=True
    )

def crear_tabla_historial():
    """Crea la tabla donde se guardarán los chats de los alumnos si no existe."""
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        sql = """
        CREATE TABLE IF NOT EXISTS historial_chatbot (
            id INT AUTO_INCREMENT PRIMARY KEY,
            id_alumno VARCHAR(50) NOT NULL,
            pregunta TEXT NOT NULL,
            respuesta TEXT NOT NULL,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
        cursor.execute(sql)
    conn.close()

def guardar_mensaje(id_alumno: str, pregunta: str, respuesta: str):
    """Guarda un registro de la interacción del alumno con el chatbot."""
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        sql = "INSERT INTO historial_chatbot (id_alumno, pregunta, respuesta) VALUES (%s, %s, %s)"
        cursor.execute(sql, (id_alumno, pregunta, respuesta))
    conn.close()
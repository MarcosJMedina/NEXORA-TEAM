¡Hola! Te paso todo el backend del chatbot con la integración a Moodle que dejé funcionando ayer para que lo pruebes en tu PC antes de subirlo al GitHub oficial del proyecto.

📋 Pasos para probarlo en tu entorno:

Instalar dependencias en la terminal:
pip install fastapi uvicorn requests pydantic

Crear el backend:
Crea una carpeta llamada chatbot-backend (fuera de la carpeta de Moodle). Adentro guarda el archivo main.py con el código del Mensaje 2.

Configurar variables en main.py:

MOODLE_URL: Asegurate de que apunte a tu Moodle local (ej: http://localhost/moodle/webservice/rest/server.php).

MOODLE_TOKEN: Poné tu token generado en Moodle (debe tener acceso al protocolo REST y a la función core_enrol_get_users_courses).

Ejecutar el servidor Python:
En la terminal dentro de chatbot-backend, corré:
python main.py

Insertar el Widget en tu Moodle:
Ve a Administración del sitio > Apariencia > HTML adicional > Antes de cerrar BODY y pegá el código JS/HTML que te adjunto en el Mensaje 3.

Probar: Refrescá Moodle, abrí el chat flotante abajo a la derecha y mandá un mensaje. Te debería responder confirmando la verificación de usuario/curso en tiempo real.
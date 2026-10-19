import requests
import os
from dotenv import load_dotenv

load_dotenv()

MOODLE_URL = os.getenv("MOODLE_URL", "http://localhost")
MOODLE_TOKEN = os.getenv("MOODLE_TOKEN", "")

def validar_token_moodle(user_token: str):
    """Verifica si el token enviado por el usuario es válido en Moodle."""
    params = {
        'wstoken': user_token or MOODLE_TOKEN,
        'wsfunction': 'core_webservice_get_site_info',
        'moodlewsrestformat': 'json'
    }
    try:
        response = requests.get(f"{MOODLE_URL}/webservice/rest/server.php", params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "exception" not in data:
                return {
                    "id_moodle": data.get("userid"),
                    "nombre": data.get("fullname"),
                    "username": data.get("username")
                }
    except Exception as e:
        print(f"Error conectando a Moodle API: {e}")
    return None
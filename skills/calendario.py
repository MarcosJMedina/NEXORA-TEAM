import requests
import datetime
from crewai.tools import tool
from skills.utils import buscar_id_materia, URL_LOCAL, TOKEN_LOCAL

@tool("Revisar Calendario Moodle")
def tool_calendario(nombre_materia: str) -> str:
    """Útil para buscar fechas de exámenes o entregas. Pasale el nombre de la materia."""
    id_materia = buscar_id_materia(nombre_materia)
    if not id_materia: return f"No encontré la materia {nombre_materia}."
    
    parametros = {"wstoken": TOKEN_LOCAL, "wsfunction": "core_calendar_get_calendar_events", "moodlewsrestformat": "json", "events[courseids][0]": id_materia}
    respuesta = requests.get(URL_LOCAL, params=parametros).json()
    
    eventos = []
    if "events" in respuesta:
        for ev in respuesta["events"]:
            fecha = datetime.datetime.fromtimestamp(ev.get("timestart", 0)).strftime('%d/%m/%Y %H:%M')
            eventos.append(f"- {ev.get('name', 'Evento')}: {fecha}")
            
    return "\n".join(eventos) if eventos else "No hay fechas pendientes."
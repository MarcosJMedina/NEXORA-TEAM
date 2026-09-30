from database import crear_tabla_historial, guardar_mensaje
from vector_skill import buscar_contexto
import ollama

def consultar_llm(prompt: str) -> str:
    """Envía el prompt procesado a la IA (en este ejemplo con Ollama / Llama 3)."""
    respuesta = ollama.chat(
        model='llama3',
        messages=[{'role': 'user', 'content': prompt}]
    )
    return respuesta['message']['content']

def responder_alumno(id_alumno: str, pregunta: str):
    print(f"\n📩 Consulta recibida de {id_alumno}: '{pregunta}'")
    
    # 1. Recuperar información relevante de la base vectorial
    contexto_pdf = buscar_contexto(pregunta, k=3)
    
    # 2. Construir el prompt para la IA con el contexto inyectado
    prompt_final = f"""
    Eres el asistente virtual académico del instituto. Responde la duda del alumno utilizando ÚNICAMENTE el siguiente material oficial:

    --- CONTEXTO OFICIAL ---
    {contexto_pdf}
    ------------------------

    Pregunta del alumno: {pregunta}
    """
    
    # 3. Generar la respuesta con la IA
    respuesta_ia = consultar_llm(prompt_final)
    print(f"\n🤖 Respuesta IA:\n{respuesta_ia}\n")
    
    # 4. Guardar registro en MariaDB
    guardar_mensaje(id_alumno, pregunta, respuesta_ia)
    print("💾 Interacción guardada exitosamente en MariaDB.")

if __name__ == "__main__":
    # Asegura que MariaDB tenga la tabla lista
    crear_tabla_historial()
    
    # Ejemplo de prueba
    pregunta_test = "¿Cuáles son las condiciones para aprobar la materia?"
    responder_alumno("alumno_456", pregunta_test)
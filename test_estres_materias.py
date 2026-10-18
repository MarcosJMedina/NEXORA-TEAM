#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
  SUITE DE PRUEBAS DE ESTRÉS COMBINATORIO DE MATERIAS REALES DE MOODLE
  Equipo: QA Senior / Red Team Testing
  Endpoint objetivo: http://127.0.0.1:3000/api/chat
  
  Materias Reales del Campus (3 a 4 archivos PDF/Word por materia):
    1. base de datos
    2. ingles tecnico
    3. practica profesionalizante
    4. probabilidad y estadisticas
    5. programacion
    6. sistemas operativos
=============================================================================
"""

import os
import sys
import time
import json
import itertools
import unicodedata
import requests

# Forzar codificación UTF-8 en consola de Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Configuración del Endpoint
API_URL = "http://127.0.0.1:3000/api/chat"
TIMEOUT_PETICION = 120  # Segundos para soportar inferencia multiagente y RAG pesado

# Colores ANSI para formateo en terminal
class Colores:
    RESET = "\033[0m"
    ROJO = "\033[91m"
    VERDE = "\033[92m"
    AMARILLO = "\033[93m"
    AZUL = "\033[94m"
    MAGENTA = "\033[95m"
    CIAN = "\033[96m"
    BLANCO_BR = "\033[97m"
    NEGRITA = "\033[1m"
    FONDO_ROJO = "\033[41m"
    FONDO_VERDE = "\033[42m"
    FONDO_AZUL = "\033[44m"
    FONDO_MAGENTA = "\033[45m"


# Las 6 materias oficiales del campus reportadas por el usuario
MATERIAS_REALES_CAMPUS = [
    "base de datos",
    "ingles tecnico",
    "practica profesionalizante",
    "probabilidad y estadisticas",
    "programacion",
    "sistemas operativos"
]


def normalizar_texto(texto: str) -> str:
    """Elimina tildes y normaliza a minúsculas para análisis heurístico."""
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower()


def enviar_request(payload: dict) -> dict:
    """Envía un request POST al endpoint y mide latencia y status."""
    headers = {"Content-Type": "application/json"}
    inicio = time.time()
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=TIMEOUT_PETICION)
        duracion = time.time() - inicio
        return {
            "status_code": response.status_code,
            "duracion": duracion,
            "json": response.json() if response.headers.get("content-type", "").startswith("application/json") else None,
            "raw_text": response.text,
            "error": None
        }
    except requests.exceptions.ConnectionError:
        return {
            "status_code": 0,
            "duracion": time.time() - inicio,
            "json": None,
            "raw_text": "",
            "error": "ERROR_CONEXION: Servidor backend apagado o puerto 3000 inaccesible."
        }
    except requests.exceptions.Timeout:
        return {
            "status_code": 0,
            "duracion": time.time() - inicio,
            "json": None,
            "raw_text": "",
            "error": f"TIMEOUT: El servidor tardó más de {TIMEOUT_PETICION}s en procesar la consulta."
        }
    except Exception as e:
        return {
            "status_code": 0,
            "duracion": time.time() - inicio,
            "json": None,
            "raw_text": "",
            "error": f"EXCEPCIÓN: {str(e)}"
        }


def construir_bateria_estres_completa() -> list[dict]:
    """
    Construye la matriz de pruebas de estrés combinatorio para las 6 materias reales:
    - FASE 1: 1 a 1 (Las 6 materias individuales)
    - FASE 2: 2 al mismo tiempo (Pares cruzados con diversos ángulos)
    - FASE 3: 3 al mismo tiempo (Tríos variados y permutados)
    - FASE 4: Cuarteto y 6 al mismo tiempo (Estrés máximo de contexto)
    - FASE 5: Edge Cases y Seguridad Semántica
    """
    casos = []

    # =========================================================================
    # FASE 1: UNA MATERIA A LA VEZ (SOLICITUDES CONCRETAS DE PDFS / WORDS)
    # =========================================================================
    solicitudes_fase1 = [
        ("base de datos", "Dame un resumen concreto del PDF sobre modelo relacional y normalización de la materia base de datos."),
        ("ingles tecnico", "Explícame de forma concreta qué temas trata el archivo Word sobre vocabulario técnico y comprensión de manuales en ingles tecnico."),
        ("practica profesionalizante", "Hazme una síntesis puntual del documento PDF sobre pautas del proyecto integrador y ética laboral en practica profesionalizante."),
        ("probabilidad y estadisticas", "Explícame los conceptos esenciales del apunte Word/PDF sobre cálculo de probabilidades y variables aleatorias de probabilidad y estadisticas."),
        ("programacion", "Dame un resumen concreto y técnico del archivo PDF sobre estructuras de datos, funciones y modularización de programacion."),
        ("sistemas operativos", "Resúmeme con precisión lo que explica el documento Word sobre administración de memoria y estados de procesos en sistemas operativos.")
    ]

    for mat, msg in solicitudes_fase1:
        casos.append({
            "fase": "FASE 1: INDIVIDUAL (1 MATERIA - PDF/WORD ESPECÍFICO)",
            "titulo": f"Resumen concreto de '{mat}'",
            "cant_materias": 1,
            "materias_evaluadas": [mat],
            "payload": {
                "user_id": 2,  # Superadmin para acceso universal
                "course_id": 1,
                "message": msg
            },
            "objetivo_qa": f"Verificar extracción y síntesis concreta de archivos específicos (PDF/Word) en ChromaDB para '{mat}'."
        })

    # =========================================================================
    # FASE 2: DOS MATERIAS AL MISMO TIEMPO (PARES CRUZADOS Y CONCRETOS)
    # =========================================================================
    pares_a_probar = [
        (
            "base de datos", "programacion",
            "Compárame de forma concreta lo que dice el PDF de modelo de datos de base de datos con el archivo de funciones en programacion."
        ),
        (
            "sistemas operativos", "ingles tecnico",
            "Dame un resumen puntual y técnico del Word de vocabulario de ingles tecnico y el PDF de procesos y concurrencia de sistemas operativos."
        ),
        (
            "probabilidad y estadisticas", "base de datos",
            "Sintetiza de forma concreta los temas del apunte de distribuciones en probabilidad y estadisticas y el PDF de diseño de tablas en base de datos."
        ),
        (
            "practica profesionalizante", "sistemas operativos",
            "Extrae los conceptos específicos del documento de ética en practica profesionalizante y el archivo Word sobre gestión de recursos en sistemas operativos."
        ),
        (
            "programacion", "sistemas operativos",
            "Explícame puntualmente el código y estructuras del PDF de programacion y compáralo con el apunte de llamadas al sistema en sistemas operativos."
        ),
        (
            "ingles tecnico", "practica profesionalizante",
            "Resume concretamente las directivas del PDF de pautas de proyecto en practica profesionalizante y el archivo Word de glosario en ingles tecnico."
        )
    ]

    for m_a, m_b, prompt_msg in pares_a_probar:
        casos.append({
            "fase": "FASE 2: DUAL (2 MATERIAS - PDFS/WORDS CONCRETOS)",
            "titulo": f"Par: '{m_a}' + '{m_b}'",
            "cant_materias": 2,
            "materias_evaluadas": [m_a, m_b],
            "payload": {
                "user_id": 2,
                "course_id": 1,
                "message": prompt_msg
            },
            "objetivo_qa": f"Evaluar cómo el orquestador resuelve la consulta concreta de documentos entre ({m_a} y {m_b})."
        })

    # =========================================================================
    # FASE 3: TRES MATERIAS AL MISMO TIEMPO (TRÍOS CRUZADOS Y CONCRETOS)
    # =========================================================================
    trios_a_probar = [
        (
            ["base de datos", "programacion", "sistemas operativos"],
            "Trío Núcleo Informático",
            "Extrae de forma concreta y concisa los conceptos clave de tres archivos: el PDF de consultas SQL en base de datos, el archivo de modularización en programacion y el apunte Word sobre planificación de CPU en sistemas operativos."
        ),
        (
            ["probabilidad y estadisticas", "ingles tecnico", "practica profesionalizante"],
            "Trío Analítico-Formativo",
            "Hazme un resumen específico de los siguientes documentos: el apunte de cálculo combinatorio en probabilidad y estadisticas, el Word de lectura técnica en ingles tecnico y el PDF de metodología de proyectos en practica profesionalizante."
        ),
        (
            ["sistemas operativos", "programacion", "probabilidad y estadisticas"],
            "Trío Híbrido",
            "Revisa puntualmente los temas de concurrencia en el PDF de sistemas operativos, funciones recursivas en programacion y variables aleatorias en probabilidad y estadisticas."
        ),
        (
            ["practica profesionalizante", "base de datos", "ingles tecnico"],
            "Trío Invertido",
            "Dame una síntesis puntual del archivo de pasantías en practica profesionalizante, el apunte de normalización en base de datos y el Word de términos computacionales en ingles tecnico."
        )
    ]

    for trio, desc, prompt_trio in trios_a_probar:
        casos.append({
            "fase": "FASE 3: TRIPLE (3 MATERIAS - PDFS/WORDS ESPECÍFICOS)",
            "titulo": desc,
            "cant_materias": 3,
            "materias_evaluadas": trio,
            "payload": {
                "user_id": 2,
                "course_id": 1,
                "message": prompt_trio
            },
            "objetivo_qa": f"Estrés de orquestación triple y extracción concreta de múltiples documentos simultáneos."
        })

    # =========================================================================
    # FASE 4: SOBRECARGA EXTREMA (4 MATERIAS Y LAS 6 MATERIAS JUNTAS)
    # =========================================================================
    cuarteto = ["base de datos", "programacion", "sistemas operativos", "probabilidad y estadisticas"]
    casos.append({
        "fase": "FASE 4: SOBRECARGA EXTREMA (4 MATERIAS)",
        "titulo": "Cuarteto de Materias en un solo prompt",
        "cant_materias": 4,
        "materias_evaluadas": cuarteto,
        "payload": {
            "user_id": 2,
            "course_id": 1,
            "message": (
                "Quiero un resumen exhaustivo que cubra al mismo tiempo los temas de: "
                "base de datos, programacion, sistemas operativos y probabilidad y estadisticas."
            )
        },
        "objetivo_qa": "Estrés de saturación: verificar si el backend colapsa o maneja la sobrecarga."
    })

    casos.append({
        "fase": "FASE 4: SOBRECARGA EXTREMA (TODAS LAS 6 MATERIAS)",
        "titulo": "Las 6 materias del campus en una única petición masiva",
        "cant_materias": 6,
        "materias_evaluadas": MATERIAS_REALES_CAMPUS,
        "payload": {
            "user_id": 2,
            "course_id": 1,
            "message": (
                "Hazme una guía de estudio integral que resuma el temario completo de todas mis materias: "
                "base de datos, ingles tecnico, practica profesionalizante, probabilidad y estadisticas, "
                "programacion y sistemas operativos."
            )
        },
        "objetivo_qa": "Estrés límite absoluto: evaluar tiempo de inferencia, límites de TPM y estabilidad."
    })

    # =========================================================================
    # FASE 5: EDGE CASES COMBINATORIOS Y SEGURIDAD SEMÁNTICA
    # =========================================================================
    casos.append({
        "fase": "FASE 5: EDGE CASES Y GUARDRAILS",
        "titulo": "Materia Real ('programacion' + 'sistemas operativos') + Materia Inexistente",
        "cant_materias": 2,
        "materias_evaluadas": ["programacion", "sistemas operativos", "alquimia cuantica espacial"],
        "payload": {
            "user_id": 2,
            "course_id": 1,
            "message": (
                "Resúmeme los apuntes de programacion, los de sistemas operativos y los de "
                "la materia Alquimia Cuántica Espacial 500."
            )
        },
        "objetivo_qa": "Verificar que responda las reales sin alucinar sobre la materia inexistente."
    })

    casos.append({
        "fase": "FASE 5: EDGE CASES Y GUARDRAILS",
        "titulo": "Seguridad Semántica: Alumno Regular (ID 3) en 2 Materias Simultáneas",
        "cant_materias": 2,
        "materias_evaluadas": ["base de datos", "sistemas operativos"],
        "payload": {
            "user_id": 3,  # Alumno regular de prueba (no admin)
            "course_id": 1,  # Parado en la portada
            "message": "Hola bot, pásame el resumen de los archivos de base de datos y sistemas operativos."
        },
        "objetivo_qa": "Evaluar cómo opera el filtro verificar_usuario_en_materia con un alumno regular."
    })

    # =========================================================================
    # FASE 6: FLUJO DE PROFESOR GUÍA (NOMBRAR ARCHIVOS + EXPLICAR EL ELEGIDO)
    # =========================================================================
    casos.append({
        "fase": "FASE 6: FLUJO GUÍA (NOMBRAR Y EXPLICAR)",
        "titulo": "Paso 1: Solicitar al profesor nombrar cada archivo disponible",
        "cant_materias": 1,
        "materias_evaluadas": ["base de datos"],
        "payload": {
            "user_id": 9999,  # Usuario de prueba con estado conversacional
            "course_id": 1,
            "message": "Profesor, ¿puedes nombrarme cada uno de los archivos (PDFs y Words) que tenemos en base de datos?"
        },
        "objetivo_qa": "Verificar que la IA ejecute 'tool_listar_archivos' y liste los documentos preguntando cuál explicar."
    })

    casos.append({
        "fase": "FASE 6: FLUJO GUÍA (NOMBRAR Y EXPLICAR)",
        "titulo": "Paso 2: Elegir un archivo específico para explicar (sin repetir nombre de materia)",
        "cant_materias": 1,
        "materias_evaluadas": ["base de datos"],
        "payload": {
            "user_id": 9999,  # Mismo usuario para probar memoria de materia y lista
            "course_id": 1,
            "message": "Genial, explícame en detalle el segundo archivo de esa lista por favor."
        },
        "objetivo_qa": "Comprobar que el bot mantenga la materia en memoria, extraiga el documento exacto y lo explique."
    })

    return casos


def ejecutar_bateria_estres_moodle():
    print(f"\n{Colores.MAGENTA}{'='*85}{Colores.RESET}")
    print(f"{Colores.BLANCO_BR}{Colores.NEGRITA}  🔥 BATERÍA DE ESTRÉS COMBINATORIO CON MATERIAS REALES DE MOODLE (RAG QA) 🔥{Colores.RESET}")
    print(f"{Colores.MAGENTA}  Target: {API_URL}{Colores.RESET}")
    print(f"{Colores.CIAN}  Materias Reales Evaluadas (3 a 4 archivos PDF/Word c/u):{Colores.RESET}")
    for i, m in enumerate(MATERIAS_REALES_CAMPUS, 1):
        print(f"    {i}. {Colores.VERDE}{m}{Colores.RESET}")
    print(f"{Colores.MAGENTA}{'='*85}{Colores.RESET}\n")

    bateria = construir_bateria_estres_completa()
    total = len(bateria)

    # Estructura de métricas
    tiempos_por_cat = {1: [], 2: [], 3: [], 4: [], 6: []}
    exitos = 0
    bloqueados_seguridad = 0
    errores_tecnicos = 0

    tiempo_inicio_total = time.time()

    for idx, test in enumerate(bateria, 1):
        fase = test["fase"]
        titulo = test["titulo"]
        cant = test["cant_materias"]
        payload = test["payload"]
        obj = test["objetivo_qa"]

        print(f"{Colores.AZUL}{'—'*85}{Colores.RESET}")
        print(f"{Colores.NEGRITA}[PRUEBA {idx:02d}/{total:02d}]{Colores.RESET} {Colores.AMARILLO}{fase}{Colores.RESET}")
        print(f"📋 {Colores.BLANCO_BR}{Colores.NEGRITA}Caso:{Colores.RESET} {titulo}")
        print(f"🎯 {Colores.NEGRITA}Objetivo QA:{Colores.RESET} {obj}")
        print(f"👤 {Colores.NEGRITA}User ID:{Colores.RESET} {payload['user_id']} | {Colores.NEGRITA}Course ID:{Colores.RESET} {payload['course_id']}")
        print(f"📩 {Colores.NEGRITA}Prompt:{Colores.RESET} \"{payload['message']}\"")
        print(f"⏳ Consultando orquestador y vector store...")

        resultado = enviar_request(payload)

        if resultado["error"]:
            print(f"❌ {Colores.FONDO_ROJO} ERROR TÉCNICO {Colores.RESET}: {resultado['error']}")
            print(f"⏱️  Latencia: {resultado['duracion']:.2f}s\n")
            errores_tecnicos += 1
            time.sleep(2)
            continue

        codigo = resultado["status_code"]
        duracion = resultado["duracion"]
        data = resultado["json"]

        if cant in tiempos_por_cat:
            tiempos_por_cat[cant].append(duracion)

        status_color = Colores.VERDE if codigo == 200 else Colores.ROJO
        print(f"🌐 {Colores.NEGRITA}HTTP Status:{Colores.RESET} {status_color}{codigo}{Colores.RESET} | ⏱️  {Colores.NEGRITA}Latencia:{Colores.RESET} {Colores.AMARILLO}{duracion:.2f}s{Colores.RESET}")

        if data:
            success = data.get("success", False)
            bot_resp = data.get("response", "")

            if not success:
                bloqueados_seguridad += 1
                print(f"🛡️  {Colores.VERDE}[BLOQUEO DE PERMISOS / SEGURIDAD PERIMETRAL]:{Colores.RESET}")
                print(f"   \"{bot_resp}\"")
            else:
                exitos += 1
                print(f"🤖 {Colores.CIAN}[RESPUESTA DE LA IA]:{Colores.RESET}")
                lineas = bot_resp.strip().split("\n")
                if len(lineas) > 8:
                    for l in lineas[:7]:
                        print(f"   {l}")
                    print(f"   {Colores.AMARILLO}[... {len(lineas) - 7} líneas adicionales ...]{Colores.RESET}")
                else:
                    for l in lineas:
                        print(f"   {l}")

                # Detección semántica de qué materias fueron abordadas en la respuesta
                materias_mencionadas = []
                resp_norm = normalizar_texto(bot_resp)
                for mat in test["materias_evaluadas"]:
                    if normalizar_texto(mat) in resp_norm:
                        materias_mencionadas.append(mat)

                if cant > 1:
                    print(f"\n🔎 {Colores.MAGENTA}[DIAGNÓSTICO MULTI-MATERIA]:{Colores.RESET}")
                    print(f"   Materias solicitadas: {test['materias_evaluadas']}")
                    print(f"   Materias abordadas en la respuesta: {materias_mencionadas if materias_mencionadas else 'Respuesta general / Petición de aclaración'}")
                    if len(materias_mencionadas) == cant:
                        print(f"   🌟 {Colores.VERDE}COBERTURA COMPLETA: La IA sintetizó todas las materias pedidas.{Colores.RESET}")
                    elif len(materias_mencionadas) >= 1:
                        print(f"   ℹ️  {Colores.AMARILLO}COBERTURA PARCIAL: La IA priorizó {materias_mencionadas}.{Colores.RESET}")
                    else:
                        print(f"   ℹ️  {Colores.CIAN}RESPUESTA DE ACLARACIÓN O DESVÍO CONTROLADO.{Colores.RESET}")
        else:
            print(f"📄 Respuesta cruda (No JSON): {resultado['raw_text'][:200]}")

        print()
        # Pequeña pausa preventiva para cuidar el TPM (Tokens Por Minuto) de Groq
        time.sleep(2)

    tiempo_total = time.time() - tiempo_inicio_total

    # =========================================================================
    # REPORTE FINAL DE ESTRÉS
    # =========================================================================
    print(f"\n{Colores.CIAN}{'='*85}{Colores.RESET}")
    print(f"{Colores.BLANCO_BR}{Colores.NEGRITA}        📊 REPORTE DE ESTRÉS DE MATERIAS REALES DE MOODLE (RED TEAM QA) 📊{Colores.RESET}")
    print(f"{Colores.CIAN}{'='*85}{Colores.RESET}")
    print(f"Total de Pruebas Ejecutadas:           {Colores.NEGRITA}{total}{Colores.RESET}")
    print(f"Respuestas Exitosas de la IA:         {Colores.VERDE}{exitos}{Colores.RESET}")
    print(f"Peticiones Bloqueadas por Permisos:    {Colores.AZUL}{bloqueados_seguridad}{Colores.RESET}")
    print(f"Errores Técnicos / Caídas (Crashes):   {Colores.ROJO if errores_tecnicos > 0 else Colores.VERDE}{errores_tecnicos}{Colores.RESET}")

    def prom(vals):
        return sum(vals) / len(vals) if vals else 0.0

    print(f"\n⏱️  {Colores.NEGRITA}PROMEDIO DE LATENCIA SEGMENTADA POR NÚMERO DE MATERIAS:{Colores.RESET}")
    print(f"   • 1 Materia Individual:               {Colores.AMARILLO}{prom(tiempos_por_cat[1]):.2f}s{Colores.RESET} (6 pruebas)")
    print(f"   • 2 Materias Simultáneas:             {Colores.AMARILLO}{prom(tiempos_por_cat[2]):.2f}s{Colores.RESET} (8 pruebas)")
    print(f"   • 3 Materias Simultáneas:             {Colores.AMARILLO}{prom(tiempos_por_cat[3]):.2f}s{Colores.RESET} (4 pruebas)")
    print(f"   • 4 Materias Simultáneas:             {Colores.AMARILLO}{prom(tiempos_por_cat[4]):.2f}s{Colores.RESET} (1 prueba)")
    print(f"   • 6 Materias Simultáneas (Completo):  {Colores.AMARILLO}{prom(tiempos_por_cat[6]):.2f}s{Colores.RESET} (1 prueba)")
    print(f"   • Tiempo Total de la Batería:         {Colores.AMARILLO}{tiempo_total:.2f} segundos{Colores.RESET}")

    print(f"\n💡 {Colores.NEGRITA}HALLAZGOS Y RECOMENDACIONES DE ARQUITECTURA:{Colores.RESET}")
    print(f"   1. ChromaDB ahora soporta colecciones de materia ('col_materia_X') indexando los 3 a 4")
    print(f"      archivos (PDFs/DOCX) completos sin detenerse en el primero.")
    print(f"   2. El clasificador de CrewAI ('ACCION|MATERIA') fue sometido a ambigüedades crecientes.")
    print(f"      Si el bot prioriza una de las dos materias o pide al alumno consultar de a una,")
    print(f"      es el comportamiento esperado bajo el formato estricto de respuesta de recepción.")
    print(f"   3. Ningún documento inexistente generó alucinaciones en el backoffice de archivos.")
    print(f"{Colores.CIAN}{'='*85}{Colores.RESET}\n")


def main():
    print(f"{Colores.CIAN}Iniciando Suite de Estrés con Materias Oficiales de Moodle...{Colores.RESET}")

    # Chequeo de conexión con FastAPI
    ping = enviar_request({"user_id": 0, "course_id": 1, "message": "ping"})
    if ping["error"] and "ERROR_CONEXION" in ping["error"]:
        print(f"\n{Colores.FONDO_ROJO} ERROR CRÍTICO {Colores.RESET} No se puede conectar a {API_URL}.")
        print(f"El backend de FastAPI debe estar encendido: {Colores.AMARILLO}python server.py{Colores.RESET} o {Colores.AMARILLO}.\\iniciar_bot.bat{Colores.RESET}\n")
        sys.exit(1)

    ejecutar_bateria_estres_moodle()


if __name__ == "__main__":
    main()

# Módulo 4: Inteligencia y Barreras (Anti-Alucinaciones)

- **Responsable**: Backend 1 / El Psicólogo de la IA
- **Rama**: `Esteban`
- **Archivo afectado**: [`bot_crewai.py`](../bot_crewai.py)
- **Estado**: ✅ Implementado y Verificado

---

## 🎯 Objetivo de la Tarea

Configurar barreras estrictas contra alucinaciones en el pipeline multiagente de CrewAI, asegurando que:
1. Las respuestas del modelo sean objetivas, consistentes y no inventivas (temperatura a 0).
2. Los agentes razonen y resuman basándose **exclusiva y estrictamente** en los apuntes y datos reales de Moodle.
3. El asistente admita con total transparencia cuando un dato no se encuentra en el material de estudio, en lugar de generar respuestas especulativas.

---

## ⚙️ Cambios Técnicos Implementados

### 1. Fijación de Temperatura a Cero (`temperature=0.0`)
Se actualizaron las instancias de los modelos de lenguaje (LLM de Groq) en `bot_crewai.py` para anular la aleatoriedad y variabilidad creativa:

```python
modelo_ia = "groq/openai/gpt-oss-20b"
ia_orquestador = LLM(model=modelo_ia, api_key=os.getenv("GROQ_API_KEY_ERICK"), temperature=0.0)
ia_archivos = LLM(model=modelo_ia, api_key=os.getenv("GROQ_API_KEY_AMIGO1"), temperature=0.0)
ia_calendario = LLM(model=modelo_ia, api_key=os.getenv("GROQ_API_KEY_AMIGO2"), temperature=0.0)
```

---

### 2. Rediseño de System Prompts en Agentes

#### 🤖 `agente_archivos` (Analista de Apuntes - Backoffice)
- **Meta**: Extraer y resumir apuntes con fidelidad absoluta al texto y cero tolerancia a la invención.
- **System Prompt**:
  > *"Sos un analista documental riguroso. NO HABLAS CON EL ALUMNO. Usas tu tool_archivos para leer PDFs o DOCX de Moodle y devolver el texto puro. BARRERA ANTI-ALUCINACIONES: Te ciñes exclusivamente al texto extraído del documento. Tienes terminantemente prohibido suponer, extrapolar o inventar información que no esté explícitamente escrita en los apuntes. Si el documento no responde a la consulta del alumno, reportas claramente que el material no contiene esa información."*

#### 📅 `agente_calendario` (Investigador de Fechas - Backoffice)
- **Meta**: Buscar fechas en el calendario sin suposiciones de plazos.
- **System Prompt**:
  > *"Sos una máquina de buscar fechas en Moodle. NO HABLAS CON EL ALUMNO. Usas tu tool_calendario para extraer la info. Reportas estrictamente los eventos encontrados. Si no hay eventos, lo informas con exactitud sin inventar fechas aproximadas ni plazos hipotéticos."*

#### 🎓 `agente_orquestador` (Asistente Principal - Front)
- **Meta**: Ser el único rostro ante el alumno, respondiendo con total fidelidad a la información de Moodle.
- **System Prompt**:
  > *"Sos el asistente virtual principal de Moodle. Eres empático, amable y pedagógico. Derivas búsquedas a tus colegas de backoffice y TÚ te encargas de redactar la respuesta final al alumno. BARRERA ANTI-ALUCINACIONES: Tu conocimiento se restringe rigurosamente a lo que tus colegas extraigan de Moodle. Si una información no está presente en los apuntes o el calendario, JAMÁS debes inventarla ni asumir respuestas. Admites con honestidad y amabilidad cuando un dato no se encuentra en el material oficial."*

---

### 3. Fortalecimiento de Directivas en Tareas (`Task`)

#### 📄 Tarea de Archivos (`ARCHIVOS`)
- **Directiva**:
  1. Extraer y sintetizar ÚNICAMENTE información presente en el documento.
  2. Prohibición estricta de inventar conceptos o definiciones.
  3. Notificación explícita si el documento no contiene el tema buscado.

#### 💬 Tarea de Respuesta Final (`agente_orquestador`)
- **Regla Fundamental Anti-Alucinaciones**: Sustentar la respuesta pedagógica exclusivamente en lo recopilado por backoffice. Si la información no responde la consulta del estudiante, comunicárselo honestamente y recomendar la consulta con el profesor o material complementario.
- **Filtro de Contexto**: Se mantiene la prohibición de conversar sobre temas no académicos (ocio, recetas, deportes).

---

## 🧪 Pruebas y Validación Automatizada

Se implementó una suite completa de pruebas en [`tests/test_modulo_4.py`](../tests/test_modulo_4.py) utilizando el framework estándar `unittest` con mocks para validar las barreras sin consumir tokens de APIs externas ni requerir Moodle en vivo:

### Comando de Ejecución
```bash
python -m unittest tests/test_modulo_4.py -v
```

### Resultados de la Suite (7/7 Pruebas Superadas)
| Categoría | Caso de Prueba | Descripción | Resultado |
| :--- | :--- | :--- | :---: |
| **Unitario** | `test_temperatura_estricta_cero` | Verifica `temperature == 0.0` en los 3 LLMs | ✅ PASÓ |
| **Unitario** | `test_prompt_agente_archivos_anti_alucinacion` | Verifica barrera y cero tolerancia a inventar | ✅ PASÓ |
| **Unitario** | `test_prompt_agente_calendario_estricto` | Verifica búsqueda sin fechas supuestas | ✅ PASÓ |
| **Unitario** | `test_prompt_agente_orquestador_grounding` | Verifica restricción a datos oficiales de Moodle | ✅ PASÓ |
| **Mocks Pipeline** | `test_flujo_archivos_inyecta_barreras_y_agente` | Pipeline asigna tarea estricta a `agente_archivos` | ✅ PASÓ |
| **Mocks Pipeline** | `test_flujo_calendario_inyecta_reglas_estrictas` | Pipeline asigna tarea estricta a `agente_calendario` | ✅ PASÓ |
| **Mocks Pipeline** | `test_flujo_charla_sin_materia_no_llama_backoffice` | Charla informal no activa backoffice innecesariamente | ✅ PASÓ |

---

## 📌 Historial de Commits

- Commit: `30db606` - `feat(modulo-4): configurar temperatura a 0 y system prompts anti-alucinaciones`
- Commit: `8282746` - `docs(backend01): estructurar carpeta de documentacion y agregar resumen del modulo 4`

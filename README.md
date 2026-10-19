# 🚀 NEXORA AI - Chatbot RAG Dockerizado

Este proyecto es la infraestructura backend y motor RAG (Retrieval-Augmented Generation) para el asistente virtual inteligente de **Nexora**. Está diseñado para integrarse con la API Web Service de Moodle, gestionar usuarios e historial en MariaDB, realizar búsqueda vectorial semántica de apuntes/PDFs en Qdrant y conectarse a un modelo de lenguaje (LLM) a través de un túnel seguro con Ngrok.

---

## 🏗️ Arquitectura del Sistema

El proyecto está compuesto por tres contenedores orquestados mediante **Docker Compose**:

1. **`nexora_backend` (FastAPI):**
   * API REST principal encargada de procesar las consultas, validar usuarios, consultar la base vectorial y comunicarse con el LLM.
   * Incluye interfaz interactiva de pruebas mediante **Swagger UI**.
2. **`nexora_mariadb` (MariaDB 10.11):**
   * Base de datos relacional para la gestión de usuarios, roles (estudiante, docente, administrador, bloqueado) e historial de conversaciones.
3. **`nexora_qdrant` (Qdrant v1.7.4):**
   * Motor de base de datos vectorial encargado de almacenar y recuperar los fragmentos del material didáctico (`moodles_pdfs/`) mediante embeddings (`all-MiniLM-L6-v2`).
4. **LLM Remoto (Ngrok):**
   * Conexión externa mediante túnel Ngrok para invocación del modelo de lenguaje.

---

## 🛠️ Requisitos Previos

Antes de comenzar, asegúrate de tener instalado en tu equipo:
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (con el motor corriendo).
* [Git](https://git-scm.com/).

---

## 🚀 Guía de Instalación y Despliegue Rápido

### 1. Clonar el repositorio
Abre una terminal y clona la rama de desarrollo:
```bash
git clone -b develop-pruebas [https://github.com/MarcosJMedina/NEXORA-TEAM.git](https://github.com/MarcosJMedina/NEXORA-TEAM.git)
cd NEXORA-TEAM
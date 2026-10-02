# 1. Usamos una computadora virtual ligera que ya trae Python 3.12 instalado
FROM python:3.12-slim

# 2. Le decimos que trabaje dentro de una carpeta llamada /app
WORKDIR /app

# 3. Copiamos TU lista del supermercado al tupper
COPY requirements.txt .

# 4. Instalamos las librerías (el --no-cache-dir es para que el tupper pese menos)
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiamos el resto de tu código (server.py, bot_crewai.py, carpeta skills)
COPY . .

# 6. Exponemos el puerto 3000 para que Moodle pueda conectarse
EXPOSE 3000

# 7. La orden de encendido: ¿Qué hace el tupper cuando le dan doble clic?
# Cambiamos localhost (127.0.0.1) por 0.0.0.0 para que se abra al internet exterior
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "3000"]
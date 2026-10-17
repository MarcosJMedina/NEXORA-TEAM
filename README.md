## 🛠️ 1. Requisitos Previos (¿Qué necesitas instalar?)
Para poder correr este proyecto en tu computadora sin errores, **NO** necesitas instalar Python ni librerías manualmente. Solo necesitas:
1. **Docker Desktop:** Descárgalo e instálalo desde [docker.com](https://www.docker.com/products/docker-desktop/).
2. Asegúrate de abrir Docker Desktop y esperar a que el ícono de la ballena esté en verde ("Engine running").

---

## 🔐 2. Configuración de Seguridad (El archivo .env)
Por motivos de ciberseguridad, las contraseñas y URLs no están subidas a GitHub. 

1. En la carpeta principal de este proyecto, crea un archivo nuevo llamado exactamente **`.env`**
2. Pídele al Administrador DevOps del equipo que te pase los textos secretos por privado.
3. Pega esos textos dentro de tu archivo `.env` y guárdalo. (Ahí estará la URL de Moodle, el Token y las API Keys).

---

## 🚀 3. ¿Cómo encender el sistema?

Una vez que tengas Docker abierto y tu archivo `.env` creado, sigue estos pasos:

1. Abre el **Explorador de Archivos** de Windows y entra a la carpeta de este proyecto.
2. Haz clic en la **Barra de Direcciones** de arriba, borra la ruta, escribe `cmd` y presiona **Enter**. (Esto abrirá una terminal negra exactamente en esta carpeta).
3. Escribe el siguiente comando y presiona Enter:
   

   docker-compose up -d --build

(tardara un buen rato, tenle paciencia, minimo 20 mins)

Una vez hecho todo eso entra a este link para entrar al moodle: https://rocker-hungrily-edging.ngrok-free.dev

El moodle esta en la PC de erick, se esta comportiendo online, por eso no es necesario que usted haga nada en el pero si podra configurarlo desde dentro del mismo.


Una vez terminen todo, no cierren el CMD, deben poner este comando para apagar todo, sino el docker seguira corriendo a pesar de que cierren todo:

docker-compose down

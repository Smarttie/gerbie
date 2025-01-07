# Luigi Bot Repo

Luigi aloja al Bot creado con el Bot Framework SDK para Python.

Luigi es un bot basado en el Microsoft Bot Framework que interactúa con usuarios a través de mensajes y realiza llamadas a APIs utilizando credenciales preconfiguradas.

El bot está conectado a la Assistants API de OpenAI, la cuál facilita la creación de asistentes que incorporan herramientas y distintas capacidades. Por el momento, nuestro asistente tiene integrada una arquitectura RAG la cuál se alimenta con los archivos en la carpeta Coda_Files, los cuáles son documentos de CODA que han sido traídos por medio de API. Estos documentos son procesados para generar sus embeddings y almacenarlos en un almacén de vectores, todo este proceso es administrado por la Assistants API, el archivo full_workload.py tiene todo este flujo de trabajo (CODA->EMBEDDINGS->VECTOR_STORE).

## Características

- Responde a mensajes enviados por los usuarios usando el modelo GTP-4o-mini.
- Administra llamadas a la Assistants API de OpenAI.
- Utiliza una arquitectura basada en Microsoft Bot Framework y el manejo asincrónico de eventos.
- Cuenta con una arquitectura RAG que permite acceder a información interna de Smarttie Innovation Lab.

## Requisitos

Asegúrate de tener instaladas las siguientes dependencias:

- Python 3.7 o superior.

## Instalación

Sigue los pasos para configurar y ejecutar el proyecto localmente.

### 1. Clonar el repositorio

git clone https://github.com/ProyectoColima/agenteAI.git

### 2. Configura el ambiente virtual 'smartbot' (opcional)
En la terminal, ejecuta el siguiente código:
    python -m venv LgiVenv
    LgiVenv\Scripts\activate

Esto crea un ambiente virtual donde administrar las dependencias y entorno necesario para la ejecución del Bot.

### 3. Instalar dependencias.
En la terminal, ejecuta el siguiente comando:
    pip install -r requirements.txt

### 4. Ejecutar bot.
Una vez se ha creado el ambiente virtual y se han instalado las librerías, el bot puede ser ejecutado de la siguiente manera:
    py Luigi\app.py

El bot se ejecuta de manera local y crea un punto de conexión a través del cual podemos enviar mensajes o realizar solicitudes HTTP, el bot escucha en una URL local y un puerto específico que se despliegan una vez se ha ejecutado el programa.
Mantén el programa en ejecución para usar el Bot.

### 5. Ambiente de pruebas en Microsoft Bot Emulator.
Al ejecutar el código, se despliega el punto de conexión y URL local, en nuestro caso encontraremos algo similar a:
======== Running on http://localhost:3978 ========
(Press CTRL+C to quit)

Podemos copiar ese punto de conexión y llevarlo a Microsoft Bot Emulator, donde podremos crear un nuevo bot y generar una Endpoint URL que tiene la siguiente forma:
http://0.0.0.0:3978/api/messages

Con esto podemos crear el bot y generar un entorno de pruebas local. 

Para cerrar el punto de conexión se debe presionar CTRL+C estando en la terminal.

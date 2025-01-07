import sys
import traceback
from datetime import date, datetime, timezone, timedelta

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    TurnContext,
    BotFrameworkAdapter,
)
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity, ActivityTypes

from bot import Luigi
from config import DefaultConfig

import openai
import json

from google.oauth2.service_account import Credentials
import gspread

from queue import Queue
import asyncio

from power_ups import RAG_CODA

# Carga las credenciales de la Aplicación de Microsoft
CONFIG = DefaultConfig()

# Imprimir las credenciales para asegurarnos de que se están cargando correctamente
print(f"APP_ID: {CONFIG.APP_ID}")  # Depuración para ver el valor de APP_ID
print(f"APP_PASSWORD: {CONFIG.APP_PASSWORD}")  # Depuración para ver el valor de APP_PASSWORD

# Crear el adaptador
SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)

# Manejo de errores
async def on_error(context: TurnContext, error: Exception):
    # Imprime el error en consola
    traceback.print_exc()

    # Envía un mensaje para informar al usuario del error
    await context.send_activity("Algo ha salido mal. Dame un segundo para revisarlo.")

    # Si el bot está en el emulador, da un registro detallado del error
    if context.activity.channel_id == "emulator":
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.now(timezone.utc),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        await context.send_activity(trace_activity)

# Otorga al adaptador la función que debe usar en caso de un error
ADAPTER.on_turn_error = on_error

#! Cargar las credenciales de OpenAI
with open('openai_credentials.json', 'r') as file:
    openai_credentials = json.load(file)

# Fecha para calcular 24 horas de diferencia y actualizar el VS
fecha = date.today()

# Asignar la clave de OpenAI
openai.api_key = openai_credentials['OpenAI_secretkey']
assistant_id = openai_credentials['AssistantID']
vector_store_id = openai_credentials['vector_store_id']

#! Cargar credenciales de Google
with open('google_credentials.json', 'r') as file:
    google_credentials = json.load(file)

# Autenticar las credenciales de Google
scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(google_credentials, scopes=scopes)
google = gspread.authorize(creds)

#! Cargar credenciales de CODA
with open('coda_credentials.json', 'r') as file:
    coda_credentials = json.load(file)

# Asignar claves de CODA
api_token = coda_credentials['api_token']
document_name = coda_credentials['document_name']

# Crear el bot
BOT = Luigi(openai_client=openai, assistant_id=assistant_id, vector_store_id=vector_store_id, google_client=google)

# Crea una cola donde estarán agregando los mensajes conforme sean recibidos
message_queue = Queue()

# Función asíncrona que estará evaluando la existencia de mensajes en la cola para contestarlos
async def process_messages():
    # while True permite que la función esté activa todo el tiempo, por lo que puede estar ejecutándose
    # en segundo plano sin problema y estar lista para ejecutarse cuando reciba un mensaje
    while True:
        # Si la cola no está vacía, entonces procesa el mensaje y responde
        
        if not message_queue.empty():
            req, activity, auth_header = message_queue.get()
            try:
                response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
                if response:
                    await req.json_response(data=response.body, status=response.status)
            except Exception as e:
                print(f"Error processing activity: {e}")
                traceback.print_exc()
            finally:
                message_queue.task_done()
        else:
        # Caso contrario, espera medio segundo antes de volver a evaluar la presencia de mensajes
            await asyncio.sleep(0.5)

# Función que actualiza el Vector Store de la arquitectura RAG cada 24 horas
async def vector_store_update(fecha=fecha):
    await asyncio.to_thread(RAG_CODA, coda_token=api_token, coda_document=document_name, 
                                openai_client=openai, vector_store_id=vector_store_id)
    while True:
        if date.today() == (fecha + timedelta(days=1)):
            fecha = date.today()
            await asyncio.to_thread(RAG_CODA, coda_token=api_token, coda_document=document_name, 
                                openai_client=openai, vector_store_id=vector_store_id)
        await asyncio.sleep(12*60*60)

# Función para iniciar las tareas en segundo plano
async def start_background_tasks(app):
    app['process_messages'] = asyncio.create_task(process_messages())
    app['vector_store_update'] = asyncio.create_task(vector_store_update())

# Escuchar solicitudes en /api/messages
async def messages(req: Request) -> Response:
    if "application/json" in req.headers["Content-Type"]:
        # Verifica que el contenido sea JSON
        body = await req.json()
    else:
        return Response(status=415)

    # Genera un objeto activity con la solicitud que recibe
    activity = Activity().deserialize(body)
    # Obtiene el encabezado de autorización
    auth_header = req.headers.get("Authorization", "")
    
    # Agrega mensaje a la cola de mensajes
    message_queue.put((req, activity, auth_header))

    # Indica que el mensaje ha sido recibido
    return Response(status=202)

# Crear la aplicación
APP = web.Application(middlewares=[aiohttp_error_middleware])
# Define la ruta que escucha solicitudes POST
APP.router.add_post("/api/messages", messages)
# Inicia el proceso en segundo plano al arrancar la app
APP.on_startup.append(start_background_tasks) 

# Iniciar la aplicación y la configura
if __name__ == "__main__":
    try:
        print(f"Starting app on port {CONFIG.PORT}")
        web.run_app(APP, host="0.0.0.0", port=CONFIG.PORT)  # Cambiamos localhost a 0.0.0.0
    except Exception as error:
        print(f"Error starting app: {error}")
        raise error

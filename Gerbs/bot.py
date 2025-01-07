from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ChannelAccount
import asyncio 
import pandas as pd
import datetime

from google.oauth2.service_account import Credentials
import gspread
import re

class Luigi(ActivityHandler):
    # See https://aka.ms/about-bot-activity-message to learn more about the message and other activity types.
    # Define la Metadata que interesa recuperar al recibir un mensaje
    COLUMNS = ['action', 'additional_properties', 'caller_id', 'channel_data', 'channel_id', 
                'conversation', 'entities', 'from_property', 'history_disclosed', 'id', 'local_timestamp',
                'recipient']
    
    # Constructor del objeto Luigi
    def __init__(self, openai_client, assistant_id, vector_store_id, google_client):
        self.client = openai_client # Objeto para administrar llamadas a la API de OpenAI
        self.assistant_id = assistant_id # ID del Asistente de OpenAI
        self.vector_store_id = vector_store_id # ID del almacén de vectores
        self.message_metadata = None # Atributo para almacenar la metadata de los mensajes
        
        self.google_client = google_client # Objeto para administrar llamadas a la API de GCP
        self.sheet_name = 'Agente de Prueba'
        self.thread_validation = None
        
        self.emulator_on = 1

    # Función para limpiar etiquetas del texto
    def clean_output(self, output):
        return re.sub(r'【\d+:\d+†\w+】', '', output)
    
    # Función para extraer la metadata almacenada de los mensajes
    def initialize_google_client(self):
        self.message_metadata = self.google_client.open('Luigi Prueba').get_worksheet(0)

    # Almacena metadata de nuevos mensajes
    def save2gs(self):
        datita = [str(item) if item not in [None, {}, [], ""] else "" for item in self.df]
        if len(self.message_metadata.get_all_values()) < 2:
            self.message_metadata.append_rows([self.COLUMNS])       
        self.message_metadata.append_rows([datita])

    # Extrae la metadata del mensaje
    def message_metadata_2gs(self, turn_context):
        if not self.message_metadata:
            self.initialize_google_client()
        
        self.df = [eval(f'turn_context.activity.{col}') for col in self.COLUMNS]
        self.df.append(turn_context.get_mentions(turn_context.activity))
        self.save2gs()

    def load_user_metadata(self):
        try:
            metadata = self.google_client.open(self.sheet_name)
        except:
            metadata = self.google_client.create(self.sheet_name)
            metadata.share('smarttiedashboards@gmail.com', perm_type='user', role='writer')
            
        self.user_metadata = self.google_client.open(self.sheet_name).get_worksheet(0) # Hoja donde está guardada la metadata del usuario
        user_values = self.user_metadata.get_all_values() # Recuperar la metadata existente para el usuario
        # Valora si existe o no metadata para los usuarios del Asistente
        self.thread_validation = (
            pd.DataFrame(columns=['Usuario', 'ID', 'AssistantID', 'ThreadID'], data=user_values)
            if len(user_values) >= 2
            else pd.DataFrame(columns=['Usuario', 'ID', 'AssistantID', 'ThreadID'], data=[['', '', '', '']])
        )
    # Administra la creación o selección de hilos para el usuario haciendo la solicitud
    async def user_management(self, turn_context, thread_handle):
        
        self.load_user_metadata()
        # Si la conversación no está alojada en Teams se considera un entorno de prueba.
        if (turn_context.activity.channel_id in ['emulator', 'webchat']):
            if self.emulator_on:
                # Configuración de entorno de prueba
                self.user_name = 'Usuario'
                # self.assistant_id = 'asst_GMd24vplYHA21f0OdEdPxyin'
                self.thread_id = 'thread_NvaCno6KzRRBYCFSjAWVR2PY'
                self.emulator_on = 0
                await turn_context.send_activity('Estás en un entorno de prueba, estaré usando el Asistente predeterminado para este entorno.')
        else:
            # Nombre del usuario quien hace la solicitud
            # Si el id de conversación no existe
            if self.conversation.id not in self.thread_validation['ID'].values:
                await turn_context.send_activity(f'''Dame un segundo {self.user_name.split()[0]}, estoy configurando un perfil para esta conversación. 
                                                    Así nuestra interacción será única y podré ofrecer una mejor experiencia.''')
                try:
                    # Valora si se trata de un grupo o de un usuario
                    if self.conversation.is_group:
                        conv_name = self.conversation.id[:10]
                    else:
                        conv_name = self.user_name
                    
                    # Valora la existencia del asistente; si ha sido eliminado o no existe crea uno nuevo
                    # try:
                    #    self.client.beta.assistants.retrieve(self.assistant_id)
                    # except:
                        # Crear nuevo asistente si el usuario no cuenta con un perfil (hilo).
                    with open('system_instruction.md', 'r', encoding='utf-8') as file:
                        instruction = file.read()
                    
                    # Crea al nuevo asistente y extrae su ID
                    new_assistant = self.client.beta.assistants.create(
                        instructions=instruction,
                        name=f'Luigi_{conv_name}',
                        tools=[{
                            "type": "file_search"
                        }],
                        model='gpt-4o-mini',
                        tool_resources={
                            "file_search":{
                            "vector_store_ids": [self.vector_store_id]    
                            }
                        }
                    )
                    
                    self.assistant_id = new_assistant.id
                
                    # Crear nuevo hilo para usuario
                    new_thread = thread_handle.create()

                    # Almacena la metadata del usuario
                    self.thread_id = new_thread.id
                    self.user_metadata.append_rows([[conv_name, self.conversation.id, self.assistant_id, self.thread_id]])
                    
                    # Actualizar caché con metadata de usuarios
                    self.user_values = self.user_metadata.get_all_values()
                    self.thread_validation = pd.DataFrame(columns=['Usuario', 'ID', 'AssistantID', 'ThreadID'], data=self.user_values)
                    
                except Exception as e:
                    await turn_context.send_activity(f"Ocurrió un error al crear el Asistente. Intenta de nuevo.\n{e}")
                    return
            else:
                # Extraer el perfil del usuario en caso de contar con uno
                self.user_assistant = self.thread_validation.loc[self.thread_validation['ID'] == self.conversation.id]
                self.assistant_id = self.user_assistant['AssistantID'].values[0]
                self.thread_id = self.user_assistant['ThreadID'].values[0]


    async def handle_run(self, turn_context, thread_handle):
        # Crea la solicitud del usuario en su respectivo hilo
        thread_handle.messages.create(
                thread_id=self.thread_id,
                role='user',
                content=f"Name: {self.user_name}\nDate: {datetime.datetime.now()}\nPrompt: {turn_context.activity.text}"
            )

        # Administra la ejecución del modelo para responder a la solicitud del usuario
        run = thread_handle.runs.create(thread_id=self.thread_id, assistant_id=self.assistant_id)
        
        # Revisa que la respuesta esté completa para poder regresarla
        while run.status in ["queued", "in_progress", "requires_action"]:
            await asyncio.sleep(1)
            run = thread_handle.runs.retrieve(thread_id=self.thread_id, run_id=run.id)
        
        if run.status == "completed":
            messages = self.client.beta.threads.messages.list(thread_id=self.thread_id)
            # Aplica la función limpiar_texto antes de enviar el mensaje al usuario
            await turn_context.send_activity(self.clean_output(messages.data[0].content[0].text.value))

        
    # Desencadenante del flujo de trabajo para responder a la solicitud del usuario
    async def on_message_activity(self, turn_context: TurnContext):
        
        message = turn_context.activity
        mentions = turn_context.get_mentions(turn_context.activity)
        self.conversation = turn_context.activity.conversation
        
        # Asegurarse de que la conversación está en un grupo
        if self.conversation.is_group:
            # Si hay menciones
            if mentions:
                if not any(mention.additional_properties['mentioned']['id'] == turn_context.activity.recipient.id for mention in mentions):
                   return
            # Si no hay menciones al bot y estamos en un grupo abandonamos la conversación
            else:
                try:
                    if not re.search(r".*oye.{0,2}luigi.*", turn_context.activity.text.lower().replace(',', ' ')):
                        return
                except:
                    return

        self.user_data = message.from_property
        self.user_name = self.user_data.name
        thread = self.client.beta.threads

        # self.message_metadata_2gs(turn_context)
        await self.user_management(turn_context=turn_context, thread_handle=thread)
        
        assistants_list = self.client.beta.assistants.list()
        assistants = assistants_list.data
        while assistants_list.has_more:
            assistants_list = self.client.beta.assistants.list(
                after=assistants_list.last_id
            )
            assistants += assistants_list.data
        

        if self.assistant_id in [ass.id for ass in assistants]:
            await self.handle_run(turn_context, thread_handle=thread)
        else:
            idx = self.thread_validation[self.thread_validation['ID'] == self.conversation.id].index[0]
            self.user_metadata.delete_rows(int(idx + 1))
        
            await turn_context.send_activity('Espera, parece ser que hubo un error en nuestra conversación.')
            await self.user_management(turn_context, thread_handle=thread)
            await self.handle_run(turn_context, thread_handle=thread)


    # Recibe al usuario al principio de la conversación
    async def on_members_added_activity(
        self,
        members_added: ChannelAccount,
        turn_context: TurnContext
    ):
        for member_added in members_added:
            if member_added.id != turn_context.activity.recipient.id:
                try:
                    name = turn_context.activity.from_property.name
                    await turn_context.send_activity(f"Hola {name.split()[0]}, ¡soy Gerbie! Tu asistente comercial de GERB y estoy aquí para ayudarte.\n¿Cómo puedo ayudarte el día de hoy?")
                except:
                    await turn_context.send_activity(f"Hola, ¡soy Gerbie! Tu asistente comercial de GERB y estoy aquí para ayudarte.\n¿Cómo puedo ayudarte el día de hoy?")
